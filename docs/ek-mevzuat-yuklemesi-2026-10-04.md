# Ek Mevzuat Yüklemesi — 17 dosya, 1544 madde

Tarih: 4 Ekim 2026

Mevcut 7 kanuna (701 madde) ek olarak 17 mevzuat daha madde bazında
ayrıştırıldı. Toplam havuz: 24 mevzuat, 2245 madde.

## Eklenen dosyalar

### Yönetmelikler (12)
| MevzuatNo | Ad | Madde |
|---|---|---|
| 5451 | Yıllık Ücretli İzin Yönetmeliği | 23 |
| 38393 | Uzaktan Çalışma Yönetmeliği | 16 |
| 45087 | Çalışanların İSG Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik | 30 |
| 18493 | İşyerlerinde Acil Durumlar Hakkında Yönetmelik | 25 |
| 16924 | İSG Hizmetleri Yönetmeliği | 32 |
| 16925 | İSG Risk Değerlendirmesi Yönetmeliği | 20 |
| 16923 | İş Güvenliği Uzmanları Yönetmeliği | 51 |
| 18615 | İşyeri Hekimi ve Diğer Sağlık Personeli Yönetmeliği | 59 |
| 17288 | Ekranlı Araçlarla Çalışmalar Yönetmeliği | 12 |
| 18318 | İş Ekipmanlarının Kullanımı Yönetmeliği | 33 |
| 32659 | Sıfır Atık Yönetmeliği | 25 |
| 13973 | Sosyal Sigorta İşlemleri Yönetmeliği | 167 |

### Kanunlar (5)
| No | Ad | Madde |
|---|---|---|
| 5746 | Ar-Ge ve Tasarım Faaliyetlerinin Desteklenmesi | 8 |
| 2872 | Çevre Kanunu | 61 |
| 6098 | Türk Borçlar Kanunu | 651 |
| 6356 | Sendikalar ve Toplu İş Sözleşmesi Kanunu | 92 |
| 193 | Gelir Vergisi Kanunu | 239 |

## Önemli: 18371 artık geçersiz

Listede 18371 (Çalışanların İSG Eğitimleri Yönetmeliği, 15/5/2013) vardı
ama o yönetmelik **2 Nisan 2026 tarihli ve 33212 sayılı Resmî Gazete ile
yürürlükten kaldırıldı.** Yerine geçen yeni yönetmelik yüklendi:
MevzuatNo 45087.

Yeni yönetmeliğin 27. maddesi eskisini kaldırıyor, Geçici Madde 1 ise
eski yönetmelik kapsamında verilen eğitimleri geçerli sayıyor.

Bu aynı zamanda test seti için gerçek bir vaka: aynı gün hem mülga hem
yeni yayın. Sistemin "yerine yenisi geldi" durumunu doğru ayırt etmesi
gerekiyor.

## Doğrulama

- 17 PDF'in tamamında metin katmanı var, OCR gerekmedi.
- Her PDF'in ilk sayfasındaki başlık beklenen mevzuat adıyla karşılaştırıldı,
  hepsi uyuştu.
- Madde numaralarında atlama taraması yapıldı. Üç dosyada eksik görünen
  numara çıktı, üçü de incelendi ve script hatası olmadığı doğrulandı:
  - **2872 Madde 7**: PDF'te "Madde 6 – 7 – (Mülga: 8/6/1984-KHK 222/30 md.)"
    şeklinde, iki madde tek satırda birleşik. Mülga, içerik kaybı yok.
  - **193 Madde 115**: PDF'te hiç geçmiyor, mülga edilip metinden çıkarılmış.
  - **6098 Madde 428**: PDF'te hiç geçmiyor, aynı durum.
- Aynı numaralı maddeler (193'te 14, 2872'de 6, 6098'de 1) incelendi.
  Hepsi farklı değişiklik kanunlarıyla eklenmiş geçici maddeler, gerçek.
  `#2`, `#3` soneki ile ayrıştırıldılar.
- 17 harfli madde yakalandı (16923: 28/A, 34/A, 35/A | 16924: 17/A, 22/A |
  18318: 3/A, 6/A, 7/A, 13/A, 14/A, 14/B | 18615: 35/A, 35/B, 41/A, 42/A).
  Harfli madde düzeltmesi yapılmamış olsaydı bunların hepsi kaybolacaktı.

## Oryantasyon modülünü ilgilendiren bulgu (45087)

Yeni İSG eğitim yönetmeliği, oryantasyon modülünün hukuki konumunu
netleştiriyor:

- **Madde 7**: İşe başlama eğitimi uygulamalı ve **yüz yüze** verilmek
  zorunda, en az iki saat, tutanakla imzalanıp özlük dosyasında saklanır.
  Bu kısmın yerini bir sistem alamaz.
- **Madde 12/2**: Ek-1'deki birinci, ikinci ve üçüncü konu başlıkları
  **tüm işyerlerinde uzaktan** verilebilir. Dördüncü başlık az tehlikeli
  sınıfta uzaktan verilebilir.
- **Madde 12/4**: Uzaktan eğitimde giriş-çıkışlar, tamamlama oranları,
  ölçme sonuçları kayıt altına alınır, izlenir ve raporlanır.
- **Madde 12/5**: İleri sarma, sekme, pencere kapatma gibi eğitimin
  verimliliğini olumsuz etkileyecek davranışlar engellenmeli.
- **Madde 16/3**: Sınavda 100 üzerinden **en az 60 puan** geçme notu.
  Başarısız olan **en fazla iki kez daha** girebilir, yine başarısızsa
  eğitime yeniden katılır.

Sonuç: Sistem işe başlama eğitiminin yerini almaz, ama temel eğitimin
uzaktan verilebilen kısmını karşılayabilir ve mevzuatın istediği
kayıt/izleme/raporlama yükümlülüğünü yerine getirir.

**Quiz tasarımı buna göre güncellenmeli**: 60 puan geçme notu, en fazla
3 deneme hakkı, video oynatıcıda ileri sarma kapalı.

## Kaynak ve yöntem

Tüm PDF'ler mevzuat.gov.tr'den **elle** indirildi (site robots.txt ile
otomatik erişimi engelliyor), `scripts/pdf_to_madde_json.py` ile
işlendi. Format mevcut JSON'larla aynı.
