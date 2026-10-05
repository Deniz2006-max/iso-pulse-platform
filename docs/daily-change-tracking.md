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

2026-10-05 canlı denemesinde bu ortamdan RG ve SGK bağlantıları kurulamadı.
Gerçek belge alınmadı. Bu deneme hata yolunu doğrulamak için kullanıldı; başarılı
canlı veri toplama testi olarak değerlendirilmemelidir. Birleştirmeden önce kaynaklara
erişebilen ortamda yukarıdaki küçük örnekle gerçek metin ve rapor kontrol edilmelidir.

Bu sürüm tek kolektör süreci için tasarlanmıştır. Aynı çıktı köküne eşzamanlı
yazılmamalıdır. Durum dosyası özetleri saklar; tam sürüm arşivi veya madde bazında
hukuki değişiklik analizi sağlamaz.

Karşılaştırma son saklanan gözleme dayanır. Geçmiş tarih denemeleri için ayrı
`--out-dir` kullanın: RG seçilen tarihin sayısını getirirken SGK güncel listesini
getirir; `--date` SGK için geçmiş tarih filtresi değildir.
