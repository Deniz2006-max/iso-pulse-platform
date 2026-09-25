#!/usr/bin/env python3
"""
İSO Pulse - Kanun/Yönetmelik PDF'ini madde madde JSON'a çeviren script.

Kullanım:
    python3 pdf_to_madde_json.py <pdf_dosyasi> \
        --no 4857 \
        --baslik "İş Kanunu" \
        --url "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.4857.pdf" \
        --cikti data/mevzuat/4857_is_kanunu.json

Girdi:  Elle indirilmiş bir mevzuat.gov.tr PDF'i.
Çıktı:  agentic-data-handoff-proposal.md'deki legislation-context.json
        şemasına uygun, tek bir JSON dosyası.
"""

import argparse
import hashlib
import json
import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Kurulum gerekli: pip install pymupdf --break-system-packages")
    sys.exit(1)


# "MADDE 14 –", "Madde 4 —", "EK MADDE 2 –", "GEÇİCİ MADDE 12 –" yakalar.
# Türkçe büyük/küçük İ-I sorununu önlemek için hem büyük hem küçük yazımı
# ayrı ayrı listeliyoruz, tek bir IGNORECASE'e güvenmiyoruz.
# Madde numarasından sonra ya bir tire gelir ("MADDE 14 –") ya da
# doğrudan parantez ("Madde 87 (Mülga: ...)"). İkisini de yakalıyoruz.
# Sadece rakamla bitmesine izin VERMİYORUZ, yoksa akan metindeki
# "...14 üncü maddesi" gibi ifadeler sahte madde üretir.
#
# HARFLİ NUMARALAR: Bazı maddeler "Madde 24/A" biçimindedir (6331'de
# 24/A ve 25/A, 4632'de 20/A). Bunlar ayrı maddedir. Harf kısmı
# opsiyonel; yakalanmazsa bu başlıklar bir önceki maddenin metnine
# karışır ve ayrı kayıt olarak görünmez.
MADDE_RE = re.compile(
    r'^\s*((?:EK\s+MADDE|GEÇİCİ\s+MADDE|Ek\s+Madde|Geçici\s+Madde|MADDE|Madde))'
    r'\s+(\d+)\s*(?:/\s*([A-ZÇĞİÖŞÜa-zçğıöşü]))?\s*(?:[–—-]|\()',
    re.MULTILINE
)

MULGA_ANAHTAR = ("mülga", "yürürlükten kaldırılmıştır")


def pdf_den_metin_cikar(pdf_yolu: str) -> str:
    """PDF'in tüm sayfalarından düz metni çıkarır ve temizler."""
    doc = fitz.open(pdf_yolu)
    parcalar = [sayfa.get_text("text") for sayfa in doc]
    doc.close()
    metin = "\n".join(parcalar)
    metin = metin.replace("\u00ad", "")          # yumuşak tire
    metin = metin.replace("\u00b7", " ")          # orta nokta
    metin = re.sub(r"-\n(\w)", r"\1", metin)      # satır sonu bölünmüş kelime
    metin = re.sub(r"[ \t]+", " ", metin)
    return metin


# mevzuat.gov.tr PDF'lerinin sonunda "... EK VE DEĞİŞİKLİK GETİREN
# MEVZUATIN ... YÜRÜRLÜĞE GİRİŞ TARİHİNİ GÖSTERİR LİSTE" başlıklı bir
# tablo var. Bu tabloda "Geçici Madde 9", "Ek Madde 2" gibi ifadeler
# geçiyor ama bunlar madde metni DEĞİL, sadece referans. Kesmezsek
# sahte madde üretiyor.
KUYRUK_ISARETLERI = (
    "EK VE DEĞİŞİKLİK GETİREN MEVZUATIN",
    "EK VE DEĞİŞİKLİK GETİREN",
    "YÜRÜRLÜĞE GİRİŞ TARİHİNİ GÖSTERİR",
)


def kuyrugu_kes(metin: str) -> tuple[str, bool]:
    """Sondaki değişiklik tablosunu keser. (kesilmiş_metin, kesildi_mi)"""
    en_erken = len(metin)
    for isaret in KUYRUK_ISARETLERI:
        yer = metin.find(isaret)
        # Belgenin ilk yarısındaki eşleşmeleri yok say (başlıkta geçebilir)
        if yer > len(metin) // 2:
            en_erken = min(en_erken, yer)
    if en_erken < len(metin):
        return metin[:en_erken], True
    return metin, False


def maddelere_ayir(metin: str) -> list[dict]:
    """Metni madde/ek madde/geçici madde sınırlarında böler."""
    eslesmeler = list(MADDE_RE.finditer(metin))
    if not eslesmeler:
        return []

    maddeler = []
    for i, m in enumerate(eslesmeler):
        bas = m.start()
        son = eslesmeler[i + 1].start() if i + 1 < len(eslesmeler) else len(metin)
        govde = metin[bas:son].strip()

        # DİKKAT: Türkçe İ/I sorunu nedeniyle .upper() KULLANMIYORUZ.
        # Python'da "Geçici".upper() -> "GEÇICI" (noktasız I) verir ve
        # "GEÇİCİ" ile karşılaştırma başarısız olur. Onun yerine
        # eşleşen metni olduğu gibi, boşlukları atarak kontrol ediyoruz.
        tur_etiketi = m.group(1).replace(" ", "").replace("\n", "")
        # Harfli madde: "Madde 24/A" -> madde_no "24/A" olur.
        # Harf yoksa m.group(3) None gelir, sade numara kalır.
        harf = m.group(3)
        madde_no = m.group(2) + (f"/{harf.upper()}" if harf else "")

        if tur_etiketi in ("EKMADDE", "EkMadde", "Ekmadde"):
            madde_turu = "ek"
        elif tur_etiketi in ("GEÇİCİMADDE", "GeçiciMadde", "Geçicimadde"):
            madde_turu = "gecici"
        else:
            madde_turu = "normal"

        ilk_120_karakter = govde[:150].lower()
        mulga = any(k in ilk_120_karakter for k in MULGA_ANAHTAR)

        maddeler.append({
            "madde_no": madde_no,
            "madde_turu": madde_turu,
            "mulga": mulga,
            "govde": govde,
        })
    return maddeler


def provision_id_uret(mevzuat_no: str, madde: dict) -> str:
    on_ek = {"normal": "article", "ek": "ek-madde", "gecici": "gecici-madde"}[madde["madde_turu"]]
    return f"law:{mevzuat_no}:{on_ek}:{madde['madde_no']}"


def label_uret(madde: dict) -> str:
    on_ek = {"normal": "Madde", "ek": "Ek Madde", "gecici": "Geçici Madde"}[madde["madde_turu"]]
    return f"{on_ek} {madde['madde_no']}"


def sha256_kisa(metin: str) -> str:
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("girdi", help="PDF dosya yolu veya .txt (test için)")
    ap.add_argument("--no", required=True, help="Mevzuat numarası, örn. 4857")
    ap.add_argument("--baslik", required=True, help="Mevzuat adı")
    ap.add_argument("--url", required=True, help="Kaynak URL (canonical_url)")
    ap.add_argument("--cikti", required=True, help="Çıktı JSON dosya yolu")
    args = ap.parse_args()

    if args.girdi.lower().endswith(".pdf"):
        metin = pdf_den_metin_cikar(args.girdi)
    else:
        # .txt: test/sahte veri için, PDF gerekmez
        with open(args.girdi, encoding="utf-8") as f:
            metin = f.read()

    metin, kuyruk_kesildi = kuyrugu_kes(metin)
    if kuyruk_kesildi:
        print("Bilgi: Sondaki 'değişiklik getiren mevzuat' tablosu kesildi.")

    maddeler = maddelere_ayir(metin)

    if not maddeler:
        print("UYARI: Hiç madde bulunamadı. Regex kalıbı bu belgeye uymuyor "
              "olabilir, elle kontrol edin.")
        sys.exit(1)

    # Aynı numaralı madde birden fazla olabilir. Bu bir hata değil:
    # örn. 5510'a 5/12/2019-7194 ile bir "Geçici Madde 79", ertesi gün
    # 6/12/2019-7196 ile BİR TANE DAHA "Geçici Madde 79" eklenmiş ve
    # ikisi de yürürlükte. provision_id çakışmasın diye ikinciden
    # itibaren sonek veriyoruz, yoksa veritabanında biri diğerinin
    # üstüne yazar ve sessizce veri kaybolur.
    sayac: dict[str, int] = {}
    provisions = []
    cakisma_sayisi = 0
    for m in maddeler:
        temel_id = provision_id_uret(args.no, m)
        sayac[temel_id] = sayac.get(temel_id, 0) + 1
        if sayac[temel_id] == 1:
            pid = temel_id
            lbl = label_uret(m)
        else:
            pid = f"{temel_id}#{sayac[temel_id]}"
            lbl = f"{label_uret(m)} ({sayac[temel_id]}. örnek)"
            cakisma_sayisi += 1

        provisions.append({
            "provision_id": pid,
            "label": lbl,
            "madde_turu": m["madde_turu"],
            "mulga": m["mulga"],
            "text": m["govde"],
            "normalized_hash": sha256_kisa(m["govde"]),
        })

    cikti = {
        "documents": [{
            "document_id": f"law:{args.no}",
            "title": args.baslik,
            "canonical_url": args.url,
            "current_version_id": f"law:{args.no}:sha256:{sha256_kisa(metin)}",
            "included_provisions": provisions,
        }]
    }

    with open(args.cikti, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)

    normal_sayisi = sum(1 for m in maddeler if m["madde_turu"] == "normal")
    ek_sayisi = sum(1 for m in maddeler if m["madde_turu"] == "ek")
    gecici_sayisi = sum(1 for m in maddeler if m["madde_turu"] == "gecici")
    mulga_sayisi = sum(1 for m in maddeler if m["mulga"])

    print(f"Toplam {len(maddeler)} madde bulundu:")
    print(f"  - {normal_sayisi} normal madde")
    print(f"  - {ek_sayisi} ek madde")
    print(f"  - {gecici_sayisi} geçici madde")
    print(f"  - {mulga_sayisi} mülga işaretli")
    if cakisma_sayisi:
        print(f"  - {cakisma_sayisi} aynı numaralı madde (#2, #3 soneki verildi)")
    print(f"Yazıldı: {args.cikti}")


if __name__ == "__main__":
    main()
