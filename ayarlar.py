"""Ayarları .env dosyasından (ya da GitHub Secrets'tan) okur."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

KLASOR = Path(__file__).resolve().parent

# .env varsa yükle. Ortamda zaten tanımlı değişkenleri ezmez (GitHub Actions için önemli).
load_dotenv(KLASOR / ".env")


class AyarHatasi(Exception):
    pass


def _oku(ad: str, varsayilan: str = "") -> str:
    return (os.getenv(ad) or varsayilan).strip()


def _evet_mi(ad: str, varsayilan: str) -> bool:
    return _oku(ad, varsayilan).lower() in ("evet", "e", "true", "1", "yes", "acik", "açık")


@dataclass
class Ayarlar:
    telegram_token: str
    telegram_chat_id: str
    telegram_test_chat_id: str
    youtube_api_key: str
    youtube_kanal_id: str
    kontrol_araligi_dk: float
    planli_bildirim: bool
    shorts_bildirim: bool
    durum_dosyasi: Path


def yukle(telegram_gerekli: bool = True) -> Ayarlar:
    eksik = []
    zorunlu = ["YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID"]
    if telegram_gerekli:
        zorunlu += ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    for ad in zorunlu:
        if not _oku(ad):
            eksik.append(ad)
    if eksik:
        raise AyarHatasi(
            "Şu ayarlar eksik: " + ", ".join(eksik)
            + ". .env dosyasını (ya da GitHub Secrets'ı) kontrol et."
        )

    kanal = _oku("YOUTUBE_CHANNEL_ID")
    if not (kanal.startswith("UC") and len(kanal) == 24):
        raise AyarHatasi(
            f"YOUTUBE_CHANNEL_ID hatalı görünüyor ('{kanal}'). "
            "Kanal ID'si 'UC' ile başlar ve 24 karakterdir. README'deki 'Kanal ID'si bulma' adımına bak."
        )

    try:
        aralik = float(_oku("KONTROL_ARALIGI_DAKIKA", "3").replace(",", "."))
        if aralik < 1:
            raise ValueError
    except ValueError:
        raise AyarHatasi("KONTROL_ARALIGI_DAKIKA en az 1 olan bir sayı olmalı (örnek: 3).")

    durum = Path(_oku("DURUM_DOSYASI", "durum.json"))
    if not durum.is_absolute():
        durum = KLASOR / durum

    return Ayarlar(
        telegram_token=_oku("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_oku("TELEGRAM_CHAT_ID"),
        telegram_test_chat_id=_oku("TELEGRAM_TEST_CHAT_ID"),
        youtube_api_key=_oku("YOUTUBE_API_KEY"),
        youtube_kanal_id=kanal,
        kontrol_araligi_dk=aralik,
        planli_bildirim=_evet_mi("PLANLI_YAYIN_BILDIRIMI", "evet"),
        shorts_bildirim=_evet_mi("SHORTS_BILDIRIMI", "hayir"),
        durum_dosyasi=durum,
    )
