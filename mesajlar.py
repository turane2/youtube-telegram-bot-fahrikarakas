"""
Mesaj şablonları. Telegram'a giden yazıları buradan değiştirebilirsin.

Kurallar:
- {baslik}, {link}, {tarih} gibi süslü parantezli yerleri SİLME; bot bunları doldurur.
- <b>kalın</b>, <i>italik</i> gibi basit HTML etiketleri kullanabilirsin.
- Yeni satır için \n yaz.
"""

# Normal video yüklendiğinde
YENI_VIDEO = (
    "🎬 <b>Yeni video!</b>\n"
    "\n"
    "{baslik}\n"
    "\n"
    "▶️ İzle: {link}"
)

# Canlı yayın planlandığında (henüz başlamadı)
YAYIN_PLANLANDI = (
    "📅 <b>Yayın planlandı:</b> {tarih}\n"
    "\n"
    "{baslik}\n"
    "\n"
    "🔔 Hatırlatıcı kur: {link}"
)

# Canlı yayın başladığında
CANLI_BASLADI = (
    "🔴 <b>Canlı yayın başladı!</b>\n"
    "\n"
    "{baslik}\n"
    "\n"
    "📺 Hemen katıl: {link}"
)

# İlk gösterim (prömiyer) planlandığında
PROMIYER_PLANLANDI = (
    "🎞️ <b>İlk gösterim planlandı:</b> {tarih}\n"
    "\n"
    "{baslik}\n"
    "\n"
    "🔔 Hatırlatıcı kur: {link}"
)

# İlk gösterim (prömiyer) başladığında
PROMIYER_BASLADI = (
    "🎞️ <b>İlk gösterim başladı!</b>\n"
    "\n"
    "{baslik}\n"
    "\n"
    "▶️ Birlikte izleyelim: {link}"
)

# Shorts (sadece SHORTS_BILDIRIMI=evet ise kullanılır)
YENI_SHORTS = (
    "📱 <b>Yeni Shorts!</b>\n"
    "\n"
    "{baslik}\n"
    "\n"
    "▶️ {link}"
)

# Test modunda mesajın başına eklenir
TEST_ON_EKI = "🧪 <i>Test mesajı, dikkate almayın</i>\n\n"

# Tarih yazımı için Türkçe adlar
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Örnek çıktı: "21 Kasım 2026 Cumartesi, 20:00"
TARIH_BICIMI = "{gun} {ay} {yil} {haftanin_gunu}, {saat}"
