"""Avatar yukleme ve kaldirma (POST/DELETE /api/v1/profile/avatar)."""

import io
import pathlib

import pytest
from PIL import Image
from sqlalchemy import update

from models import User
from services.user import avatar as avatar_modulu
from settings import settings
from tests.conftest import (
    DEFAULT_USER,
    TEST_MEDIA_ROOT,
    auth_header,
    login,
    register_user,
)

URL = "/api/v1/profile/avatar"


def gorsel(
    boyut=(600, 400), bicim="PNG", renk=(200, 30, 30), exif: bytes | None = None
) -> bytes:
    cikti = io.BytesIO()
    kwargs = {"exif": exif} if exif else {}
    Image.new("RGB", boyut, renk).save(cikti, format=bicim, **kwargs)
    return cikti.getvalue()


def yukle(client, veri: bytes, ad="avatar.png", tur="image/png"):
    return client.post(URL, files={"file": (ad, veri, tur)})


def dosya_yolu(adres: str) -> pathlib.Path:
    return TEST_MEDIA_ROOT / adres.removeprefix("http://test/media/")


async def profil_adresini_yaz(app, username: str, adres: str | None) -> None:
    """Eski serbest alanin biraktigi durumu taklit eder."""
    session_factory = app.container.async_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(User.username == username)
            .values(profile_image_url=adres)
        )
        await session.commit()


class TestYukleme:
    async def test_yuklenen_gorsel_kare_jpeg_olarak_sunuluyor(self, auth_client):
        yanit = await yukle(auth_client, gorsel((600, 400)))
        assert yanit.status_code == 200, yanit.text

        adres = yanit.json()["data"]["profile_image_url"]
        assert adres.startswith("http://test/media/avatars/")
        assert adres.endswith(".jpg")

        sunulan = await auth_client.get(adres.removeprefix("http://test"))
        assert sunulan.status_code == 200
        assert sunulan.headers["content-type"] == "image/jpeg"
        assert sunulan.headers["x-content-type-options"] == "nosniff"
        assert "immutable" in sunulan.headers["cache-control"]

        with Image.open(io.BytesIO(sunulan.content)) as cikti:
            assert cikti.format == "JPEG"
            assert cikti.size == (400, 400)

    async def test_profilde_ve_herkese_acik_sayfada_gorunuyor(self, auth_client):
        adres = (await yukle(auth_client, gorsel())).json()["data"]["profile_image_url"]

        me = await auth_client.get("/api/v1/profile/me")
        assert me.json()["data"]["profile_image_url"] == adres

        herkese_acik = await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")
        assert herkese_acik.json()["data"]["profile_image_url"] == adres

    async def test_kucuk_gorsel_buyutulmuyor(self, auth_client):
        yanit = await yukle(auth_client, gorsel((50, 80)))
        adres = yanit.json()["data"]["profile_image_url"]
        with Image.open(dosya_yolu(adres)) as cikti:
            assert cikti.size == (50, 50)

    @pytest.mark.parametrize("bicim", ["JPEG", "WEBP", "GIF"])
    async def test_diger_bicimler_kabul_ediliyor(self, auth_client, bicim):
        yanit = await yukle(auth_client, gorsel(bicim=bicim), ad="a", tur="x/y")
        assert yanit.status_code == 200, yanit.text

    async def test_exif_siliniyor(self, auth_client):
        exif = Image.Exif()
        exif[0x010F] = "TelefonMarkasi"  # Make
        exif[0x8825] = {2: (41.0, 0.0, 0.0)}  # GPSInfo: enlem
        yanit = await yukle(
            auth_client, gorsel(bicim="JPEG", exif=exif.tobytes()), tur="image/jpeg"
        )
        assert yanit.status_code == 200, yanit.text

        with Image.open(dosya_yolu(yanit.json()["data"]["profile_image_url"])) as c:
            assert "exif" not in c.info
            assert len(c.getexif()) == 0

    async def test_exif_yonu_uygulaniyor(self, auth_client):
        # Sol yari kirmizi, sag yari mavi; EXIF "90 derece saga cevir"
        # diyor. Dogru uygulanirsa kirmizi uste, mavi alta gelir.
        ham = Image.new("RGB", (200, 100), (0, 0, 255))
        ham.paste((255, 0, 0), (0, 0, 100, 100))
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation
        tampon = io.BytesIO()
        ham.save(tampon, format="JPEG", exif=exif.tobytes(), quality=95)

        yanit = await yukle(auth_client, tampon.getvalue(), tur="image/jpeg")
        with Image.open(dosya_yolu(yanit.json()["data"]["profile_image_url"])) as c:
            ust = c.convert("RGB").getpixel((c.width // 2, 5))
            alt = c.convert("RGB").getpixel((c.width // 2, c.height - 5))
        assert ust[0] > 200 and ust[2] < 60, ust
        assert alt[2] > 200 and alt[0] < 60, alt

    async def test_saydamlik_korunuyor(self, auth_client):
        tampon = io.BytesIO()
        Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(tampon, format="PNG")
        yanit = await yukle(auth_client, tampon.getvalue())
        adres = yanit.json()["data"]["profile_image_url"]
        # JPEG saydamligi tasimiyor; saydam gorsel PNG olarak saklaniyor.
        assert adres.endswith(".png")
        with Image.open(dosya_yolu(adres)) as c:
            assert c.format == "PNG"
            assert c.mode == "RGBA"
            assert c.getpixel((50, 50))[3] == 0


class TestReddetme:
    async def test_gorsel_olmayan_dosya_422(self, auth_client):
        # Uzanti ve tur gorsel diyor, icerik degil: tur dosyadan okunuyor.
        yanit = await yukle(auth_client, b"<html><script>alert(1)</script></html>")
        assert yanit.status_code == 422
        assert "valid image" in yanit.json()["message"]

    async def test_desteklenmeyen_bicim_422(self, auth_client):
        tampon = io.BytesIO()
        Image.new("RGB", (10, 10)).save(tampon, format="BMP")
        yanit = await yukle(auth_client, tampon.getvalue(), ad="a.bmp")
        assert yanit.status_code == 422
        assert "Unsupported" in yanit.json()["message"]

    async def test_kesik_dosya_422(self, auth_client):
        yanit = await yukle(auth_client, gorsel()[:200])
        assert yanit.status_code == 422

    async def test_olcusu_buyuk_gorsel_cozulmeden_reddediliyor(
        self, auth_client, monkeypatch
    ):
        monkeypatch.setattr(avatar_modulu, "AZAMI_PIKSEL", 100 * 100)
        yanit = await yukle(auth_client, gorsel((101, 100)))
        assert yanit.status_code == 422
        assert "dimensions" in yanit.json()["message"]

    async def test_buyuk_dosya_413(self, auth_client, monkeypatch):
        monkeypatch.setattr(settings, "avatar_max_bytes", 1000)
        yanit = await yukle(auth_client, gorsel((300, 300)) + b"\0" * 2000)
        assert yanit.status_code == 413

    async def test_content_length_yalan_soylese_de_sinir_tutuyor(
        self, auth_client, monkeypatch
    ):
        # Uzunluk siniri ayristirmadan once bakiliyor; okunan bayt da
        # ayrica sinirli, yani ikisinden biri yeterli degil.
        monkeypatch.setattr(settings, "avatar_max_bytes", 1000)
        monkeypatch.setattr("routers.v1.profile_router._MULTIPART_PAYI", 10**6)
        yanit = await yukle(auth_client, b"x" * 5000)
        assert yanit.status_code == 413

    async def test_uzunluksuz_govde_411(self, auth_client):
        async def parcalar():
            yield b"--sinir\r\n"

        yanit = await auth_client.post(
            URL,
            content=parcalar(),
            headers={"content-type": "multipart/form-data; boundary=sinir"},
        )
        assert yanit.status_code == 411

    async def test_dosya_alani_yoksa_422(self, auth_client):
        yanit = await auth_client.post(URL, files={"baska": ("a", b"x", "x/y")})
        assert yanit.status_code in (400, 422)

    async def test_girissiz_401(self, client):
        yanit = await yukle(client, gorsel())
        assert yanit.status_code == 401

    async def test_hiz_siniri(self, auth_client):
        kucuk = gorsel((8, 8))
        for _ in range(10):
            assert (await yukle(auth_client, kucuk)).status_code == 200
        yanit = await yukle(auth_client, kucuk)
        assert yanit.status_code == 429
        assert "retry-after" in yanit.headers


class TestEskiAvatar:
    async def test_yenisi_yuklenince_eskisi_siliniyor(self, auth_client):
        ilk = (await yukle(auth_client, gorsel())).json()["data"]["profile_image_url"]
        ikinci = (await yukle(auth_client, gorsel(renk=(1, 2, 3)))).json()["data"][
            "profile_image_url"
        ]

        assert ilk != ikinci
        assert not dosya_yolu(ilk).exists()
        assert dosya_yolu(ikinci).exists()

    async def test_kayit_duserse_yazilan_dosya_siliniyor(
        self, auth_client, monkeypatch
    ):
        from services.user.user_service import UserService

        async def dus(self, user):
            raise RuntimeError("veritabani gitti")

        monkeypatch.setattr(UserService, "update_user", dus)
        oncesi = set(TEST_MEDIA_ROOT.rglob("*.jpg"))

        yanit = await yukle(auth_client, gorsel())

        assert yanit.status_code == 500
        assert set(TEST_MEDIA_ROOT.rglob("*.jpg")) == oncesi

    async def test_kaldirinca_dosya_siliniyor(self, auth_client):
        adres = (await yukle(auth_client, gorsel())).json()["data"]["profile_image_url"]
        yanit = await auth_client.delete(URL)

        assert yanit.status_code == 200
        assert yanit.json()["data"]["profile_image_url"] is None
        assert not dosya_yolu(adres).exists()

    async def test_baskasinin_dosyasi_silinmiyor(self, client, app):
        # Serbest alan zamaninda biri kendi alanina BASKASININ avatar
        # adresini yazmis olabilir. O kisi yukleme yaptiginda "eski
        # avatari" diye baskasinin dosyasi silinmemeli.
        await register_user(client)
        kurban = auth_header(await login(client))
        kurbanin = (
            await client.post(
                URL, files={"file": ("a.png", gorsel(), "image/png")}, headers=kurban
            )
        ).json()["data"]["profile_image_url"]

        await register_user(client, username="saldirgan", email="saldirgan@example.com")
        await profil_adresini_yaz(app, "saldirgan", kurbanin)
        saldirgan = auth_header(await login(client, "saldirgan@example.com"))

        yanit = await client.post(
            URL, files={"file": ("a.png", gorsel(), "image/png")}, headers=saldirgan
        )
        assert yanit.status_code == 200
        assert dosya_yolu(kurbanin).exists()

        assert (await client.delete(URL, headers=saldirgan)).status_code == 200
        assert dosya_yolu(kurbanin).exists()

    async def test_eski_dis_adres_kaldirilabiliyor(self, auth_client, app):
        await profil_adresini_yaz(
            app, DEFAULT_USER["username"], "https://example.com/a.png"
        )
        me = await auth_client.get("/api/v1/profile/me")
        assert me.json()["data"]["profile_image_url"] == "https://example.com/a.png"

        yanit = await auth_client.delete(URL)
        assert yanit.status_code == 200
        assert yanit.json()["data"]["profile_image_url"] is None


class TestSerbestAdresArtikYazilamiyor:
    """profile_image_url profil uclarindan yazilamiyor.

    Serbest alan dis bir adresi kabul ediyordu: profil sayfasi ziyaretcinin
    IP'sini o adresin sahibine sizdiriyordu ve paylasim karti o adresi
    SUNUCUDA indiriyordu (ic aga istek attirma, SSRF).
    """

    async def test_profil_guncelleme_alani_yok_sayiyor(self, auth_client):
        yanit = await auth_client.put(
            "/api/v1/profile/update",
            json={"bio": "merhaba", "profile_image_url": "http://169.254.169.254/"},
        )
        assert yanit.status_code == 200
        assert yanit.json()["data"]["bio"] == "merhaba"
        assert yanit.json()["data"]["profile_image_url"] is None

    async def test_onboarding_adim1_alani_yok_sayiyor(self, auth_client):
        yanit = await auth_client.post(
            "/api/v1/profile/complete-step-1",
            json={"display_name": "Ada", "profile_image_url": "http://api:8000/"},
        )
        assert yanit.status_code == 200
        assert yanit.json()["data"]["profile_image_url"] is None
