# ZamanMatik

ZamanMatik, Türk Ceza Kanunu'ndaki dava zamanaşımı sürelerini masaüstünde pratik biçimde hesaplamak için geliştirilen bir `PyQt5` uygulamasıdır.

Uygulama içinde:

- temel zamanaşımı hesaplama akışı
- yaşa göre süre uyarlaması
- zamanaşımının durması hesaplaması
- tekli ve çoklu kesilme tarihleriyle hesaplama
- detaylı sonuç ve açıklama çıktısı

bulunur.

## Kurulum

Temel bağımlılıkları kurun:

```bash
pip install PyQt5 requests
```

## Çalıştırma

Uygulamayı proje klasöründe şu komutla başlatabilirsiniz:

```bash
python main.py
```

## Proje Yapısı

- `main.py`: uygulama giriş noktası
- `ui/`: arayüz bileşenleri ve ana pencere
- `logic/`: zamanaşımı hesaplama mantığı
- `models/`: veri modelleri
- `utils/`: tarih yardımcıları
- `assets/`: simge dosyaları

## Notlar

- Uygulama `PyQt5` ile geliştirilmiştir.
- Hesaplamalar TCK m.66 ve m.67 esas alınarak yardımcı araç niteliğinde yapılır.
- Kullanıcı, çıkan sonucu mutlaka manuel olarak doğrulamalıdır.
- GitHub kaynak kodu: `https://github.com/cezateknik/zmnmtk/tree/main`

## Lisans ve Üçüncü Taraf Notları

- Proje lisansı için:
  - `LICENSE`
- Üçüncü taraf bağımlılık ve lisans notları için:
  - `THIRD_PARTY.md`
- Uygulamanın zamanaşımı hesaplama mantığı ve arayüz kodu proje içinde özgün olarak yazılmıştır.
