# Üçüncü Taraf Bildirimleri

Bu uygulama üçüncü taraf yazılım bileşenleri kullanır.

## PyQt5 / Qt

- Bu uygulama masaüstü arayüz katmanında `PyQt5` ve `Qt` kullanır.
- `PyQt5`, Riverbank Computing tarafından `GPL` veya ticari lisans modeliyle sunulan bir üçüncü taraf kütüphanedir.
- Proje kapsamında geliştirilen uygulama kodu ile kullanılan `PyQt5 / Qt` bileşenleri aynı şey değildir.
- `Qt` çerçevesine ilişkin lisans ve belge bağlantıları aşağıdadır:
  - PyQt ticari lisans ve GPL bilgisi: https://riverbankcomputing.com/commercial/
  - PyQt5 PyPI paketi: https://pypi.org/project/PyQt5/
  - Qt lisanslama: https://doc.qt.io/qt-5/licensing.html
  - Qt belgeleri: https://doc.qt.io/qt-5/

## Yerel Lisans Dosyaları

- `LICENSE`
  - Bu dağıtıma eklenmiş GNU General Public License v3 lisans metnidir.

## Birlikte Çalışabilirlik Notları

- Bu projede kullanılan `PyQt5`, masaüstü arayüzünün oluşturulması için bağımlılık olarak kullanılır.
- Uygulamanın zamanaşımı hesaplama mantığı, arayüz düzeni ve yardımcı bileşenleri proje kapsamında geliştirilmiş uygulama kodudur.
- Projenin dağıtımı değerlendirilirken hem proje lisansı hem de kullanılan `PyQt5 / Qt` bileşenlerinin ilgili lisans koşulları birlikte dikkate alınmalıdır.

## Gömülü Üçüncü Taraf Kaynak Kod Bulunmaması

- Bu notun hazırlandığı tarih itibarıyla depoya kopyalanmış ayrı bir `PyQt5` veya `Qt` kaynak kodu eklenmemiştir.
- İleride projeye kopyalanmış ya da uyarlanmış üçüncü taraf kaynak kod eklenirse, ilgili kaynak ve lisans bilgisi bu dosyaya ayrıca yazılmalıdır.
