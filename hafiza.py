"""
Botun hafızası: hangi videoyu gördü, hangisini bildirdi, hangi yayını bekliyor.
durum.json dosyasında tutulur (GitHub Actions bu dosyayı repoya kaydeder).
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("hafiza")

EN_FAZLA_KAYIT = 300  # RSS zaten son 15 videoyu gösteriyor; 300 fazlasıyla yeterli

# Bir video için olası durumlar:
#   video, shorts, canli, bitti   -> işi bitti
#   planlandi                     -> yayın bekleniyor, her turda kontrol edilir
#   iptal, erisilemedi            -> bırakıldı


class Hafiza:
    def __init__(self, yol: Path):
        self.yol = yol
        self.ilk_calisma = False
        self.veri: dict = {"videolar": {}}

        if not yol.exists():
            self.ilk_calisma = True
            return
        try:
            self.veri = json.loads(yol.read_text(encoding="utf-8"))
            self.veri.setdefault("videolar", {})
        except (ValueError, OSError) as e:
            yedek = yol.with_suffix(".json.bozuk")
            log.error("Hafıza dosyası okunamadı (%s). Yedeklendi: %s. "
                      "Güvenlik için ilk çalıştırma gibi davranılacak (eski videolar bildirilmez).", e, yedek.name)
            try:
                yol.replace(yedek)
            except OSError:
                pass
            self.ilk_calisma = True
            self.veri = {"videolar": {}}

    @property
    def videolar(self) -> dict:
        return self.veri["videolar"]

    def bilinen(self, vid: str) -> bool:
        return vid in self.videolar

    def durum(self, vid: str) -> str | None:
        return self.videolar.get(vid, {}).get("durum")

    def yaz(self, vid: str, durum: str, baslik: str | None = None, **ek) -> None:
        kayit = self.videolar.setdefault(vid, {
            "eklendi": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        kayit["durum"] = durum
        if baslik is not None:
            kayit["baslik"] = baslik
        kayit.update(ek)

    def takiptekiler(self) -> list[str]:
        return [vid for vid, k in self.videolar.items() if k.get("durum") == "planlandi"]

    def kaydet(self) -> None:
        # Çok eskileri temizle (bekleyen yayınlara dokunma)
        if len(self.videolar) > EN_FAZLA_KAYIT:
            sirali = sorted(self.videolar.items(), key=lambda x: x[1].get("eklendi", ""))
            fazla = len(self.videolar) - EN_FAZLA_KAYIT
            for vid, k in sirali:
                if fazla <= 0:
                    break
                if k.get("durum") != "planlandi":
                    del self.videolar[vid]
                    fazla -= 1

        gecici = self.yol.with_suffix(".tmp")
        gecici.write_text(
            json.dumps(self.veri, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(gecici, self.yol)  # yarım yazılmış dosya kalmasın
        self.ilk_calisma = False
