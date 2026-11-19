"""
YouTube -> Telegram bildirim botu.

Kullanım:
  python bot.py            Sürekli çalışır, KONTROL_ARALIGI_DAKIKA'da bir kontrol eder (bilgisayar/VPS)
  python bot.py --bir-kez  Tek kontrol yapar ve çıkar (GitHub Actions bunu kullanır)
  python bot.py --test     Son videoyu "test" etiketiyle bir kez gönderir, hafızaya dokunmaz
  python bot.py --duzelt VIDEO_LINKI MESAJ_LINKI
                           Botun gönderdiği bir mesajı güncel şablonla düzenler
  python bot.py --kuru     Telegram'a hiçbir şey göndermez, gönderilecek mesajları ekrana yazar
                           (--bir-kez veya --test ile birlikte kullanılabilir)
"""

import argparse
import html
import logging
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import mesajlar
import telegram_api
import youtube
from ayarlar import AyarHatasi, Ayarlar, yukle
from hafiza import Hafiza

TURKIYE = timezone(timedelta(hours=3))  # Türkiye 2016'dan beri sabit UTC+3
KAYIP_LIMITI = 3                          # planlı yayın API'den 3 tur üst üste kaybolursa bırak
PLANLI_ZAMAN_ASIMI = timedelta(hours=48)  # planlanan saatten 48 saat geçtiyse bırak

log = logging.getLogger("bot")


# ---------------------------------------------------------------- yardımcılar

def loglari_ayarla() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda emoji/Türkçe sorun çıkmasın
    except AttributeError:
        pass
    logging.addLevelName(logging.INFO, "BİLGİ")
    logging.addLevelName(logging.WARNING, "UYARI")
    logging.addLevelName(logging.ERROR, "HATA")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
        stream=sys.stdout,
    )


def zaman_coz(metin: str | None) -> datetime | None:
    if not metin:
        return None
    try:
        return datetime.fromisoformat(metin.replace("Z", "+00:00"))
    except ValueError:
        return None


def turkce_tarih(metin: str | None) -> str:
    z = zaman_coz(metin)
    if not z:
        return "yakında"
    z = z.astimezone(TURKIYE)
    return mesajlar.TARIH_BICIMI.format(
        gun=z.day, ay=mesajlar.AYLAR[z.month - 1], yil=z.year,
        haftanin_gunu=mesajlar.GUNLER[z.weekday()], saat=z.strftime("%H:%M"),
    )


def mesaj_olustur(sablon: str, item: dict) -> str:
    baslik = item.get("snippet", {}).get("title", "(başlıksız)")
    canli = item.get("liveStreamingDetails") or {}
    return sablon.format(
        baslik=html.escape(baslik),
        link=f"https://youtu.be/{item['id']}",
        tarih=turkce_tarih(canli.get("scheduledStartTime")),
    )


class Bildirici:
    def __init__(self, ayar: Ayarlar, kuru: bool, test: bool = False):
        self.ayar, self.kuru, self.test = ayar, kuru, test

    def gonder(self, sablon: str, item: dict) -> bool:
        metin = mesaj_olustur(sablon, item)
        if self.test:
            metin = mesajlar.TEST_ON_EKI + metin
        resim = youtube.kucuk_resim(item)
        if self.kuru:
            log.info("[KURU MOD, gönderilmedi]\n----\n%s\n(resim: %s)\n----", metin, resim)
            return True
        hedef = self.ayar.telegram_chat_id
        if self.test and self.ayar.telegram_test_chat_id:
            hedef = self.ayar.telegram_test_chat_id
        return telegram_api.gonder(self.ayar.telegram_token, hedef, metin, resim)


def baslik(item: dict) -> str:
    return item.get("snippet", {}).get("title", "")


def basladi_sablonu(item: dict) -> str:
    return mesajlar.PROMIYER_BASLADI if youtube.promiyer_mu(item) else mesajlar.CANLI_BASLADI


def tur_adi(item: dict) -> str:
    return "İlk gösterim" if youtube.promiyer_mu(item) else "Canlı yayın"


# ---------------------------------------------------------------- ana mantık

def normal_video_isle(item: dict, ayar: Ayarlar, hafiza: Hafiza, bildirici: Bildirici) -> None:
    vid = item["id"]
    if youtube.shorts_mu(vid, youtube.sure_saniye(item)):
        if not ayar.shorts_bildirim:
            log.info("Shorts atlandı (SHORTS_BILDIRIMI=hayır): %s", baslik(item))
            hafiza.yaz(vid, "shorts", baslik(item))
            return
        sablon, durum = mesajlar.YENI_SHORTS, "shorts"
    else:
        sablon, durum = mesajlar.YENI_VIDEO, "video"

    if bildirici.gonder(sablon, item):
        log.info("🎬 Bildirim gönderildi: %s", baslik(item))
        hafiza.yaz(vid, durum, baslik(item))
    else:
        log.warning("Gönderilemedi, bir sonraki turda tekrar denenecek: %s", baslik(item))


def yeni_video_isle(item: dict, ayar: Ayarlar, hafiza: Hafiza, bildirici: Bildirici) -> None:
    vid, tur = item["id"], youtube.video_turu(item)

    if tur == "planlandi":
        planli = (item.get("liveStreamingDetails") or {}).get("scheduledStartTime")
        if youtube.promiyer_mu(item):
            log.info("🎞️ İlk gösterim takibe alındı (planlandı mesajı gönderilmez): %s", baslik(item))
        elif ayar.planli_bildirim:
            if not bildirici.gonder(mesajlar.YAYIN_PLANLANDI, item):
                log.warning("Planlı yayın bildirimi gönderilemedi, tekrar denenecek: %s", baslik(item))
                return
            log.info("📅 %s planlandı, bildirildi: %s (%s)", tur_adi(item), baslik(item), turkce_tarih(planli))
        else:
            log.info("📅 Planlı yayın takibe alındı (bildirim kapalı): %s", baslik(item))
        hafiza.yaz(vid, "planlandi", baslik(item), planlanan=planli, kayip=0)

    elif tur == "canli":
        if bildirici.gonder(basladi_sablonu(item), item):
            log.info("🔴 %s başladı, bildirildi: %s", tur_adi(item), baslik(item))
            hafiza.yaz(vid, "canli", baslik(item))
        else:
            log.warning("Canlı yayın bildirimi gönderilemedi, tekrar denenecek: %s", baslik(item))

    else:  # 'video' ya da çoktan bitmiş yayın/prömiyer -> artık normal video
        normal_video_isle(item, ayar, hafiza, bildirici)


def takip_isle(vid: str, item: dict | None, ayar: Ayarlar, hafiza: Hafiza, bildirici: Bildirici) -> None:
    kayit = hafiza.videolar[vid]
    ad = kayit.get("baslik", vid)

    if item is None:  # silinmiş ya da gizlenmiş olabilir
        kayip = kayit.get("kayip", 0) + 1
        if kayip >= KAYIP_LIMITI:
            log.info("Planlı yayın artık bulunamıyor, takipten çıkarıldı: %s", ad)
            hafiza.yaz(vid, "iptal")
        else:
            hafiza.yaz(vid, "planlandi", kayip=kayip)
        return

    tur = youtube.video_turu(item)
    if tur == "planlandi":
        planli = (item.get("liveStreamingDetails") or {}).get("scheduledStartTime")
        z = zaman_coz(planli)
        if z and datetime.now(timezone.utc) - z > PLANLI_ZAMAN_ASIMI:
            log.info("Planlanan saatten 48 saat geçti ama yayın başlamadı, takip bırakıldı: %s", ad)
            hafiza.yaz(vid, "iptal")
        else:
            hafiza.yaz(vid, "planlandi", baslik(item), planlanan=planli, kayip=0)
        return

    if tur == "canli":
        if bildirici.gonder(basladi_sablonu(item), item):
            log.info("🔴 %s başladı, bildirildi: %s", tur_adi(item), baslik(item))
            hafiza.yaz(vid, "canli", baslik(item))
        else:
            log.warning("Canlı yayın bildirimi gönderilemedi, tekrar denenecek: %s", baslik(item))
        return

    # Yayın başlayıp biz görmeden bittiyse (ör. kısa prömiyer) en azından video olarak duyur
    log.info("Yayın/prömiyer biz yakalamadan bitmiş, normal video olarak bildiriliyor: %s", baslik(item))
    normal_video_isle(item, ayar, hafiza, bildirici)
    if hafiza.durum(vid) in ("video", "shorts"):
        hafiza.yaz(vid, "bitti")


def ilk_kurulum(rss: list[dict], ayar: Ayarlar, hafiza: Hafiza, kuru: bool) -> None:
    detay = youtube.video_detaylari([v["id"] for v in rss], ayar.youtube_api_key)
    takip = 0
    for v in rss:
        item = detay.get(v["id"])
        tur = youtube.video_turu(item) if item else "erisilemedi"
        if tur == "planlandi":
            takip += 1
            planli = (item.get("liveStreamingDetails") or {}).get("scheduledStartTime")
            hafiza.yaz(v["id"], "planlandi", v["baslik"], planlanan=planli, kayip=0)
        else:
            hafiza.yaz(v["id"], {"yayin_bitti": "bitti"}.get(tur, tur), v["baslik"])
    if not kuru:
        hafiza.kaydet()
    log.info("İlk çalıştırma: %d mevcut video 'görüldü' olarak kaydedildi, bildirim GÖNDERİLMEDİ. "
             "%d planlı yayın takibe alındı. Bundan sonraki yeni videolar bildirilecek.", len(rss), takip)


def bir_tur(ayar: Ayarlar, hafiza: Hafiza, kuru: bool) -> None:
    rss = youtube.rss_videolari(ayar.youtube_kanal_id)
    if not rss:
        log.info("Kanalda hiç video görünmüyor.")
        return

    if hafiza.ilk_calisma:
        ilk_kurulum(rss, ayar, hafiza, kuru)
        return

    yeniler = [v["id"] for v in rss if not hafiza.bilinen(v["id"])]
    takip = [t for t in hafiza.takiptekiler() if t not in yeniler]
    if not yeniler and not takip:
        log.info("Kontrol edildi, yeni bir şey yok.")
        return

    log.info("%d yeni video, %d bekleyen yayın kontrol ediliyor.", len(yeniler), len(takip))
    detay = youtube.video_detaylari(yeniler + takip, ayar.youtube_api_key)
    bildirici = Bildirici(ayar, kuru)

    for vid in reversed(yeniler):  # eskiden yeniye, sırayla duyur
        item = detay.get(vid)
        if item is None:
            log.warning("YouTube bu video hakkında bilgi vermedi (gizli/silinmiş olabilir): %s", vid)
            hafiza.yaz(vid, "erisilemedi")
        else:
            yeni_video_isle(item, ayar, hafiza, bildirici)
        if not kuru:
            hafiza.kaydet()  # her bildirimden sonra kaydet: çökme olursa tekrar gönderilmesin

    for vid in takip:
        takip_isle(vid, detay.get(vid), ayar, hafiza, bildirici)
        if not kuru:
            hafiza.kaydet()


def test_modu(ayar: Ayarlar, kuru: bool) -> int:
    log.info("TEST MODU: son video bir kez gönderilecek, hafızaya dokunulmayacak.")
    rss = youtube.rss_videolari(ayar.youtube_kanal_id)
    if not rss:
        log.error("Kanalda video bulunamadı.")
        return 1
    son = rss[0]
    detay = youtube.video_detaylari([son["id"]], ayar.youtube_api_key)
    item = detay.get(son["id"])
    if not item:
        log.error("Son videonun detayı alınamadı.")
        return 1

    tur = youtube.video_turu(item)
    sablon = {"planlandi": mesajlar.YAYIN_PLANLANDI, "canli": basladi_sablonu(item)}.get(tur)
    if tur == "planlandi" and youtube.promiyer_mu(item):
        sablon = mesajlar.PROMIYER_BASLADI
    if sablon is None:
        sure = youtube.sure_saniye(item)
        sablon = mesajlar.YENI_SHORTS if youtube.shorts_mu(item["id"], sure) else mesajlar.YENI_VIDEO
    log.info("Son video: %s (tür: %s)", baslik(item), tur)

    hedef = "test sohbetine" if ayar.telegram_test_chat_id else "ana sohbete (TELEGRAM_CHAT_ID)"
    if Bildirici(ayar, kuru, test=True).gonder(sablon, item):
        log.info("✅ Test mesajı %s.", "ekrana yazıldı" if kuru else f"{hedef} gönderildi")
        return 0
    log.error("❌ Test mesajı gönderilemedi, yukarıdaki hatalara bak.")
    return 1


def video_id_coz(metin: str) -> str | None:
    """'https://youtu.be/ID', 'watch?v=ID', '/live/ID' ya da düz ID kabul eder."""
    metin = metin.strip()
    m = re.search(r"(?:v=|youtu\.be/|/live/|/shorts/)([A-Za-z0-9_-]{11})", metin)
    if m:
        return m.group(1)
    return metin if re.fullmatch(r"[A-Za-z0-9_-]{11}", metin) else None


def mesaj_id_coz(metin: str) -> int | None:
    """Telegram mesaj linkinden (t.me/c/123/456 ya da t.me/grup/456) ya da düz sayıdan mesaj numarası."""
    sayilar = re.findall(r"\d+", metin.strip().split("?")[0])
    return int(sayilar[-1]) if sayilar else None


def incele_modu(ayar: Ayarlar, videolar: str) -> int:
    """Videoların API'de nasıl göründüğünü loga yazar (sorun ayıklamak için). Hiçbir şey göndermez."""
    import json
    idler = [v for v in (video_id_coz(p) for p in re.split(r"[\s,]+", videolar) if p) if v]
    if not idler:
        log.error("İncelenecek video linki anlaşılamadı: '%s'", videolar)
        return 1
    detay = youtube.video_detaylari(idler, ayar.youtube_api_key)
    for vid in idler:
        item = detay.get(vid)
        if not item:
            log.warning("İNCELEME %s: YouTube bilgi vermedi.", vid)
            continue
        ozet = {
            "baslik": baslik(item),
            "liveBroadcastContent": item["snippet"].get("liveBroadcastContent"),
            "contentDetails": item.get("contentDetails"),
            "status": item.get("status"),
            "liveStreamingDetails": item.get("liveStreamingDetails"),
            "sayfa_isLiveContent": youtube.canli_icerik_mi(vid),
            "bot_tur": youtube.video_turu(item),
            "bot_promiyer_mu": youtube.promiyer_mu(item),
        }
        log.info("İNCELEME %s:\n%s", vid, json.dumps(ozet, ensure_ascii=False, indent=2))
    return 0


def duzelt_modu(ayar: Ayarlar, video: str, mesaj: str, kuru: bool) -> int:
    vid, mid = video_id_coz(video), mesaj_id_coz(mesaj)
    if not vid:
        log.error("Video linki/ID'si anlaşılamadı: '%s'", video)
        return 1
    if not mid:
        log.error("Telegram mesaj linki anlaşılamadı: '%s'. Mesaja sağ tık → 'Mesaj bağlantısını kopyala'.", mesaj)
        return 1
    item = youtube.video_detaylari([vid], ayar.youtube_api_key).get(vid)
    if not item:
        log.error("YouTube bu video hakkında bilgi vermedi: %s", vid)
        return 1

    if youtube.promiyer_mu(item):
        sablon = mesajlar.PROMIYER_BASLADI
    elif item.get("liveStreamingDetails"):
        sablon = mesajlar.CANLI_BASLADI
    else:
        sablon = mesajlar.YENI_VIDEO
    metin = mesaj_olustur(sablon, item)
    log.info("DÜZELTME: %d numaralı mesaj yeni haliyle değiştirilecek (%s).", mid, baslik(item))
    if kuru:
        log.info("[KURU MOD, düzenlenmedi]\n----\n%s\n----", metin)
        return 0
    if telegram_api.duzenle(ayar.telegram_token, ayar.telegram_chat_id, mid, metin):
        log.info("✅ Mesaj düzeltildi.")
        return 0
    log.error("❌ Mesaj düzeltilemedi. Link doğru mu, mesajı bu bot mu göndermişti?")
    return 1


# ---------------------------------------------------------------- giriş noktası

def main() -> int:
    loglari_ayarla()
    p = argparse.ArgumentParser(description="YouTube -> Telegram bildirim botu")
    p.add_argument("--bir-kez", action="store_true", help="tek kontrol yap ve çık")
    p.add_argument("--test", action="store_true", help="son videoyu test olarak gönder")
    p.add_argument("--kuru", action="store_true", help="Telegram'a gönderme, ekrana yaz")
    p.add_argument("--duzelt", nargs=2, metavar=("VIDEO", "MESAJ"),
                   help="gönderilmiş mesajı yeni şablonla düzelt (video linki + Telegram mesaj linki)")
    arg = p.parse_args()

    try:
        ayar = yukle(telegram_gerekli=not arg.kuru)
    except AyarHatasi as e:
        log.error("%s", e)
        return 2

    if arg.duzelt:
        try:
            if not arg.duzelt[1].strip():  # mesaj linki boş: sadece incele
                return incele_modu(ayar, arg.duzelt[0])
            return duzelt_modu(ayar, arg.duzelt[0], arg.duzelt[1], arg.kuru)
        except youtube.YouTubeHatasi as e:
            log.error("%s", e)
            return 1

    if arg.test:
        try:
            return test_modu(ayar, arg.kuru)
        except youtube.YouTubeHatasi as e:
            log.error("%s", e)
            return 1

    if arg.bir_kez:
        try:
            bir_tur(ayar, Hafiza(ayar.durum_dosyasi), arg.kuru)
        except youtube.YouTubeHatasi as e:
            # Geçici hata: GitHub'da kırmızı hata e-postası yağmasın, sonraki çalıştırma tekrar dener
            log.error("%s Bir sonraki çalıştırmada tekrar denenecek.", e)
        except Exception:
            log.exception("Beklenmeyen hata. Bir sonraki çalıştırmada tekrar denenecek.")
            return 1
        return 0

    log.info("Bot başladı. Her %g dakikada bir kontrol edilecek. Durdurmak için Ctrl+C.",
             ayar.kontrol_araligi_dk)
    hafiza = Hafiza(ayar.durum_dosyasi)
    try:
        while True:
            try:
                bir_tur(ayar, hafiza, arg.kuru)
            except youtube.YouTubeHatasi as e:
                log.error("%s Bir sonraki turda tekrar denenecek.", e)
            except Exception:
                log.exception("Beklenmeyen hata, bot çalışmaya devam ediyor.")
                hafiza = Hafiza(ayar.durum_dosyasi)  # hafızayı diskten temiz yükle
            time.sleep(ayar.kontrol_araligi_dk * 60)
    except KeyboardInterrupt:
        log.info("Bot durduruldu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
