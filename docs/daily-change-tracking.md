# Günlük yayın değişiklik takibi

Her çalıştırmada kaynak JSON dosyaları ve `all.json` yanında `change_report.json`
üretilir. Önceki karşılaştırma durumu, çıktı kökündeki `.change_tracking/state.json`
dosyasında tutulur. Bu dosya sonraki çalıştırmalarda korunmalıdır.

- `new`: Bu kaynak kimliği için ilk dolu metin gözlemi; yayının bugün yayımlandığını söylemez.
- `changed`: Aynı kimlik için başlık, kategori veya çıkarılan metnin normalize edilmiş özeti değişti.
- `unchanged`: Karşılaştırılan alanların özeti aynı.
- `unverified`: Çıkarılan metin boş. Önceki dolu metnin özeti korunur.

SHA-256 karşılaştırması hukuki değişikliğin doğrulandığı veya belgenin eksiksiz
çıkarıldığı anlamına gelmez. Dolu fakat eksik bir metin de karşılaştırılabilir.
Metin çıkarımının kalitesi ve kaynak kanıtlarının doğrulanması ayrıca gerekir.
Yeni RG yayını, başka bir URL'deki eski kanunla otomatik olarak karşılaştırılmaz.

İlk çalıştırma başlangıç kaydı oluşturur. Aynı tarih ve içerikle tekrar çalıştırma,
o tarihin önceki durumunu ve karşılaştırma özetini korur. Kaybolan kayıtlar silinmiş
sayılmaz. RG belirli bir sayıdan, SGK sınırlı bir güncel listeden toplanır.

`collection.failed_sources` yakalanan kaynak hatalarını;
`collection.unconfirmed_sources` hata atmadan boş dönen temel kaynakları gösterir.
`partial` bu durumlarda veya boş metin bulunduğunda `true` olur. `partial=false`
tüm kaynak kapsamının ya da eklerin eksiksiz olduğunun garantisi değildir.
Kaynak istisnalarında komut 1 çıkış kodu verir; toplanabilen diğer kayıtlar saklanır.

## Doğrulama

Proje bağımlılıklarının kurulu olduğu ortamda:

```cmd
python -m unittest discover -s tests -v
python -m src.ingestion.fetch_daily_updates --source all --date 2026-10-05 --max-items 1 --out-dir data/daily_updates/_smoke
```

Birim ve entegrasyon testleri kontrollü, açıkça sentetik kayıtlarla karşılaştırma,
yeniden çalıştırma, kaynak hatası, boş sonuç ve mevcut JSON biçimini sınar.

2026-10-05 tarihinde ilk bağlantı denemesi başarısız oldu; sonraki canlı doğrulamada
iki RG yayını ve iki SGK duyurusu iki kez toplandı. Her iki çalıştırma da 0 çıkış
koduyla tamamlandı. Kayıt kimlikleri ve içerik özetleri aynı kaldı. Aynı gün tekrar
çalıştırma tasarımı nedeniyle her iki raporda da 3 `new`, 1 `unverified` vardı.
Gerçek bir içerik değişikliği gözlenmedi; `changed` yolu kontrollü testlerle sınandı.

| Örnek | Kontrol sonucu |
| --- | --- |
| [Ankara Medipol Üniversitesi yönetmeliği](https://www.resmigazete.gov.tr/eskiler/2026/10/20261005-1.htm) | 82.718 karakter; taze resmi HTML yanıtının metin çıkarımıyla aynı. |
| [Beykoz Üniversitesi yönetmelik değişikliği](https://www.resmigazete.gov.tr/eskiler/2026/10/20261005-2.htm) | 10.772 karakter; taze resmi HTML yanıtının metin çıkarımıyla aynı. |
| [SGK Gayrimenkul Satış İlanı](https://www.sgk.gov.tr/duyuru/detay/Gayrimenkul-Satis-Ilani-2026-10-05-11-35-26) | 98 sayfalık PDF erişilebilir. SGK için 40 sayfalık kesme kaldırıldı; tüm sayfalardan elde edilen metin kayıtta mevcut (başlıklarla 61.666 karakter). Görsel içeriğe OCR uygulanmadı. |
| [Güncel 2013 SUT duyurusu](https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06) | Ek ZIP biçiminde. Başlık ve ek adı yanlışlıkla belge metni sayılıyordu. Düzeltmeden sonra boş metin ve `unverified`; `partial=true`. |

SGK'da herhangi bir ekten metin alınamıyorsa kaydın metni boş bırakılır; diğer
eklerden gelen kısmi metin karşılaştırma başlangıcı olarak kabul edilmez.
ZIP açma ve OCR desteği bu değişikliğe dahil değildir. Karşılaştırma raporu uygulama
tarafından henüz filtre olarak tüketilmez; `all.json` kayıtları mevcut biçimde kalır.

16 birim ve entegrasyon testi başarılı. Yerel ham yanıtlar ve ilk kontrol manifesti
`data/daily_updates/_live_validation/evidence/` altında; son iki canlı rapor ve
`validation_summary.json`, `data/daily_updates/_live_validation_final/` altında saklandı.
Bu üretilmiş dosyalar Git tarafından dışlanır. Örnekler teknik doğrulama içindir;
İSO üyelerine konu uygunluğu bu denemede değerlendirilmedi.

Bu sürüm tek kolektör süreci için tasarlanmıştır. Aynı çıktı köküne eşzamanlı
yazılmamalıdır. Durum dosyası özetleri saklar; tam sürüm arşivi veya madde bazında
hukuki değişiklik analizi sağlamaz.

Karşılaştırma son saklanan gözleme dayanır. Geçmiş tarih denemeleri için ayrı
`--out-dir` kullanın: RG seçilen tarihin sayısını getirirken SGK güncel listesini
getirir; `--date` SGK için geçmiş tarih filtresi değildir.
