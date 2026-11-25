"""YouTube tarafı: RSS akışı (kotasız) ve videos.list (1 kota birimi / istek)."""

import logging
import re

import feedparser
import requests

log = logging.getLogger("youtube")

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
PLAYLIST_RSS_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={}"
API_URL = "https://www.googleapis.com/youtube/v3/videos"
ZAMAN_ASIMI = 20
TARAYICI = {"User-Agent": "Mozilla/5.0 (YouTube-Telegram-Bildirim-Botu)"}


class YouTubeHatasi(Exception):
    """Geçici olabilecek YouTube hatası; bot bir sonraki turda tekrar dener."""


def _gizle(metin: str) -> str:
    """Hata mesajlarında API anahtarı görünmesin."""
    return re.sub(r"key=[^&\s'\"]+", "key=***", str(metin))


def uye_rss_videolari(kanal_id: str) -> list[dict]:
    """
    Üyelere özel içerikler (video + canlı yayın) kanalın normal RSS akışında çıkmaz.
    YouTube bunları kanal başına otomatik tutulan "UUMO..." listesinde toplar; o listenin RSS'i okunur.
    Hata olursa ana akışı bozmamak için boş liste döner.
    """
    url = PLAYLIST_RSS_URL.format("UUMO" + kanal_id[2:])
    try:
        return _akis_oku(url, "Üyelere özel akış")
    except YouTubeHatasi as e:
        log.warning("%s Bu turda üyelere özel içerik kontrol edilemedi.", e)
        return []


def rss_videolari(kanal_id: str) -> list[dict]:
    """Kanalın son ~15 videosu, en yeniden eskiye: [{'id':..., 'baslik':...}]"""
    return _akis_oku(RSS_URL.format(kanal_id), "RSS akışı")


def _akis_oku(url: str, ad: str) -> list[dict]:
    try:
        r = requests.get(url, headers=TARAYICI, timeout=ZAMAN_ASIMI)
    except requests.RequestException as e:
        raise YouTubeHatasi(f"{ad} okunamadı (internet sorunu olabilir): {e}") from None
    if r.status_code == 404:
        raise YouTubeHatasi(f"{ad} bulunamadı (404). YOUTUBE_CHANNEL_ID doğru mu?")
    if r.status_code != 200:
        raise YouTubeHatasi(f"{ad} hata verdi (HTTP {r.status_code}).")

    akis = feedparser.parse(r.content)
    if akis.bozo and not akis.entries:
        raise YouTubeHatasi(f"{ad} okunamadı (bozuk veri geldi).")

    videolar = []
    for e in akis.entries:
        vid = e.get("yt_videoid")
        if vid:
            videolar.append({"id": vid, "baslik": e.get("title", "")})
    return videolar


def video_detaylari(idler: list[str], api_key: str) -> dict[str, dict]:
    """videos.list ile detayları çeker. 50'şerli gruplar, her grup 1 kota birimi."""
    sonuc: dict[str, dict] = {}
    for i in range(0, len(idler), 50):
        grup = idler[i:i + 50]
        params = {
            "part": "snippet,liveStreamingDetails,contentDetails,status",
            "id": ",".join(grup),
            "key": api_key,
        }
        try:
            r = requests.get(API_URL, params=params, timeout=ZAMAN_ASIMI)
        except requests.RequestException as e:
            raise YouTubeHatasi(f"YouTube API'ye ulaşılamadı: {_gizle(e)}") from None

        if r.status_code != 200:
            sebep = ""
            try:
                hata = r.json().get("error", {})
                sebep = (hata.get("errors") or [{}])[0].get("reason", "") or hata.get("message", "")
            except ValueError:
                pass
            if sebep == "quotaExceeded":
                raise YouTubeHatasi("YouTube API günlük kotası doldu. Gece yarısı (Pasifik saati) sıfırlanır.")
            if sebep in ("keyInvalid", "badRequest") or r.status_code == 400:
                raise YouTubeHatasi(f"YouTube API anahtarı geçersiz görünüyor ({sebep}). YOUTUBE_API_KEY'i kontrol et.")
            if r.status_code == 403:
                raise YouTubeHatasi(
                    f"YouTube API erişimi reddedildi ({sebep}). "
                    "Google Cloud'da 'YouTube Data API v3' etkin mi, anahtarın kısıtlamaları doğru mu?"
                )
            raise YouTubeHatasi(f"YouTube API hata verdi (HTTP {r.status_code}, {sebep}).")

        for item in r.json().get("items", []):
            sonuc[item["id"]] = item
    return sonuc


def video_turu(item: dict) -> str:
    """
    'planlandi'   -> canlı yayın/prömiyer planlanmış, henüz başlamadı
    'canli'       -> şu an canlı
    'yayin_bitti' -> canlı yayındı ama bitmiş (artık kayıt)
    'video'       -> normal video
    """
    durum = item.get("snippet", {}).get("liveBroadcastContent", "none")
    canli = item.get("liveStreamingDetails") or {}
    if durum == "upcoming":
        return "planlandi"
    if durum == "live":
        return "canli"
    if canli.get("actualStartTime"):
        return "yayin_bitti"
    return "video"


def sure_saniye(item: dict) -> int | None:
    """ISO 8601 süreyi (PT1H2M3S) saniyeye çevirir."""
    sure = item.get("contentDetails", {}).get("duration", "")
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", sure)
    if not m or not sure or sure in ("P0D", "PT0S"):
        return None
    g, s, d, sn = (int(x or 0) for x in m.groups())
    return g * 86400 + s * 3600 + d * 60 + sn


def promiyer_mu(item: dict) -> bool:
    """
    İlk gösterim (prömiyer) mi, gerçek canlı yayın mı? (Sadece planlı/canlı durumdayken güvenilir.)
    API'de ölçülen fark (19.11.2026): prömiyer önceden yüklenip işlenmiş bir videodur, status.uploadStatus
    "processed" olur ve süre alanı gelmez. Gerçek canlı yayında "uploaded" olur ve süre "P0D".
    (Video sayfasındaki isLiveContent daha kesin ama GitHub sunucularından okunamıyor.)
    """
    if not item.get("liveStreamingDetails"):
        return False
    if item.get("snippet", {}).get("liveBroadcastContent") not in ("upcoming", "live"):
        return False  # bittikten sonra ikisi de "processed" olur, ayırt edilemez
    durum = item.get("status", {}).get("uploadStatus")
    if durum:
        return durum == "processed"
    return "duration" not in item.get("contentDetails", {})


def shorts_mu(video_id: str, sure: int | None) -> bool:
    """
    API'de 'Shorts' alanı yok. youtube.com/shorts/ID adresi Shorts için açılır (200),
    normal videoda başka adrese yönlendirir (3xx). 3 dakikadan uzunsa zaten Shorts değildir.
    """
    if sure is not None and sure > 180:
        return False
    try:
        r = requests.head(
            f"https://www.youtube.com/shorts/{video_id}",
            headers=TARAYICI, allow_redirects=False, timeout=10,
        )
        if r.status_code == 200:
            return True
        if 300 <= r.status_code < 400:
            return False
    except requests.RequestException:
        pass
    # Emin olunamadı: 1 dakika ve altıysa Shorts say
    return sure is not None and sure <= 60


def kucuk_resim(item: dict) -> str | None:
    resimler = item.get("snippet", {}).get("thumbnails", {})
    for boyut in ("maxres", "standard", "high", "medium", "default"):
        if boyut in resimler:
            return resimler[boyut]["url"]
    return None
