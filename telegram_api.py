"""Telegram'a mesaj gönderme. 429 (çok hızlı gönderim) ve ağ hatalarını ele alır."""

import logging
import re
import time

import requests

log = logging.getLogger("telegram")

API = "https://api.telegram.org/bot{token}/{metod}"
EN_FAZLA_DENEME = 4


def _gizle(metin: str) -> str:
    """Hata mesajlarında bot token'ı görünmesin."""
    return re.sub(r"bot\d+:[\w-]+", "bot***", str(metin))


def _istek(token: str, metod: str, veri: dict) -> bool:
    for deneme in range(1, EN_FAZLA_DENEME + 1):
        try:
            r = requests.post(API.format(token=token, metod=metod), json=veri, timeout=30)
        except requests.RequestException as e:
            bekle = 5 * deneme
            log.warning("Telegram'a ulaşılamadı (%s). %d sn sonra tekrar denenecek (%d/%d).",
                        _gizle(e), bekle, deneme, EN_FAZLA_DENEME)
            time.sleep(bekle)
            continue

        try:
            cevap = r.json()
        except ValueError:
            cevap = {}

        if r.status_code == 200 and cevap.get("ok"):
            return True

        if r.status_code == 429:
            bekle = int(cevap.get("parameters", {}).get("retry_after", 30)) + 1
            log.warning("Telegram 'çok hızlı gönderiyorsun' dedi (429). %d sn bekleniyor.", bekle)
            time.sleep(bekle)
            continue

        aciklama = cevap.get("description", f"HTTP {r.status_code}")
        if r.status_code == 401:
            log.error("Telegram token'ı geçersiz (401). TELEGRAM_BOT_TOKEN'ı kontrol et.")
        elif "chat not found" in aciklama.lower():
            log.error("Sohbet bulunamadı. TELEGRAM_CHAT_ID doğru mu, bot gruba/kanala ekli mi?")
        elif r.status_code == 403:
            log.error("Bot bu sohbete yazamıyor (403): %s. Kanalda botu yönetici yap.", aciklama)
        elif r.status_code >= 500:
            log.warning("Telegram sunucu hatası (%s), tekrar denenecek.", aciklama)
            time.sleep(5 * deneme)
            continue
        else:
            log.error("Telegram mesajı reddetti (%s): %s", metod, aciklama)
        return False

    log.error("Telegram'a %d denemede de gönderilemedi.", EN_FAZLA_DENEME)
    return False


def duzenle(token: str, chat_id: str, mesaj_id: int, metin: str) -> bool:
    """Botun daha önce gönderdiği bir mesajın yazısını değiştirir (resimli mesajda resim altı yazısı)."""
    if _istek(token, "editMessageCaption", {
        "chat_id": chat_id, "message_id": mesaj_id, "caption": metin, "parse_mode": "HTML",
    }):
        return True
    log.info("Resim altı yazısı düzenlenemedi, düz metin mesajı olarak deneniyor.")
    return _istek(token, "editMessageText", {
        "chat_id": chat_id, "message_id": mesaj_id, "text": metin, "parse_mode": "HTML",
    })


def gonder(token: str, chat_id: str, metin: str, resim_url: str | None = None) -> bool:
    """Önce küçük resimli göndermeyi dener, olmazsa düz metin (link önizlemeli) gönderir."""
    if resim_url:
        if _istek(token, "sendPhoto", {
            "chat_id": chat_id, "photo": resim_url, "caption": metin, "parse_mode": "HTML",
        }):
            return True
        log.info("Resimli gönderim olmadı, düz metin olarak deneniyor.")
    return _istek(token, "sendMessage", {
        "chat_id": chat_id, "text": metin, "parse_mode": "HTML",
    })
