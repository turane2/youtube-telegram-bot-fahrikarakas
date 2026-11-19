# YouTube → Telegram Bildirim Botu

Bir YouTube kanalına yeni video yüklendiğinde ya da canlı yayın planlanıp başladığında
Telegram grubuna/kanalına otomatik mesaj atar. GitHub Actions üzerinde **ücretsiz** çalışır.

| Ne oldu?                     | Telegram'a giden mesaj                         |
| ---------------------------- | ---------------------------------------------- |
| Yeni video                   | 🎬 Yeni video! + başlık + link + küçük resim    |
| Canlı yayın planlandı        | 📅 Yayın planlandı: 21 Kasım 2026 Cumartesi, 20:00 |
| Canlı yayın başladı          | 🔴 Canlı yayın başladı!                          |
| İlk gösterim (prömiyer) planlandı / başladı | 🎞️ İlk gösterim planlandı: ... / 🎞️ İlk gösterim başladı! |
| Shorts                       | Bildirilmez (istersen açılabilir)              |

**Nasıl çalışır?** Her 5 dakikada bir kanalın RSS akışına bakar (kota harcamaz). Yeni bir şey
varsa YouTube API'ye "bu normal video mu, canlı yayın mı?" diye sorar (çok az kota). Planlanan
yayınları başlayana kadar takip eder. Neyi gönderdiğini `durum.json` dosyasında hatırlar, böylece
aynı bildirimi iki kez atmaz. İlk çalıştırmada eski videoları bildirmez, sadece "gördüm" diye kaydeder.

---

## İçindekiler

1. [Telegram bot token'ı al (BotFather)](#1-telegram-bot-tokenı-al-botfather)
2. [Chat ID'yi bul](#2-chat-idyi-bul)
3. [YouTube API anahtarı al](#3-youtube-api-anahtarı-al)
4. [Kanal ID'sini bul](#4-kanal-idsini-bul)
5. [Bilgisayarında test et](#5-bilgisayarında-test-et)
6. [GitHub Actions'a kur (7/24)](#6-github-actionsa-kur-724)
7. [Ayarları değiştirme](#7-ayarları-değiştirme)
8. [Sorun giderme](#8-sorun-giderme)

---

## 1. Telegram bot token'ı al (BotFather)

1. Telegram'da **@BotFather**'ı aç (mavi tikli olan).
2. `/newbot` yaz.
3. Bota bir görünen ad ver (örnek: `Fahri Karakaş Bildirim`).
4. Bir kullanıcı adı ver. Sonu `bot` ile bitmeli (örnek: `fahrikarakas_bildirim_bot`).
5. BotFather sana şöyle bir **token** verir: `7123456789:AAHk3...`
   Bunu bir kenara kopyala. **Kimseyle paylaşma.** Bu, botun şifresi.

## 2. Chat ID'yi bul

Chat ID, botun mesajı hangi gruba/kanala atacağını söyleyen numaradır.

**Önce botu ekle:**
- **Grup ise:** Botu gruba üye olarak ekle.
- **Kanal ise:** Botu kanala **yönetici** olarak ekle ("Mesaj gönder" yetkisi açık olsun).

**Sonra numarayı bul:**
1. Gruba `/start@botunun_kullanici_adi` yaz. Kanal ise kanala herhangi bir mesaj at.
2. Tarayıcıda şu adresi aç (`TOKEN` yerine kendi token'ını yaz):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
3. Çıkan yazıda `"chat":{"id":-100xxxxxxxxxx` gibi bir kısım göreceksin. Eksi işaretiyle
   birlikte bu sayı senin **Chat ID**'n (gruplar ve kanallar genelde `-100` ile başlar).
   - Boş çıkarsa (`"result":[]`) 1. adımı tekrarla ve sayfayı yenile.

**Test için kendi özel sohbetin (önerilir):** Botuna Telegram'dan özelden `/start` yaz, aynı
`getUpdates` adresini yenile. Orada eksisiz bir numara göreceksin (senin kendi ID'n). Bunu
`TELEGRAM_TEST_CHAT_ID` olarak kullanırsan test mesajları gruba değil sana gelir.

## 3. YouTube API anahtarı al

1. https://console.cloud.google.com adresine Google hesabınla gir.
2. Üstteki proje seçiciden **Yeni Proje** oluştur (ad: `youtube-bot`).
3. Sol menü → **API'ler ve Hizmetler** → **Kitaplık** → `YouTube Data API v3` ara → **Etkinleştir**.
4. **API'ler ve Hizmetler** → **Kimlik Bilgileri** → **Kimlik bilgisi oluştur** → **API anahtarı**.
5. Çıkan anahtarı kopyala.
6. (Önerilir) Anahtarın yanındaki düzenle simgesi → **API kısıtlamaları** → sadece
   `YouTube Data API v3` seç → Kaydet. Böylece anahtar çalınsa bile başka işte kullanılamaz.

Ücretsizdir; kart bilgisi istemez. Günlük kota 10.000 birim, bot günde en fazla birkaç yüz kullanır.

## 4. Kanal ID'sini bul

Kanal ID'si `UC` ile başlayan 24 karakterlik koddur (kanalın `@kullaniciadi` adresi değil).

- Kanalın sayfasını aç → kanal açıklamasına (**...daha fazla**) tıkla → en altta
  **Kanalı paylaş** → **Kanal kimliğini kopyala**.
- Ya da kanal sahibi YouTube Studio → **Ayarlar** → **Kanal** → **Gelişmiş ayarlar** kısmından bakabilir.

## 5. Bilgisayarında test et

Gerçek gruba mesaj atmadan her şeyin çalıştığını burada görürsün.

**Kurulum (bir kez):** Bu klasörde PowerShell aç ve sırayla çalıştır:

```powershell
py -3.11 -m venv .venv
```
```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```
```powershell
Copy-Item .env.example .env
```

Sonra `.env` dosyasını Not Defteri ile aç ve 1-4. adımlarda aldığın bilgileri doldur.

**Test 1: Hiçbir şey göndermeden dene (kuru mod).** Kanaldaki son videoyu bulur ve gidecek mesajı ekrana yazar:
```powershell
.\.venv\Scripts\python bot.py --test --kuru
```

**Test 2: Gerçekten gönder.** Son videoyu "🧪 Test mesajı" etiketiyle bir kez gönderir. Hafızaya dokunmaz.
`TELEGRAM_TEST_CHAT_ID` doluysa sana, boşsa gruba gider.
```powershell
.\.venv\Scripts\python bot.py --test
```

**Test 3: Bir tur gerçek kontrol (isteğe bağlı).** İlk seferde eski videoları kaydeder, hiçbir şey göndermez:
```powershell
.\.venv\Scripts\python bot.py --bir-kez
```

> İstersen botu bilgisayarında sürekli de çalıştırabilirsin (`python bot.py`). Bu durumda
> `KONTROL_ARALIGI_DAKIKA` (varsayılan 3) kadar aralıkla kontrol eder. Bilgisayar kapanınca durur.

## 6. GitHub Actions'a kur (7/24)

### 6.1 Repo oluştur

1. https://github.com adresinde hesap aç / giriş yap.
2. Sağ üstte **+** → **New repository**.
3. Ad: `youtube-telegram-bot`. **Public** seç (aşağıdaki nota bak). Başka hiçbir şeyi işaretleme → **Create repository**.

> **Neden Public?** Gizli (private) repolarda ayda 2.000 dakika ücretsiz sınır var. Bot
> 5 dakikada bir çalışınca ayda ~8.600 çalıştırma eder, sınır aşılır. Public repolarda sınır yok.
> **Endişe etme:** Token ve anahtarlar "Secrets" içinde saklanır, kimse göremez. Repoda sadece kod
> ve herkese açık video ID'leri (`durum.json`) görünür.

### 6.2 Dosyaları yükle

Bu klasörde PowerShell açıp sırayla çalıştır (`KULLANICI` yerine GitHub kullanıcı adını yaz):

```powershell
git init -b main
```
```powershell
git add .
```
```powershell
git status
```

⚠️ `git status` listesinde **`.env` OLMAMALI**. Varsa dur, devam etme.

```powershell
git commit -m "YouTube Telegram botu"
```
```powershell
git remote add origin https://github.com/KULLANICI/youtube-telegram-bot.git
```
```powershell
git push -u origin main
```

### 6.3 Gizli bilgileri ekle (Secrets)

Repo sayfası → **Settings** → sol menü **Secrets and variables** → **Actions** →
**New repository secret**. Şu 5 tanesini tek tek ekle (ad tam olarak böyle olmalı):

| Name                    | Secret (değer)                         |
| ----------------------- | -------------------------------------- |
| `TELEGRAM_BOT_TOKEN`    | BotFather'ın verdiği token             |
| `TELEGRAM_CHAT_ID`      | Grubun/kanalın ID'si (`-100...`)       |
| `YOUTUBE_API_KEY`       | Google'dan aldığın anahtar             |
| `YOUTUBE_CHANNEL_ID`    | `UC...` ile başlayan kanal ID'si       |
| `TELEGRAM_TEST_CHAT_ID` | (isteğe bağlı) kendi özel sohbet ID'n  |

### 6.4 Çalıştır

1. Repo → **Actions** sekmesi. "Workflows aren't being run..." gibi bir uyarı çıkarsa
   **I understand... enable them** düğmesine bas.
2. Soldan **YouTube kontrol** → sağda **Run workflow** → **Test modu** kutusunu işaretle → **Run workflow**.
   Birkaç saniye sonra Telegram'a test mesajı gelmeli. ✅
3. Bir kez daha **Run workflow** de, bu sefer kutuyu **işaretleme**. Bu ilk gerçek çalıştırma:
   eski videoları `durum.json`'a kaydeder, mesaj atmaz.
4. Bitti! Artık bot her 5 dakikada bir kendiliğinden çalışır. Yaptıklarını **Actions** sekmesinde,
   bir çalıştırmaya tıklayıp **Botu çalıştır** adımını açarak Türkçe loglarda görebilirsin.

### GitHub Actions'ın bilmen gereken sınırları

- **Gecikme:** GitHub zamanlanmış işleri yoğunlukta birkaç dakika (bazen 15+ dakika) geciktirebilir.
  Yani bildirim bazen video yüklendikten 5-20 dakika sonra gelir. Canlı yayın genelde uzun
  sürdüğü için yine yakalanır.
- **60 gün kuralı:** Public repolarda 60 gün hiç hareket olmazsa GitHub zamanlamayı durdurur.
  Bot yeni video geldikçe `durum.json`'u kaydettiği için aktif bir kanalda bu sorun olmaz. Olursa
  GitHub e-posta atar. **Actions** sekmesinden tekrar **Enable** demen yeterli.
- **Bu repoda kullanılan çözüm: cron-job.org.** GitHub'ın zamanlayıcısı yeni repoda saatlerce hiç
  çalışmadı. Bu yüzden ücretsiz https://cron-job.org her 2 dakikada bir şu adrese `POST` atıyor:
  `https://api.github.com/repos/turane2/youtube-telegram-bot-fahrikarakas/actions/workflows/youtube-bot.yml/dispatches`
  Header'lar: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
  `Content-Type: application/json`. Body: `{"ref":"main"}`. Başarılı cevap: **204**.
  Token: GitHub → Settings → Developer settings → Fine-grained token, sadece bu repo, sadece
  **Actions: Read and write**. **Token'ın süresi dolunca** yenisini oluşturup cron-job.org'daki
  `Authorization` header'ına yapıştır, yoksa bot durur.
- Daha hızlı ve kesin bildirim istersen ileride aynı kod bir VPS'te `python bot.py` ile 3 dakikada bir çalıştırılabilir.

## 7. Ayarları değiştirme

| Ne değiştirmek istiyorsun?          | Nerede?                                                                |
| ----------------------------------- | ---------------------------------------------------------------------- |
| Mesaj yazıları, emojiler            | `mesajlar.py` (açıklamalar içinde)                                     |
| Shorts bildirilsin mi?              | `.github/workflows/youtube-bot.yml` → `SHORTS_BILDIRIMI: "evet"`       |
| Planlı yayın mesajı gitsin mi?      | Aynı dosya → `PLANLI_YAYIN_BILDIRIMI: "hayir"`                         |
| Kontrol aralığı (GitHub)            | Aynı dosya → `cron: "*/5 * * * *"` (5 = dakika, 5'ten az olamaz)       |
| Kontrol aralığı (bilgisayar/VPS)    | `.env` → `KONTROL_ARALIGI_DAKIKA`                                      |

Dosyaları GitHub sitesinde de düzenleyebilirsin: dosyaya tıkla → kalem simgesi → değiştir → **Commit changes**.

## 8. Sorun giderme

| Log'da gördüğün                              | Anlamı / çözüm                                                          |
| -------------------------------------------- | ----------------------------------------------------------------------- |
| `Şu ayarlar eksik: ...`                      | Secret'ın adı yanlış yazılmış ya da eklenmemiş.                         |
| `Telegram token'ı geçersiz (401)`            | Token yanlış kopyalanmış. BotFather'da `/token` ile tekrar al.          |
| `Sohbet bulunamadı`                          | Chat ID yanlış ya da bot gruba/kanala eklenmemiş.                       |
| `Bot bu sohbete yazamıyor (403)`             | Kanalda botu yönetici yap, "mesaj gönder" yetkisi ver.                  |
| `YouTube API anahtarı geçersiz`              | Anahtarı kontrol et; YouTube Data API v3 etkin mi?                      |
| `YouTube API günlük kotası doldu`            | Ertesi gün kendiliğinden düzelir.                                       |
| `RSS akışı bulunamadı (404)`                 | `YOUTUBE_CHANNEL_ID` yanlış. `UC...` ile başlayan ID olmalı.            |
| `RSS akışına ulaşılamadı`                    | Geçici internet/YouTube sorunu; bot sonraki turda kendisi tekrar dener. |
| `Telegram 'çok hızlı gönderiyorsun' (429)`   | Normal; bot bekleyip kendisi tekrar gönderir.                           |

**Her şeyi sıfırlamak istersen:** `durum.json` dosyasını sil. Bot bir sonraki çalıştırmada
ilk kurulum gibi davranır (eski videoları kaydeder, bildirim atmaz).

---

## Dosyalar

| Dosya                              | Görevi                                             |
| ---------------------------------- | -------------------------------------------------- |
| `bot.py`                           | Ana program, karar mantığı                         |
| `youtube.py`                       | RSS okuma, YouTube API, Shorts tespiti             |
| `telegram_api.py`                  | Telegram'a gönderim, 429 ve hata yönetimi          |
| `hafiza.py`                        | `durum.json`: neyin gönderildiğini hatırlar         |
| `mesajlar.py`                      | Mesaj şablonları (düzenlemesi kolay)               |
| `ayarlar.py`                       | `.env` / Secrets okuma ve kontrol                  |
| `.github/workflows/youtube-bot.yml`| GitHub Actions zamanlaması                         |
