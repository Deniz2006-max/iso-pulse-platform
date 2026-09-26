# Düzeltme: harfli madde numaraları (24/A)

Devir notundaki bulgu doğrulandı ve düzeltildi.

## Sorun

`MADDE_RE` madde numarasını yalnızca `\d+` olarak eşliyordu. Bu yüzden
`Madde 24/A` biçimindeki başlıklar hiç eşleşmiyor, dolayısıyla yeni bir
madde sınırı olarak görülmüyordu. Sonuç: bu maddelerin metni bir önceki
maddenin `text` alanına karışıyordu.

## Tarama sonucu

7 kanunun tamamı harfli başlık için tarandı. Devir notundaki 3 vaka
dışında başka örnek yok:

| Kanun | Harfli madde | Durum |
|---|---|---|
| 6331 | `MADDE 24/A` | düzeltildi |
| 6331 | `MADDE 25/A` | düzeltildi |
| 4632 | `Madde 20/A` | düzeltildi |
| 4447, 4857, 5174, 5510, 6698 | yok | — |

## Yapılan değişiklik

`scripts/pdf_to_madde_json.py` içinde:

```
- r'\s+(\d+)\s*(?:[–—-]|\()'
+ r'\s+(\d+)\s*(?:/\s*([A-ZÇĞİÖŞÜa-zçğıöşü]))?\s*(?:[–—-]|\()'
```

Harf kısmı opsiyonel. Yakalanırsa `madde_no` "24/A" olur ve
`provision_id` `law:6331:article:24/A` biçiminde üretilir. Harf
büyük harfe normalize edilir.

Tire/parantez zorunluluğu korundu, yani akan metindeki
"...14 üncü maddesi" gibi atıflar hâlâ başlık olarak yakalanmıyor.

## Regresyon testleri

`scripts/test_madde_parser.py` eklendi. 18 test, hepsi geçiyor:

- Normal başlıklar: `MADDE 1 –`, `Madde 4 —`, `Madde 87 (`
- Harfli başlıklar: `MADDE 24/A`, `MADDE 25/A`, `Madde 20/A`
- Ek madde ve geçici madde başlıkları
- Boşluksuz tire (`Geçici Madde 8-`)
- Akan metindeki atıfların başlık sayılmaması
- Değişiklik tablosu kuyruğunun kesilmesi
- Harfli maddenin sade numaralıyla karışmaması
- `provision_id` üretimi (normal / ek / geçici / harfli)

Çalıştırma: `cd scripts && python3 test_madde_parser.py`

## Kaynak

JSON'lar, ilk üretimde kullanılan **özgün mevzuat.gov.tr PDF'lerinden**
yeniden üretildi. Kaynak değiştirilmedi, Bedesten metni kullanılmadı.
Dosya adları: `1.5.4447.pdf`, `1.5.4632.pdf`, `1.5.4857.pdf`,
`1.5.5174.pdf`, `1.5.5510.pdf`, `1.5.6331.pdf`, `1.5.6698.pdf`.

## Etki (diff özeti)

| Dosya | Yeni kayıt | Metni değişen | Silinen |
|---|---|---|---|
| 6331_isg_kanunu.json | `article:24/A`, `article:25/A` | `article:24`, `article:25` | yok |
| 4632_bireysel_emeklilik.json | `article:20/A` | `article:20` | yok |
| 4447, 4857, 5174, 5510, 6698 | — | — | — |

Toplam: 3 yeni kayıt, 3 maddenin metni (ve hash'i) değişti, silinen yok.

Madde sayıları: 6331 50 → 52, 4632 35 → 36. Diğer beş dosya
bit düzeyinde aynı, `current_version_id` dahil hiçbir alan değişmedi.

## Metin bütünlüğü doğrulaması

Bölünen üç maddede eski metin ile yeni iki parçanın toplamı karşılaştırıldı
(boşluklar normalize edilerek):

| Madde | Eski | Yeni ana | Yeni harfli | Sonuç |
|---|---:|---:|---:|---|
| 6331 m.24 | 2202 | 618 | 1582 | korundu |
| 6331 m.25 | 3395 | 2887 | 506 | korundu |
| 4632 m.20 | 2193 | 477 | 1714 | korundu |

Metin kaybı yok, çift sayım yok. Aradaki 2 karakterlik fark yalnızca
birleşme noktasındaki boşluktur.

## Veritabanına yüklenmişse

Etkilenen kayıtlar yalnızca şunlar:

```
GUNCELLE: law:6331:article:24   (metin kısaldı, hash değişti)
GUNCELLE: law:6331:article:25   (metin kısaldı, hash değişti)
GUNCELLE: law:4632:article:20   (metin kısaldı, hash değişti)
EKLE    : law:6331:article:24/A
EKLE    : law:6331:article:25/A
EKLE    : law:4632:article:20/A
```

Silinecek kayıt yok. Diğer 692 madde etkilenmedi, yeniden gömmeye
(re-embedding) gerek yok. Vektör veritabanı kullanılıyorsa sadece
yukarıdaki 6 kaydın yeniden gömülmesi yeterli.
