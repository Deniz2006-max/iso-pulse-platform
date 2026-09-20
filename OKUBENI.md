# Mevzuat Yükleme Kiti

## Neden bu şekilde?

mevzuat.gov.tr'nin robots.txt'i **otomatik erişimi engelliyor** (test edildi,
doğrulandı). Yani bu siteyi kod ile scriptletmeyin. Bunun yerine:

1. PDF'i tarayıcıdan elle indirin (bir insanın "Farklı Kaydet" yapması
   robots.txt'in engellediği şey değil, bot trafiği engelleniyor).
2. `pdf_to_madde_json.py` scriptini o PDF üzerinde ÇALIŞTIRIN (bu adım
   internete hiç çıkmıyor, sadece diskteki dosyayı okuyor).
3. Çıkan JSON dosyasını repoya commit edin.

Bu yüzden mevzuat.gov.tr için gece taraması KURMAYIN. Otomatik gece
taraması sadece Resmî Gazete için olacak (o sitede robots engeli yok,
sadece TLS/tarayıcı taklidi sorunu var — Playwright ile çözülüyor).
mevzuat.gov.tr'deki kanun metinleri "sabit temel veri" (baseline), her
gece değil, ara sıra elle güncellenir.

## Kullanım

```bash
pip install pymupdf --break-system-packages

python3 pdf_to_madde_json.py 4857_indirilen.pdf \
    --no 4857 \
    --baslik "İş Kanunu" \
    --url "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.4857.pdf" \
    --cikti data/mevzuat/4857_is_kanunu.json
```

Aynısını diğer 6 kanun için tekrarlayın, sadece `--no`, `--baslik`, `--url`
ve `--cikti` değerlerini değiştirin.

## Yönetmelikler için

Yönetmelikler de aynı script ile çalışır, sadece `--no` yerine mevzuat
numarasını (MevzuatNo) kullanın. Örnek:

```bash
python3 pdf_to_madde_json.py yillik_izin_yonetmeligi.pdf \
    --no 5451 \
    --baslik "Yıllık Ücretli İzin Yönetmeliği" \
    --url "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5451&MevzuatTur=7&MevzuatTertip=5" \
    --cikti data/mevzuat/5451_yillik_izin_yonetmeligi.json
```

## Çıktı formatı

`agentic-data-handoff-proposal.md` dosyasındaki
`legislation-context.json` şemasına uyumlu:

```json
{
  "documents": [{
    "document_id": "law:4857",
    "title": "İş Kanunu",
    "canonical_url": "...",
    "current_version_id": "law:4857:sha256:...",
    "included_provisions": [
      {
        "provision_id": "law:4857:article:74",
        "label": "Madde 74",
        "madde_turu": "normal",
        "mulga": false,
        "text": "...",
        "normalized_hash": "..."
      }
    ]
  }]
}
```

`madde_turu`: `normal` / `ek` / `gecici`.

## Bilinen sınır

`mulga: true` bayrağı kaba bir sezgi — "mülga" veya "yürürlükten
kaldırılmıştır" kelimesi maddenin ilk 150 karakterinde geçiyorsa
işaretliyor. Bazen maddenin TAMAMI değil sadece bir FIKRASI mülga
olabilir (script bunu ayırt etmiyor). Kritik maddelerde (46, 53-60,
63-68, 74, Ek Madde 2 gibi) elle bir göz atın.

---

# İŞLEME RAPORU (19 Eylül 2026)

7 kanunun tamamı işlendi. Sonuçlar:

| Kanun | Normal | Ek | Geçici | Mülga | Toplam |
|---|---:|---:|---:|---:|---:|
| 4857 İş Kanunu | 122 | 3 | 12 | 20 | 137 |
| 4447 İşsizlik Sigortası | 25 | 7 | 37 | 0 | 69 |
| 4632 Bireysel Emeklilik | 28 | 2 | 5 | 2 | 35 |
| 5174 TOBB/Odalar | 105 | 1 | 19 | 0 | 125 |
| 5510 Sosyal Sigortalar | 109 | 24 | 113 | 14 | 246 |
| 6331 İSG | 39 | 1 | 10 | 2 | 50 |
| 6698 KVKK | 33 | 0 | 3 | 0 | 36 |

## Doğrulama

- **4857**: Madde 1-122 eksiksiz, hiçbir numara atlanmadı.
- **6698**: 33 normal + 3 geçici çıktı; kanunun gerçek yapısıyla birebir
  aynı (MADDE 1-33, GEÇİCİ MADDE 1-3). Bu, script'in doğru çalıştığının
  en güçlü kanıtı.
- Kritik maddeler elle kontrol edildi ve güncel içerik teyit edildi:
  - 4857 Ek Madde 2: "eşinin doğum yapması hâlinde ise **on gün**"
    (7578 değişikliği işlenmiş)
  - 4857 Madde 74: "doğumdan sonra **onaltı hafta**, toplam **yirmidört
    hafta**" (7578 değişikliği işlenmiş)
  - 5510 Madde 81: "%9'u sigortalı hissesi, **%12'si işveren**"
    (7566 değişikliği işlenmiş)
  - 6698 Madde 9: "(Değişik:2/3/2024-7499/34 md.)" (yurt dışı aktarım
    yeni rejimi işlenmiş)

## Geliştirme sırasında bulunan 3 tuzak

Bunlar script'te düzeltildi ama benzer kod yazacak herkesin bilmesi
gerekiyor:

**1. Türkçe İ/I sorunu.** Python'da `"Geçici".upper()` → `"GEÇICI"`
(noktasız I) verir. `"GEÇİCİ"` (noktalı İ) ile karşılaştırma sessizce
başarısız olur. İlk denemede 12 geçici madde "normal" diye
etiketlenmişti ve hiçbir hata mesajı çıkmamıştı. Çözüm: `.upper()`
kullanmayın, eşleşen metni olduğu gibi kontrol edin.

**2. PDF sonundaki değişiklik tablosu.** mevzuat.gov.tr PDF'lerinin
sonunda "EK VE DEĞİŞİKLİK GETİREN MEVZUATIN ... LİSTE" başlıklı bir
tablo var. İçinde "Geçici Madde 9", "Ek Madde 2" gibi ifadeler geçiyor
ama bunlar madde metni değil, sadece referans. Kesilmezse sahte madde
üretir. Script artık bu tabloyu otomatik kesiyor.

**3. Aynı numaralı iki madde.** 5510'a 5/12/2019'da 7194 sayılı Kanunla
bir "Geçici Madde 79", ertesi gün 6/12/2019'da 7196 sayılı Kanunla BİR
TANE DAHA "Geçici Madde 79" eklenmiş. İkisi de yürürlükte. Aynı durum
4447'de de var. provision_id çakışmasın diye ikinciye `#2` soneki
veriliyor. Bu önlem alınmazsa veritabanında biri diğerinin üstüne yazar
ve veri sessizce kaybolur.

## Test seti için not

4632 Ek Madde 2 (BES otomatik katılım) incelendiğinde:

- 7351 değişikliği metinde MEVCUT: "(Ek cümle:19/1/2022-7351/7 md.)
  Kırk beş yaşını doldurmuş çalışanlar, talep etmeleri halinde anılan
  planlara dahil edilebilir."
- Cayma süresi: "iki ay içinde sözleşmeden cayabilir. (Ek cümle:
  21/3/2018-7103/45 md.) Bu süreyi üç katına kadar artırmaya
  Cumhurbaşkanı yetkilidir."

Yani İSO'nun 2017 tarihli BES çalışan sunumundaki "45 yaşını
doldurmamış" ifadesi artık eksik, "60 gün cayma" ifadesi de
Cumhurbaşkanı kararıyla değişmiş olabilir. Oryantasyon içeriği
güncelleme vakası olarak kullanılabilir.
