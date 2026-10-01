"""Hiz sinirinin ayaga kalkarken yazdigi rapor.

NEDEN: iki yanlis yapilandirma SESSIZDI. Olculdu, uvicorn
WEB_CONCURRENCY=2 ile ayaga kaldirildiginda:

  - REDIS_URL yok: log'da hiz sinirina dair tek satir yok, oysa gercek
    sinir iki katina cikmis durumda.
  - REDIS_URL yanlis (kapali port): yine tek satir yok; ilk uyari ancak
    biri giris yapmaya calistiginda.

Ikisi de ancak bir saldiri sirasinda fark edilecek seylerdi.

Redis'e ULASILABILEN durum test_rate_limit_redis.py'de (gercek Redis
istiyor).
"""

import logging

import pytest

import main
from core.rate_limit.limiter import HizSiniri, isci_sayisi
from settings import settings

LOGGER = "core.rate_limit.limiter"

# Hicbir seyin dinlemedigi port: baglanti aninda reddediliyor.
KAPALI_REDIS = "redis://127.0.0.1:1/0"


class TestIsciSayisi:
    @pytest.mark.parametrize(
        ("ortam", "beklenen"),
        [
            ({"WEB_CONCURRENCY": "4"}, 4),
            ({}, 1),
            # Yalnizca bir rapor: anlamsiz deger ayaga kalkmayi bozmamali.
            ({"WEB_CONCURRENCY": "abc"}, 1),
            ({"WEB_CONCURRENCY": "0"}, 1),
            ({"WEB_CONCURRENCY": "-3"}, 1),
        ],
    )
    def test_web_concurrency_okunuyor(self, ortam, beklenen):
        assert isci_sayisi(ortam) == beklenen


class TestRapor:
    async def test_birden_fazla_isci_ve_redis_yok_uyariyor(self, caplog):
        h = HizSiniri(None)
        with caplog.at_level(logging.INFO, logger=LOGGER):
            await h.baslangic_raporu(isci_sayisi=4)

        uyarilar = [k for k in caplog.records if k.levelno == logging.WARNING]
        assert len(uyarilar) == 1
        assert "4 isci" in uyarilar[0].getMessage()
        assert "REDIS_URL" in uyarilar[0].getMessage()

    async def test_tek_isci_ve_redis_yok_uyarmiyor(self, caplog):
        """Tek isci icin bellek deposu DOGRU secim; her acilista uyari
        basmak, uyarilarin okunmamasini ogretirdi."""
        h = HizSiniri(None)
        with caplog.at_level(logging.INFO, logger=LOGGER):
            await h.baslangic_raporu(isci_sayisi=1)

        assert [k.levelno for k in caplog.records] == [logging.INFO]
        assert "bellek" in caplog.records[0].getMessage()

    async def test_redis_verilmis_ama_ulasilamiyor_hata(self, caplog):
        h = HizSiniri(KAPALI_REDIS)
        with caplog.at_level(logging.INFO, logger=LOGGER):
            await h.baslangic_raporu(isci_sayisi=4)
        await h.kapat()

        hatalar = [k for k in caplog.records if k.levelno == logging.ERROR]
        assert len(hatalar) == 1
        assert "ulasilamiyor" in hatalar[0].getMessage()

    async def test_redis_ulasilamiyorsa_da_sinirlar_isliyor(self, caplog):
        """Rapor ayaga kalkmayi engellemiyor ve sonrasinda sinirlayici
        bellege dusup calismaya devam ediyor."""
        h = HizSiniri(KAPALI_REDIS)
        with caplog.at_level(logging.INFO, logger=LOGGER):
            await h.baslangic_raporu(isci_sayisi=1)
            kararlar = [await h.dene("k", limit=2, pencere_sn=60) for _ in range(3)]
        await h.kapat()

        assert [k.izinli for k in kararlar] == [True, True, False]


class TestLifespan:
    """Rapor uygulamanin ayaga kalkisina gercekten bagli mi?"""

    async def test_acilista_rapor_yaziliyor(self, caplog, monkeypatch):
        monkeypatch.setenv("WEB_CONCURRENCY", "3")
        monkeypatch.setattr(main, "hiz_siniri", HizSiniri(None))

        with caplog.at_level(logging.INFO, logger=LOGGER):
            async with main.lifespan(main.app):
                pass

        assert "3 isci" in caplog.text

    async def test_sinir_kapaliysa_acilista_uyariyor(self, caplog, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        monkeypatch.setattr(main, "hiz_siniri", HizSiniri(None))

        with caplog.at_level(logging.INFO):
            async with main.lifespan(main.app):
                pass

        uyarilar = [
            k.getMessage() for k in caplog.records if k.levelno == logging.WARNING
        ]
        assert any("KAPALI" in m for m in uyarilar)
