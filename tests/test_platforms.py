"""Platform yonetimi (admin).

ONCEDEN HIC YOKTU: 20 platform bir seed migration'iyla gelmisti ve
yeni bir platform eklemek yeni bir migration yazmak demekti. Panelden
eklemenin yolu yoktu.

BU DOSYANIN MERKEZI SORUSU SILME. social_accounts.platform_id bir
FOREIGN KEY ve ondelete CASCADE: platformu gercekten silmek, o
platformdaki BUTUN kullanicilarin sosyal hesaplarini sessizce yok
ederdi. Asagidaki testlerin en onemlisi bunu olcen.
"""

import pytest

from tests.conftest import auth_header, login, register_user, seed_platforms

# admin_client fixture'i DEFAULT_USER'i kaydedip admin yapiyor ve AYNI
# istemci nesnesini donuyor. Yonetici disinda siradan bir kullanici da
# gereken testler bu yuzden kendi kullanicisini ayri bir adla aciyor;
# DEFAULT_USER ile kaydetmek 409 verirdi.
UYE = {
    "username": "uye",
    "email": "uye@example.com",
    "password": "Secret123",
}


async def _uye_basliklari(client):
    await register_user(client, **UYE)
    return auth_header(await login(client, UYE["email"], UYE["password"]))


async def _hesap_ac(client, basliklar, platform_id: int, username: str = "kaan"):
    yanit = await client.post(
        "/api/v1/social-accounts/",
        json={
            "platform_id": platform_id,
            "username": username,
            "profile_url": f"https://ornek.test/{username}",
        },
        headers=basliklar,
    )
    assert yanit.status_code == 201, yanit.text
    return yanit.json()["data"]


@pytest.mark.asyncio
class TestYetki:
    async def test_tokensiz_401(self, client):
        assert (await client.get("/api/v1/platforms/")).status_code == 401

    async def test_siradan_kullanici_403(self, auth_client):
        """Yonetim uclari admin istiyor.

        Siradan kullanici listeyi GET /social-accounts/platforms'tan
        okuyor; buradan okumak, emekliye ayrilmislari ve kullanim
        sayilarini gormek demek olurdu.
        """
        assert (await auth_client.get("/api/v1/platforms/")).status_code == 403
        assert (
            await auth_client.post("/api/v1/platforms/", json={"name": "yeni"})
        ).status_code == 403


@pytest.mark.asyncio
class TestOlusturma:
    async def test_yeni_platform_secim_listesine_giriyor(self, admin_client):
        """Ucun asil isi: yeni platform kullanicilarca secilebilmeli."""
        yanit = await admin_client.post(
            "/api/v1/platforms/",
            json={"name": "bluesky", "display_name": "Bluesky"},
        )

        assert yanit.status_code == 201
        assert yanit.json()["data"]["name"] == "bluesky"

        secilebilir = (
            await admin_client.get("/api/v1/social-accounts/platforms")
        ).json()["data"]
        assert "bluesky" in [p["name"] for p in secilebilir]

    async def test_ad_kucuk_harfe_cevriliyor(self, admin_client):
        """UNIQUE kolonda "TikTok" ile "tiktok" iki ayri kayit olurdu ve
        secim listesinde ayni platform iki kez gorunurdu."""
        yanit = await admin_client.post(
            "/api/v1/platforms/", json={"name": "  BlueSky  "}
        )

        assert yanit.status_code == 201
        assert yanit.json()["data"]["name"] == "bluesky"

    async def test_bosluklu_ad_reddediliyor(self, admin_client):
        yanit = await admin_client.post("/api/v1/platforms/", json={"name": "kotu ad"})

        assert yanit.status_code == 422

    async def test_ayni_ad_ikinci_kez_409(self, admin_client):
        await admin_client.post("/api/v1/platforms/", json={"name": "bluesky"})

        yanit = await admin_client.post("/api/v1/platforms/", json={"name": "bluesky"})

        assert yanit.status_code == 409


@pytest.mark.asyncio
class TestEmekliyeAyirma:
    async def test_silme_KULLANICI_HESAPLARINI_YOK_ETMIYOR(
        self, client, admin_client, app
    ):
        """BU DOSYADAKI EN ONEMLI TEST.

        platform_id FOREIGN KEY ve ondelete CASCADE. Uc gercekten
        DELETE etseydi bu kullanicinin sosyal hesabi da silinirdi --
        yoneticinin bir listeden bir satir kaldirirken yapmayi
        bekleyecegi son sey, ve geri donusu yok.

        Olculen sey durum kodu degil: hesabin HALA ORADA oldugu.
        """
        platformlar = await seed_platforms(app, "instagram")
        basliklar = await _uye_basliklari(client)
        hesap = await _hesap_ac(client, basliklar, platformlar["instagram"])

        yanit = await admin_client.delete(
            f"/api/v1/platforms/{platformlar['instagram']}"
        )
        assert yanit.status_code == 204

        kalanlar = (
            await client.get("/api/v1/social-accounts/", headers=basliklar)
        ).json()["data"]
        assert [h["id"] for h in kalanlar] == [hesap["id"]], (
            "platform emekliye ayrilinca kullanicinin hesabi silinmemeli"
        )

    async def test_emekli_platform_secim_listesinden_cikiyor(self, admin_client, app):
        platformlar = await seed_platforms(app, "instagram")

        await admin_client.delete(f"/api/v1/platforms/{platformlar['instagram']}")

        secilebilir = (
            await admin_client.get("/api/v1/social-accounts/platforms")
        ).json()["data"]
        assert "instagram" not in [p["name"] for p in secilebilir]

    async def test_emekli_platform_yonetim_listesinde_kaliyor(self, admin_client, app):
        """Geri getirmek isteyen once gorebilmeli."""
        platformlar = await seed_platforms(app, "instagram")
        await admin_client.delete(f"/api/v1/platforms/{platformlar['instagram']}")

        yonetim = (await admin_client.get("/api/v1/platforms/")).json()["data"]

        satir = next(p for p in yonetim if p["name"] == "instagram")
        assert satir["is_retired"] is True

    async def test_ayni_adla_ekleme_ESKISINI_GERI_GETIRIYOR(
        self, client, admin_client, app
    ):
        """Yeni satir acmak hem patlar hem yanlis olurdu.

        `name` UNIQUE oldugu icin INSERT IntegrityError verir (500).
        Ustelik dogru davranis da bu degil: eski satira bagli sosyal
        hesaplar eski id'yi tasiyor, yani "instagram"i geri getirmek o
        hesaplarin yeniden gorunur olmasi demek.
        """
        platformlar = await seed_platforms(app, "instagram")
        basliklar = await _uye_basliklari(client)
        await _hesap_ac(client, basliklar, platformlar["instagram"])
        await admin_client.delete(f"/api/v1/platforms/{platformlar['instagram']}")

        yanit = await admin_client.post(
            "/api/v1/platforms/",
            json={"name": "instagram", "display_name": "Instagram"},
        )

        assert yanit.status_code == 201
        # AYNI id: yeni bir satir acilmadi.
        assert yanit.json()["data"]["id"] == platformlar["instagram"]

        secilebilir = (
            await admin_client.get("/api/v1/social-accounts/platforms")
        ).json()["data"]
        assert "instagram" in [p["name"] for p in secilebilir]

    async def test_olmayan_platform_404(self, admin_client):
        assert (await admin_client.delete("/api/v1/platforms/9999")).status_code == 404


@pytest.mark.asyncio
class TestKullanimSayisi:
    async def test_kac_hesabin_etkilenecegi_gorunuyor(self, client, admin_client, app):
        """Yonetici, emekliye ayirmadan once kimi etkileyecegini gormeli.

        Sayi olmasaydi karar korlemesine verilirdi.
        """
        platformlar = await seed_platforms(app, "instagram", "github")
        basliklar = await _uye_basliklari(client)
        await _hesap_ac(client, basliklar, platformlar["instagram"], "kaan")

        yonetim = (await admin_client.get("/api/v1/platforms/")).json()["data"]
        sayilar = {p["name"]: p["account_count"] for p in yonetim}

        assert sayilar["instagram"] == 1
        assert sayilar["github"] == 0


@pytest.mark.asyncio
class TestGuncelleme:
    async def test_gosterim_adi_degisiyor(self, admin_client, app):
        platformlar = await seed_platforms(app, "x")

        yanit = await admin_client.patch(
            f"/api/v1/platforms/{platformlar['x']}",
            json={"display_name": "X (Twitter)"},
        )

        assert yanit.status_code == 200
        assert yanit.json()["data"]["display_name"] == "X (Twitter)"

    async def test_ad_degistirilemiyor(self, admin_client, app):
        """`name` bilincli olarak sabit (bkz. PlatformUpdate).

        Sosyal hesaplarin bagli oldugu kimligin okunabilir tarafi ve
        herkese acik profilde ikon secimine kadar her yerde
        kullaniliyor. Govdedeki `name` yok sayiliyor, hata degil --
        sema onu hic tanimiyor.
        """
        platformlar = await seed_platforms(app, "x")

        await admin_client.patch(
            f"/api/v1/platforms/{platformlar['x']}",
            json={"name": "twitter", "display_name": "X"},
        )

        yonetim = (await admin_client.get("/api/v1/platforms/")).json()["data"]
        assert [p["name"] for p in yonetim] == ["x"]
