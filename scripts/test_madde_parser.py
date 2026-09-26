#!/usr/bin/env python3
"""
pdf_to_madde_json.py için regresyon testleri.

Çalıştırma:
    cd scripts && python3 test_madde_parser.py

Kapsam:
  - Normal madde başlıkları (MADDE 14 –, Madde 4 —, Madde 87 ( )
  - Harfli madde başlıkları (MADDE 24/A, Madde 20/A)
  - Ek madde ve geçici madde başlıkları
  - Akan metindeki atıfların yanlışlıkla başlık sayılmaması
  - Aynı numaralı çift maddede kimlik çakışmaması
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pdf_to_madde_json import maddelere_ayir, kuyrugu_kes, provision_id_uret

basarisiz = 0


def kontrol(ad: str, kosul: bool, detay: str = ""):
    global basarisiz
    if kosul:
        print(f"  GECTI  {ad}")
    else:
        print(f"  KALDI  {ad}" + (f"  -> {detay}" if detay else ""))
        basarisiz += 1


print("1. Madde basligi cesitleri")

ORNEK = """
MADDE 1 – Bu Kanunun amaci sudur.

Madde 4 — Ikinci bir madde metni.

Madde 87 (Mülga: 20/6/2012-6331/37 md.)

MADDE 24/A – (Ek: 4/4/2015-6645/4 md.) Harfli madde metni.

MADDE 25/A – Ikinci harfli madde.

Madde 20/A - Kucuk harfli yazim ile harfli madde.

EK MADDE 2 – (Ek: 29/1/2016-6663/23 md.) Ek madde metni.

GEÇİCİ MADDE 12 – (Ek:23/1/2026-7573/6 md.) Gecici madde metni.

Geçici Madde 8- Tire bosluksuz gecici madde.
"""

maddeler = maddelere_ayir(ORNEK)
bulunan = {(m["madde_no"], m["madde_turu"]) for m in maddeler}

kontrol("MADDE 1 (tire ile)", ("1", "normal") in bulunan)
kontrol("Madde 4 (em-dash ile)", ("4", "normal") in bulunan)
kontrol("Madde 87 (parantez ile)", ("87", "normal") in bulunan)
kontrol("MADDE 24/A (harfli)", ("24/A", "normal") in bulunan,
        f"bulunanlar: {sorted(bulunan)}")
kontrol("MADDE 25/A (harfli)", ("25/A", "normal") in bulunan)
kontrol("Madde 20/A (harfli, kucuk harf baslik)", ("20/A", "normal") in bulunan)
kontrol("EK MADDE 2", ("2", "ek") in bulunan)
kontrol("GEÇİCİ MADDE 12", ("12", "gecici") in bulunan)
kontrol("Geçici Madde 8 (bosluksuz tire)", ("8", "gecici") in bulunan)
kontrol("Toplam 9 madde", len(maddeler) == 9, f"bulunan: {len(maddeler)}")

print()
print("2. Harfli madde, sade numaraliya karismamali")

karisik = [m for m in maddeler if m["madde_no"] == "24"]
kontrol("'24' diye ayri bir madde uretilmedi", len(karisik) == 0,
        f"bulundu: {len(karisik)}")

m24a = next((m for m in maddeler if m["madde_no"] == "24/A"), None)
kontrol("24/A metni kendi govdesinde", m24a is not None and "Harfli madde metni" in m24a["govde"])

print()
print("3. Akan metindeki atiflar baslik sayilmamali")

ATIF = """
MADDE 5 – Bu maddede 14 uncu maddesi hukumlerine atif yapilir ve
ayrica 4857 sayili Kanunun 74 uncu maddesi ile 25 inci maddesi
uygulanir. Madde 30 hukmu saklidir.
"""
atif_maddeleri = maddelere_ayir(ATIF)
kontrol("Sadece 1 madde yakalandi", len(atif_maddeleri) == 1,
        f"bulunan: {[m['madde_no'] for m in atif_maddeleri]}")

print()
print("4. Kuyruk (degisiklik tablosu) kesilmeli")

KUYRUKLU = ("MADDE 1 – Gercek madde metni. " + ("dolgu " * 200) +
            "\n4857 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN\n"
            "YÜRÜRLÜĞE GİRİŞ TARİHİNİ GÖSTERİR LİSTE\n"
            "Geçici Madde 9 - 112, Ek Madde 2 - 91, 92")
kesilmis, kesildi = kuyrugu_kes(KUYRUKLU)
kontrol("Kuyruk kesildi", kesildi)
kontrol("Kuyruktaki sahte maddeler alinmadi", len(maddelere_ayir(kesilmis)) == 1,
        f"bulunan: {[m['madde_no'] for m in maddelere_ayir(kesilmis)]}")

print()
print("5. provision_id uretimi")

kontrol("harfli id dogru",
        provision_id_uret("6331", {"madde_turu": "normal", "madde_no": "24/A"})
        == "law:6331:article:24/A")
kontrol("ek madde id dogru",
        provision_id_uret("4857", {"madde_turu": "ek", "madde_no": "2"})
        == "law:4857:ek-madde:2")
kontrol("gecici madde id dogru",
        provision_id_uret("5510", {"madde_turu": "gecici", "madde_no": "79"})
        == "law:5510:gecici-madde:79")

print()
if basarisiz:
    print(f"SONUC: {basarisiz} test BASARISIZ")
    sys.exit(1)
print("SONUC: tum testler gecti")
