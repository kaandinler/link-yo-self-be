"""Diske yazan depo."""

import os
import pathlib
import tempfile

from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from core.storage.base import Depo


class YerelDepo(Depo):
    def __init__(self, kok_dizin: str, kok_adres: str):
        self.kok_dizin = pathlib.Path(kok_dizin).resolve()
        self.kok_adres = kok_adres.rstrip("/")

    def _yol(self, anahtar: str) -> pathlib.Path:
        yol = (self.kok_dizin / anahtar).resolve()
        # Anahtarlar zaten kalipla sinirli (bkz. base.avatar_anahtari_mi);
        # bu ikinci kat, kalip bir gun gevserse diye.
        if not yol.is_relative_to(self.kok_dizin):
            raise ValueError(f"Depo disinda bir yol: {anahtar}")
        return yol

    async def kaydet(self, anahtar: str, veri: bytes, icerik_turu: str) -> str:
        await run_in_threadpool(self._yaz, self._yol(anahtar), veri)
        return self.adres(anahtar)

    @staticmethod
    def _yaz(yol: pathlib.Path, veri: bytes) -> None:
        yol.parent.mkdir(parents=True, exist_ok=True)
        # Once gecici dosya, sonra yeniden adlandirma: yazma yarida
        # kalirsa (disk doldu, surec oldu) sunulan adreste yarim bir
        # dosya durmuyor.
        fd, gecici = tempfile.mkstemp(dir=yol.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as dosya:
                dosya.write(veri)
            os.replace(gecici, yol)
        except BaseException:
            pathlib.Path(gecici).unlink(missing_ok=True)
            raise

    async def sil(self, anahtar: str) -> None:
        await run_in_threadpool(self._yol(anahtar).unlink, missing_ok=True)


class MedyaDosyalari(StaticFiles):
    """YerelDepo'nun dosyalarini sunar.

    StaticFiles'tan tek farki iki baslik:

    - Cache-Control immutable: her yuklemede ad degisiyor (bkz.
      base.avatar_anahtari), yani bir adresin icerigi hic degismiyor.
    - X-Content-Type-Options nosniff: dosyalar kullanicidan geliyor;
      tarayici uzantiya gore verilen turu (image/jpeg, image/png) tahminle
      degistirmesin. Sunucu zaten yeniden kodluyor, bu ikinci kat.
    """

    async def get_response(self, path: str, scope: Scope):
        yanit = await super().get_response(path, scope)
        if yanit.status_code == 200:
            yanit.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        yanit.headers["X-Content-Type-Options"] = "nosniff"
        return yanit
