"""CORS ve Host listelerinin bos birakilinca ne yaptigi.

Onceki hal `settings.allowed_origins or ["*"]` idi ve hemen altinda
allow_credentials=True duruyordu. Starlette bu ikisini birlikte gorunce
yanita `*` yazmiyor, istegin origin'ini yansitiyor -- yani liste bos
birakilinca API her siteye aciliyordu, hicbir uyari cikmadan.

Bu dosya iki seyi olcuyor:
  1. Uretimde bos liste uygulamayi baslatmiyor (fail-closed).
  2. Tanimli liste gercekten kisitliyor; yabanci origin yansitilmiyor.
"""
import pytest

import main
from main import cors_kaynaklari, guvenilir_adresler
from settings import settings


@pytest.fixture
def ayarlar(monkeypatch):
    """Ayarlari test icinde degistirip sonunda geri alir."""

    def kur(**degerler):
        for alan, deger in degerler.items():
            monkeypatch.setattr(settings, alan, deger)

    return kur


class TestCorsKaynaklari:
    def test_uretimde_bos_liste_baslatmiyor(self, ayarlar):
        """Sessizce acik olmaktansa acikca baslamamak.

        Bu test dusserse, ALLOWED_ORIGINS'i unutan bir dagitim yine
        sessizce herkese acik hale gelir.
        """
        ayarlar(environment="production", allowed_origins=None)

        with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
            cors_kaynaklari()

    def test_uretimde_bos_listeyle_uygulama_kurulmuyor(self, ayarlar):
        """Yalnizca yardimci degil, create_app() da durmali."""
        ayarlar(environment="production", allowed_origins=None, allowed_hosts=["x"])

        with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
            main.create_app()

    def test_uretimde_tanimli_liste_oldugu_gibi_donuyor(self, ayarlar):
        ayarlar(
            environment="production",
            allowed_origins=["https://linkyoself.com"],
        )

        assert cors_kaynaklari() == ["https://linkyoself.com"]

    def test_gelistirmede_frontend_adresi_kullaniliyor(self, ayarlar):
        """Gelistirmede de `*` yok: iki ortam ayni sekle sahip olmali."""
        ayarlar(
            environment="development",
            allowed_origins=None,
            frontend_url="http://localhost:3000",
        )

        assert cors_kaynaklari() == ["http://localhost:3000"]

    def test_hicbir_durumda_yildiz_donmuyor(self, ayarlar):
        """`*` + allow_credentials=True bir arada anlamli degil.

        O ikisi birlikteyken Starlette origin'i yansitiyor, yani liste
        hicbir seyi kisitlamiyor.
        """
        ayarlar(
            environment="development",
            allowed_origins=None,
            frontend_url="http://localhost:3000",
        )
        assert "*" not in cors_kaynaklari()

        ayarlar(allowed_origins=["https://a.example", "https://b.example"])
        assert "*" not in cors_kaynaklari()


class TestGuvenilirAdresler:
    def test_bos_liste_hata_veriyor(self, ayarlar):
        """allowed_hosts=None verilince Starlette listeyi ["*"] yapiyordu.

        Yani uretim icin eklenen Host kontrolu hicbir sey yapmiyordu.
        """
        ayarlar(allowed_hosts=None)

        with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
            guvenilir_adresler()

    def test_tanimli_liste_oldugu_gibi_donuyor(self, ayarlar):
        ayarlar(allowed_hosts=["linkyoself.com"])

        assert guvenilir_adresler() == ["linkyoself.com"]


class TestGercekYanitlar:
    """Yardimcilar degil, calisan uygulamanin gonderdigi basliklar."""

    async def test_tanimli_origin_kabul_ediliyor(self, client):
        yanit = await client.request(
            "OPTIONS",
            "/api/v1/profile/me",
            headers={
                "Origin": settings.frontend_url,
                "Access-Control-Request-Method": "GET",
            },
        )

        assert yanit.headers.get("access-control-allow-origin") == (
            settings.frontend_url
        )

    async def test_yabanci_origin_yansitilmiyor(self, client):
        """Asil olcum bu.

        Eski halde bu baslik "https://kotu-site.example" olarak geri
        geliyordu (calisan sunucuda olculdu). Artik ya hic gelmiyor ya
        da izinli adresi gosteriyor -- her iki halde de yabanci origin
        yanitlanmiyor.
        """
        yabanci = "https://kotu-site.example"

        yanit = await client.request(
            "OPTIONS",
            "/api/v1/profile/me",
            headers={
                "Origin": yabanci,
                "Access-Control-Request-Method": "GET",
            },
        )

        assert yanit.headers.get("access-control-allow-origin") != yabanci

    async def test_yabanci_origin_basit_istekte_de_yansitilmiyor(self, client):
        """Preflight disinda, normal bir GET'te de ayni kural.

        CEREZ NEDEN GONDERILIYOR: Starlette, allow_all_origins acikken
        basit bir istege `*` yaziyor ama istekte cerez varsa ORIGIN'I
        YANSITIYOR. Cerezsiz yazilan bir test eski kodda da gecerdi --
        `*` zaten yabanci origin'e esit degil. Ilk yazimda tam olarak
        oyleydi ve yanlis sebeple geciyordu.

        Bu yuzden iki sey birden olculuyor: yansitma yok VE `*` yok.
        Ikisi de allow_credentials=True ile bir arada olmamali.
        """
        yabanci = "https://kotu-site.example"

        yanit = await client.get(
            "/api/v1/p/olmayan-kullanici",
            headers={"Origin": yabanci, "Cookie": "a=b"},
        )

        izin = yanit.headers.get("access-control-allow-origin")
        assert izin != yabanci
        assert izin != "*"
