"""Sayfa ayarlari (PageSettings) ve herkese acik profildeki yansimasi.

Model ilk migration'dan beri veritabaninda duruyordu ama hicbir uc ona
dokunmuyordu; bu dosya yeni uclari kapsiyor.

Tablo kasten dar: users'ta karsiligi olan kolonlar (arka plan, tema
rengi, profil fotografi) b8c9d0e1f2a3 migration'inda dusuruldu. Burada
kalan iki ayarin testleri var.
"""
from tests.conftest import DEFAULT_USER, auth_header, login, register_user

YOL = "/api/v1/profile/page-settings"
PROFIL = f"/api/v1/p/{DEFAULT_USER['username']}"


class TestOkuma:
    async def test_satir_yokken_varsayilanlar_donuyor(self, auth_client):
        """Ayarlara hic dokunmamis kullanici icin 404 degil varsayilan.

        Aksi halde istemcinin "once bir kez olustur" adimi atmasi
        gerekirdi.
        """
        yanit = await auth_client.get(YOL)

        assert yanit.status_code == 200
        veri = yanit.json()["data"]
        assert veri["adult_warning_enabled"] is False
        assert veri["extra_settings"] is None

    async def test_tokensiz_401(self, client):
        assert (await client.get(YOL)).status_code == 401


class TestGuncelleme:
    async def test_ilk_yazmada_satir_olusuyor(self, auth_client):
        yanit = await auth_client.put(YOL, json={"adult_warning_enabled": True})

        assert yanit.status_code == 200
        assert yanit.json()["data"]["adult_warning_enabled"] is True
        # Kalici mi?
        assert (await auth_client.get(YOL)).json()["data"][
            "adult_warning_enabled"
        ] is True

    async def test_ikinci_guncelleme_ayni_satiri_kullaniyor(self, auth_client):
        """user_id UNIQUE; ikinci yazma yeni satir acmaya calismamali."""
        await auth_client.put(YOL, json={"adult_warning_enabled": True})

        yanit = await auth_client.put(YOL, json={"adult_warning_enabled": False})

        assert yanit.status_code == 200
        assert yanit.json()["data"]["adult_warning_enabled"] is False

    async def test_verilmeyen_alan_degismiyor(self, auth_client):
        await auth_client.put(
            YOL,
            json={"adult_warning_enabled": True, "extra_settings": {"tema": "koyu"}},
        )

        await auth_client.put(YOL, json={"adult_warning_enabled": False})

        veri = (await auth_client.get(YOL)).json()["data"]
        assert veri["adult_warning_enabled"] is False
        assert veri["extra_settings"] == {"tema": "koyu"}

    async def test_extra_settings_acikca_bosaltilabiliyor(self, auth_client):
        await auth_client.put(YOL, json={"extra_settings": {"tema": "koyu"}})

        await auth_client.put(YOL, json={"extra_settings": None})

        assert (await auth_client.get(YOL)).json()["data"]["extra_settings"] is None

    async def test_bos_govde_422(self, auth_client):
        assert (await auth_client.put(YOL, json={})).status_code == 422

    async def test_acikca_null_gonderilen_bayrak_422(self, auth_client):
        """Kolon nullable=False; None yazilsaydi 500 olurdu."""
        yanit = await auth_client.put(YOL, json={"adult_warning_enabled": None})

        assert yanit.status_code == 422

    async def test_cok_buyuk_extra_settings_422(self, auth_client):
        yanit = await auth_client.put(
            YOL, json={"extra_settings": {"dolgu": "x" * 5000}}
        )

        assert yanit.status_code == 422

    async def test_sinirin_altindaki_extra_settings_kabul_ediliyor(self, auth_client):
        """Sinir tumden engellememeli; makul bir govde gecmeli."""
        yanit = await auth_client.put(
            YOL, json={"extra_settings": {"dolgu": "x" * 1000}}
        )

        assert yanit.status_code == 200

    async def test_tokensiz_401(self, client):
        yanit = await client.put(YOL, json={"adult_warning_enabled": True})

        assert yanit.status_code == 401


class TestKullanicilarAyrisiyor:
    async def test_baskasinin_ayari_gorunmuyor(self, client):
        await register_user(client)
        ilk = auth_header(await login(client))
        await client.put(YOL, json={"adult_warning_enabled": True}, headers=ilk)

        await register_user(client, username="baskasi", email="baskasi@example.com")
        ikinci = auth_header(await login(client, identifier="baskasi@example.com"))

        veri = (await client.get(YOL, headers=ikinci)).json()["data"]
        assert veri["adult_warning_enabled"] is False


class TestHerkeseAcikProfil:
    async def test_varsayilan_olarak_false(self, auth_client):
        yanit = await auth_client.get(PROFIL)

        assert yanit.status_code == 200
        assert yanit.json()["data"]["adult_warning_enabled"] is False

    async def test_acilinca_profilde_gorunuyor(self, auth_client):
        await auth_client.put(YOL, json={"adult_warning_enabled": True})

        veri = (await auth_client.get(PROFIL)).json()["data"]

        assert veri["adult_warning_enabled"] is True

    async def test_kapatilinca_profilde_de_kapaniyor(self, auth_client):
        await auth_client.put(YOL, json={"adult_warning_enabled": True})
        await auth_client.put(YOL, json={"adult_warning_enabled": False})

        veri = (await auth_client.get(PROFIL)).json()["data"]

        assert veri["adult_warning_enabled"] is False

    async def test_extra_settings_herkese_acik_profile_sizmiyor(self, auth_client):
        """Alanin semasi yok; icerigini istemci belirliyor.

        Herkese acik yanita eklenseydi, sahibinin oraya koydugu her sey
        yayinlanmis olurdu.
        """
        await auth_client.put(
            YOL, json={"extra_settings": {"gizli_not": "bu-disari-cikmamali"}}
        )

        yanit = await auth_client.get(PROFIL)

        assert "extra_settings" not in yanit.json()["data"]
        assert "bu-disari-cikmamali" not in yanit.text

    async def test_tokensiz_ziyaretci_de_bayragi_goruyor(self, client):
        """Uyari ziyaretci icin; token olmadan da gelmeli."""
        await register_user(client)
        basliklar = auth_header(await login(client))
        await client.put(YOL, json={"adult_warning_enabled": True}, headers=basliklar)

        veri = (await client.get(PROFIL)).json()["data"]

        assert veri["adult_warning_enabled"] is True
