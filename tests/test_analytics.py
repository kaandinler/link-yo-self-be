"""GET /analytics/summary - pano ve analytics sayfasinin okudugu ozet."""

from datetime import UTC, datetime, time, timedelta

from tests.conftest import DEFAULT_USER, auth_header, login, register_user
from tests.test_links import create_link
from utils.time_utils import utcnow


class TestAnalyticsOzeti:
    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/analytics/summary")
        assert response.status_code == 401

    async def test_bos_hesapta_sifirlar(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/summary")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["total_links"] == 0
        assert data["active_links"] == 0
        assert data["total_clicks"] == 0
        assert data["profile_view_count"] == 0
        assert data["links"] == []

    async def test_toplamlar_ve_siralama(self, auth_client):
        bir = await create_link(auth_client, title="Bir")
        iki = await create_link(auth_client, title="Iki")
        await auth_client.patch(f"/api/v1/links/{iki['id']}/toggle")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")

        response = await auth_client.get("/api/v1/analytics/summary")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_links"] == 2
        assert data["active_links"] == 1
        # Pasif linkin gecmis tiklamalari toplamdan dusmemeli.
        assert data["total_clicks"] == 2
        # En cok tiklanan basta
        assert data["links"][0]["title"] == "Bir"

    async def test_profil_bilgileri_doner(self, auth_client):
        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]

        assert data["username"] == DEFAULT_USER["username"]
        assert data["profile_url_path"] == f"/{DEFAULT_USER['username']}"

    async def test_baska_kullanicinin_linkleri_sayilmaz(self, auth_client):
        await create_link(auth_client, title="Benim")

        await register_user(auth_client, username="baska", email="baska@example.com")
        baska_token = await login(auth_client, "baska@example.com")

        response = await auth_client.get(
            "/api/v1/analytics/summary", headers=auth_header(baska_token)
        )

        assert response.json()["data"]["total_links"] == 0


class TestProfilGoruntulenme:
    async def test_public_profil_ziyareti_sayaci_artirir(self, auth_client):
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]

        assert data["profile_view_count"] == 2

    async def test_olmayan_profil_sayaci_artirmaz(self, auth_client):
        response = await auth_client.get("/api/v1/p/olmayan")
        assert response.status_code == 404

        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]
        assert data["profile_view_count"] == 0

    async def test_count_view_false_sayaci_artirmaz(self, auth_client):
        """Paylasim kartinin okumasi ziyaret sayilmamali.

        Frontend karti cizerken ayni ucu yeniden cagiriyor. Sayac
        varsayilan olarak arttigi icin bir kaziyicinin kart istegi
        "ziyaret" olarak sayiliyordu; kimsenin gormedigi bir sayfa
        goruntulenme uretiyordu.
        """
        for _ in range(3):
            response = await auth_client.get(
                f"/api/v1/p/{DEFAULT_USER['username']}?count_view=false"
            )
            assert response.status_code == 200, response.text

        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]

        assert data["profile_view_count"] == 0

    async def test_count_view_false_yaniti_degistirmiyor(self, auth_client):
        """Bayrak yalnizca sayimi kapatiyor; donen profil ayni."""
        sayan = await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")
        saymayan = await auth_client.get(
            f"/api/v1/p/{DEFAULT_USER['username']}?count_view=false"
        )

        assert sayan.json()["data"] == saymayan.json()["data"]

    async def test_count_view_varsayilani_hala_sayiyor(self, auth_client):
        """Bayrak verilmezse davranis degismiyor."""
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]

        assert data["profile_view_count"] == 1

    async def test_sayac_kullaniciya_ozel(self, client):
        await register_user(client)
        await register_user(client, username="baska", email="baska@example.com")
        token = await login(client)
        baska_token = await login(client, "baska@example.com")

        await client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        benim = (
            await client.get("/api/v1/analytics/summary", headers=auth_header(token))
        ).json()["data"]
        baska = (
            await client.get(
                "/api/v1/analytics/summary", headers=auth_header(baska_token)
            )
        ).json()["data"]

        assert benim["profile_view_count"] == 1
        assert baska["profile_view_count"] == 0


class TestAnalyticsZamanSerisi:
    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/analytics/timeseries")
        assert response.status_code == 401

    async def test_varsayilan_yedi_gun(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/timeseries")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["days"] == 7
        assert len(data["points"]) == 7

    async def test_olaysiz_gunler_sifirla_doluyor(self, auth_client):
        data = (await auth_client.get("/api/v1/analytics/timeseries?days=30")).json()[
            "data"
        ]

        assert len(data["points"]) == 30
        assert data["total_clicks"] == 0
        assert data["total_profile_views"] == 0
        assert all(nokta["clicks"] == 0 for nokta in data["points"])

    async def test_gunler_artan_sirada_ve_bugunle_bitiyor(self, auth_client):
        data = (await auth_client.get("/api/v1/analytics/timeseries?days=3")).json()[
            "data"
        ]

        gunler = [nokta["date"] for nokta in data["points"]]
        assert gunler == sorted(gunler)
        assert gunler[0] == data["start_date"]
        assert gunler[-1] == data["end_date"]

    async def test_tiklama_bugune_yaziliyor(self, auth_client):
        link = await create_link(auth_client, title="Olculen")
        await auth_client.post(f"/api/v1/links/{link['id']}/click")
        await auth_client.post(f"/api/v1/links/{link['id']}/click")

        data = (await auth_client.get("/api/v1/analytics/timeseries?days=7")).json()[
            "data"
        ]

        assert data["total_clicks"] == 2
        assert data["points"][-1]["clicks"] == 2
        # Onceki gunlere yazilmamali.
        assert all(nokta["clicks"] == 0 for nokta in data["points"][:-1])

    async def test_profil_goruntulemesi_sayiliyor(self, auth_client):
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        data = (await auth_client.get("/api/v1/analytics/timeseries?days=7")).json()[
            "data"
        ]

        assert data["total_profile_views"] == 1
        assert data["points"][-1]["profile_views"] == 1

    async def test_count_view_false_zaman_serisine_de_girmiyor(self, auth_client):
        """Sayac ile olay kaydi ayri yerlerde tutuluyor; ikisi de susmali."""
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}?count_view=false")

        data = (await auth_client.get("/api/v1/analytics/timeseries?days=7")).json()[
            "data"
        ]

        assert data["total_profile_views"] == 0

    async def test_baska_kullanicinin_olaylari_sizmaz(self, auth_client):
        link = await create_link(auth_client, title="Benim")
        await auth_client.post(f"/api/v1/links/{link['id']}/click")

        await register_user(auth_client, username="baska", email="baska@example.com")
        baska_token = await login(auth_client, "baska@example.com")

        data = (
            await auth_client.get(
                "/api/v1/analytics/timeseries", headers=auth_header(baska_token)
            )
        ).json()["data"]

        assert data["total_clicks"] == 0

    async def test_gecersiz_gun_sayisi_422(self, auth_client):
        assert (
            await auth_client.get("/api/v1/analytics/timeseries?days=0")
        ).status_code == 422
        assert (
            await auth_client.get("/api/v1/analytics/timeseries?days=91")
        ).status_code == 422

    async def test_silinen_link_gecmis_tiklamayi_goturmez(self, auth_client):
        link = await create_link(auth_client, title="Silinecek")
        await auth_client.post(f"/api/v1/links/{link['id']}/click")
        await auth_client.delete(f"/api/v1/links/{link['id']}")

        data = (await auth_client.get("/api/v1/analytics/timeseries?days=7")).json()[
            "data"
        ]

        # Olay link_id'si bosa duser ama satir kalir: gecmis bir gunun
        # toplami bugun yapilan bir silme yuzunden degismemeli.
        assert data["total_clicks"] == 1


class TestLinkZamanSerisi:
    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/analytics/timeseries/by-link")
        assert response.status_code == 401

    async def test_linki_olmayan_hesapta_bos_liste(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/timeseries/by-link")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["days"] == 7
        assert data["links"] == []

    async def test_tiklanmayan_link_de_listede(self, auth_client):
        await create_link(auth_client, title="Sessiz")

        data = (await auth_client.get("/api/v1/analytics/timeseries/by-link")).json()[
            "data"
        ]

        assert len(data["links"]) == 1
        seri = data["links"][0]
        assert seri["title"] == "Sessiz"
        assert seri["total_clicks"] == 0
        assert len(seri["points"]) == 7
        assert all(nokta["clicks"] == 0 for nokta in seri["points"])

    async def test_tiklamalar_dogru_linke_yaziliyor(self, auth_client):
        bir = await create_link(auth_client, title="Bir")
        iki = await create_link(auth_client, title="Iki")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")
        await auth_client.post(f"/api/v1/links/{iki['id']}/click")

        data = (
            await auth_client.get("/api/v1/analytics/timeseries/by-link?days=3")
        ).json()["data"]

        seriler = {seri["title"]: seri for seri in data["links"]}
        assert seriler["Bir"]["total_clicks"] == 2
        assert seriler["Iki"]["total_clicks"] == 1
        # Bugun son gun.
        assert seriler["Bir"]["points"][-1]["clicks"] == 2
        assert all(nokta["clicks"] == 0 for nokta in seriler["Bir"]["points"][:-1])

    async def test_en_cok_tiklanan_basta(self, auth_client):
        az = await create_link(auth_client, title="Az")
        cok = await create_link(auth_client, title="Cok")
        await auth_client.post(f"/api/v1/links/{az['id']}/click")
        for _ in range(3):
            await auth_client.post(f"/api/v1/links/{cok['id']}/click")

        data = (await auth_client.get("/api/v1/analytics/timeseries/by-link")).json()[
            "data"
        ]

        assert [seri["title"] for seri in data["links"]] == ["Cok", "Az"]

    async def test_pasif_link_de_listede(self, auth_client):
        link = await create_link(auth_client, title="Pasif")
        await auth_client.patch(f"/api/v1/links/{link['id']}/toggle")

        data = (await auth_client.get("/api/v1/analytics/timeseries/by-link")).json()[
            "data"
        ]

        assert data["links"][0]["title"] == "Pasif"
        assert data["links"][0]["is_active"] is False

    async def test_silinen_linkin_tiklamalari_kirilimda_yok(self, auth_client):
        kalan = await create_link(auth_client, title="Kalan")
        silinecek = await create_link(auth_client, title="Silinecek")
        await auth_client.post(f"/api/v1/links/{silinecek['id']}/click")
        await auth_client.post(f"/api/v1/links/{kalan['id']}/click")
        await auth_client.delete(f"/api/v1/links/{silinecek['id']}")

        kirilim = (
            await auth_client.get("/api/v1/analytics/timeseries/by-link")
        ).json()["data"]
        genel = (await auth_client.get("/api/v1/analytics/timeseries")).json()["data"]

        basliklar = [seri["title"] for seri in kirilim["links"]]
        assert basliklar == ["Kalan"]
        # Olay satiri duruyor: genel seride iki tiklama da sayiliyor.
        assert genel["total_clicks"] == 2
        assert sum(seri["total_clicks"] for seri in kirilim["links"]) == 1

    async def test_baska_kullanicinin_linkleri_gorunmez(self, auth_client):
        await create_link(auth_client, title="Benim")

        await register_user(auth_client, username="baska", email="baska@example.com")
        baska_token = await login(auth_client, "baska@example.com")

        data = (
            await auth_client.get(
                "/api/v1/analytics/timeseries/by-link",
                headers=auth_header(baska_token),
            )
        ).json()["data"]

        assert data["links"] == []

    async def test_gecersiz_gun_sayisi_422(self, auth_client):
        assert (
            await auth_client.get("/api/v1/analytics/timeseries/by-link?days=0")
        ).status_code == 422
        assert (
            await auth_client.get("/api/v1/analytics/timeseries/by-link?days=91")
        ).status_code == 422


async def tikla(client, link_id: int, referrer: str | None = None):
    """Tiklama ucunu cagirir; referrer verilirse govdede gonderir.

    Govdesiz cagri bilincli olarak destekleniyor: referrer'i olmayan
    ziyaretler ve eski istemciler icin.
    """
    govde = None if referrer is None else {"referrer": referrer}
    response = await client.post(f"/api/v1/links/{link_id}/click", json=govde)
    assert response.status_code == 200, response.text
    return response


def kaynak_sozlugu(data: dict) -> dict:
    """Yanittaki kaynak listesini {etiket: tiklama} sozluguna cevirir."""
    return {
        kaynak["host"] or kaynak["kind"]: kaynak["clicks"] for kaynak in data["sources"]
    }


class TestTrafikKaynaklari:
    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/analytics/referrers")
        assert response.status_code == 401

    async def test_bos_hesapta_bos_liste(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/referrers")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["days"] == 7
        assert data["total_clicks"] == 0
        assert data["sources"] == []

    async def test_referrersiz_tiklama_dogrudan_sayiliyor(self, auth_client):
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"])

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert data["total_clicks"] == 1
        assert data["sources"] == [{"kind": "direct", "host": None, "clicks": 1}]

    async def test_dis_site_host_olarak_geliyor(self, auth_client):
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "https://www.instagram.com/p/abc?x=1")

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert data["sources"] == [
            {"kind": "host", "host": "instagram.com", "clicks": 1}
        ]

    async def test_ayni_kaynak_tek_satirda_toplaniyor(self, auth_client):
        link = await create_link(auth_client)
        # Farkli yol, farkli sorgu, "www." var/yok: hepsi ayni kaynak.
        await tikla(auth_client, link["id"], "https://instagram.com/p/bir")
        await tikla(auth_client, link["id"], "https://www.instagram.com/p/iki?a=1")

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert kaynak_sozlugu(data) == {"instagram.com": 2}

    async def test_site_ici_gezinme_dogrudan_sayiliyor(self, auth_client):
        # Testlerde frontend_url varsayilan: http://localhost:3000
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "http://localhost:3000/en/kaan")

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert kaynak_sozlugu(data) == {"direct": 1}

    async def test_ayrastirilamayan_referrer_istegi_dusurmuyor(self, auth_client):
        # Tiklama sayaci, kaynak bilgisinden onemli: cop bir referrer
        # yuzunden tiklama kaybedilmemeli.
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "hello world")

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]
        assert kaynak_sozlugu(data) == {"direct": 1}

        ozet = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]
        assert ozet["total_clicks"] == 1

    async def test_cok_uzun_referrer_422(self, auth_client):
        link = await create_link(auth_client)
        response = await auth_client.post(
            f"/api/v1/links/{link['id']}/click",
            json={"referrer": "https://example.com/" + "a" * 3000},
        )
        assert response.status_code == 422

    async def test_en_cok_getiren_kaynak_basta(self, auth_client):
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "https://t.co/a")
        for _ in range(3):
            await tikla(auth_client, link["id"], "https://instagram.com/p/a")
        await tikla(auth_client, link["id"])
        await tikla(auth_client, link["id"])

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        # Dogrudan satiri da siralamaya giriyor; en ustte kalmiyor diye
        # gizlenmiyor.
        assert [kaynak["clicks"] for kaynak in data["sources"]] == [3, 2, 1]
        assert data["sources"][0]["host"] == "instagram.com"
        assert data["sources"][1]["kind"] == "direct"
        assert data["sources"][2]["host"] == "t.co"

    async def test_toplam_kaynaklarin_toplamina_esit(self, auth_client):
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "https://instagram.com/p/a")
        await tikla(auth_client, link["id"], "https://t.co/a")
        await tikla(auth_client, link["id"])

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert data["total_clicks"] == sum(
            kaynak["clicks"] for kaynak in data["sources"]
        )

    async def test_uzun_kuyruk_diger_satirinda_ve_sonda(self, auth_client):
        from services.analytics.analytics_service import MAX_SOURCES

        link = await create_link(auth_client)
        # Listeye sigacak kadar kaynak, her biri iki tiklama.
        for sira in range(MAX_SOURCES):
            for _ in range(2):
                await tikla(auth_client, link["id"], f"https://site{sira}.com/a")
        # Sigmayacak iki kaynak, birer tiklama.
        await tikla(auth_client, link["id"], "https://kuyruk-bir.com/a")
        await tikla(auth_client, link["id"], "https://kuyruk-iki.com/a")

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert len(data["sources"]) == MAX_SOURCES + 1
        son = data["sources"][-1]
        assert son["kind"] == "other"
        assert son["clicks"] == 2
        # Kuyruk gizlenmiyor, toplama dahil.
        assert data["total_clicks"] == MAX_SOURCES * 2 + 2

    async def test_profil_goruntulemesi_kaynak_listesine_girmiyor(self, auth_client):
        # Profil goruntulemesi sunucuda kaydediliyor ve orada ziyaretcinin
        # referrer'i elimizde olmuyor; listeye girseydi "Direct"i yapay
        # olarak sisirirdi.
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "https://instagram.com/p/a")
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        data = (await auth_client.get("/api/v1/analytics/referrers")).json()["data"]

        assert data["total_clicks"] == 1
        assert kaynak_sozlugu(data) == {"instagram.com": 1}

    async def test_baska_kullanicinin_tiklamalari_sizmaz(self, auth_client):
        link = await create_link(auth_client)
        await tikla(auth_client, link["id"], "https://instagram.com/p/a")

        await register_user(auth_client, username="baska", email="baska@example.com")
        baska_token = await login(auth_client, "baska@example.com")

        data = (
            await auth_client.get(
                "/api/v1/analytics/referrers", headers=auth_header(baska_token)
            )
        ).json()["data"]

        assert data["total_clicks"] == 0
        assert data["sources"] == []

    async def test_gecersiz_gun_sayisi_422(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/referrers?days=0")
        assert response.status_code == 422

        response = await auth_client.get("/api/v1/analytics/referrers?days=91")
        assert response.status_code == 422


async def olay_yaz(app, user_id: int, ne_zaman, link_id=None, adet=1):
    """Belirli bir ana tiklama olayi yazar.

    Uc uzerinden yazilamiyor: tiklama her zaman "simdi" kaydediliyor.
    Gecmise ait bir zaman istendigi icin dogrudan veritabanina yaziliyor.
    """
    from models import EVENT_LINK_CLICK, AnalyticsEvent

    session_factory = app.container.async_session_factory()
    async with session_factory() as session:
        for _ in range(adet):
            session.add(
                AnalyticsEvent(
                    user_id=user_id,
                    event_type=EVENT_LINK_CLICK,
                    link_id=link_id,
                    created_at=ne_zaman,
                )
            )
        await session.commit()


async def kullanici_id(client) -> int:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def gun_sozlugu(data: dict) -> dict:
    return {k["weekday"]: k["clicks"] for k in data["by_weekday"] if k["clicks"]}


def saat_sozlugu(data: dict) -> dict:
    return {k["hour"]: k["clicks"] for k in data["by_hour"] if k["clicks"]}


class TestEnIyiZamanlar:
    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/analytics/best-times")
        assert response.status_code == 401

    async def test_bos_hesapta_sifirlar(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/best-times")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["days"] == 30
        assert data["timezone"] == "UTC"
        assert data["total_clicks"] == 0
        # Kutular her zaman tam: cagiran taraf eksikleri tamamlamak
        # zorunda kalmasin.
        assert len(data["by_weekday"]) == 7
        assert len(data["by_hour"]) == 24
        assert data["peak_weekday"] is None
        assert data["peak_hour"] is None
        assert data["enough_data"] is False

    async def test_tiklamalar_saatlere_dagiliyor(self, auth_client, app):
        from datetime import UTC, datetime, timedelta

        kimlik = await kullanici_id(auth_client)
        link = await create_link(auth_client)
        dun = datetime.now(UTC) - timedelta(days=1)

        await olay_yaz(app, kimlik, dun.replace(hour=9, minute=0), link["id"], adet=3)
        await olay_yaz(app, kimlik, dun.replace(hour=21, minute=0), link["id"], adet=1)

        data = (await auth_client.get("/api/v1/analytics/best-times")).json()["data"]

        assert data["total_clicks"] == 4
        assert saat_sozlugu(data) == {9: 3, 21: 1}
        assert data["peak_hour"] == 9

    async def test_saat_dilimi_saatleri_kaydiriyor(self, auth_client, app):
        from datetime import UTC, datetime, timedelta

        kimlik = await kullanici_id(auth_client)
        link = await create_link(auth_client)
        dun = datetime.now(UTC) - timedelta(days=1)
        await olay_yaz(app, kimlik, dun.replace(hour=9), link["id"], adet=2)

        utc = (await auth_client.get("/api/v1/analytics/best-times")).json()["data"]
        istanbul = (
            await auth_client.get("/api/v1/analytics/best-times?tz=Europe/Istanbul")
        ).json()["data"]

        assert saat_sozlugu(utc) == {9: 2}
        # UTC+3: ayni olay kullanicinin saatiyle 12'de.
        assert saat_sozlugu(istanbul) == {12: 2}
        assert istanbul["timezone"] == "Europe/Istanbul"
        # Toplam degismiyor; yalnizca kutular kayiyor.
        assert istanbul["total_clicks"] == utc["total_clicks"]

    async def test_saat_dilimi_gun_sinirini_kaydiriyor(self, auth_client, app):
        # Asil mesele bu: gece yarisina yakin bir tiklama, kullanicinin
        # saat diliminde baska bir gune dusuyor. Saatleri cevirip gunu
        # UTC'den okumak burada yanlis cevap verirdi.
        from datetime import UTC, datetime

        kimlik = await kullanici_id(auth_client)
        link = await create_link(auth_client)

        # 2026-09-14 bir Pazartesi. 23:00 UTC -> Istanbul'da Sali 02:00.
        an = datetime(2026, 9, 14, 23, tzinfo=UTC)
        await olay_yaz(app, kimlik, an, link["id"], adet=2)

        yol = "/api/v1/analytics/best-times?days=90"
        utc = (await auth_client.get(yol)).json()["data"]
        istanbul = (await auth_client.get(f"{yol}&tz=Europe/Istanbul")).json()["data"]

        assert gun_sozlugu(utc) == {0: 2}  # Pazartesi
        assert gun_sozlugu(istanbul) == {1: 2}  # Sali
        assert saat_sozlugu(istanbul) == {2: 2}

    async def test_az_veriyle_zirve_iddia_edilmiyor(self, auth_client, app):
        from datetime import UTC, datetime, timedelta

        from services.analytics.analytics_service import MIN_CLICKS_FOR_PEAK

        kimlik = await kullanici_id(auth_client)
        link = await create_link(auth_client)
        dun = datetime.now(UTC) - timedelta(days=1)

        await olay_yaz(app, kimlik, dun.replace(hour=9), link["id"], adet=3)
        az = (await auth_client.get("/api/v1/analytics/best-times")).json()["data"]
        assert az["enough_data"] is False
        # Zirve yine donuyor -- arayuz "su an en cok" diyebilsin diye; ama
        # bayrak "en iyi gunun su" demeyi engelliyor.
        assert az["peak_hour"] == 9

        await olay_yaz(
            app,
            kimlik,
            dun.replace(hour=9),
            link["id"],
            adet=MIN_CLICKS_FOR_PEAK,
        )
        cok = (await auth_client.get("/api/v1/analytics/best-times")).json()["data"]
        assert cok["enough_data"] is True

    async def test_profil_goruntulemesi_sayilmiyor(self, auth_client, app):
        from datetime import UTC, datetime, timedelta

        from models import EVENT_PROFILE_VIEW

        kimlik = await kullanici_id(auth_client)
        link = await create_link(auth_client)
        dun = datetime.now(UTC) - timedelta(days=1)
        await olay_yaz(app, kimlik, dun.replace(hour=9), link["id"], adet=2)

        session_factory = app.container.async_session_factory()
        from models import AnalyticsEvent

        async with session_factory() as session:
            session.add(
                AnalyticsEvent(
                    user_id=kimlik,
                    event_type=EVENT_PROFILE_VIEW,
                    created_at=dun.replace(hour=15),
                )
            )
            await session.commit()

        data = (await auth_client.get("/api/v1/analytics/best-times")).json()["data"]

        # Uc yalnizca tiklamalari sayiyor; 15 saati listede olmamali.
        assert saat_sozlugu(data) == {9: 2}

    async def test_baska_kullanicinin_tiklamalari_sizmaz(self, auth_client, app):
        from datetime import UTC, datetime, timedelta

        kimlik = await kullanici_id(auth_client)
        link = await create_link(auth_client)
        dun = datetime.now(UTC) - timedelta(days=1)
        await olay_yaz(app, kimlik, dun.replace(hour=9), link["id"], adet=2)

        await register_user(auth_client, username="baska", email="baska@example.com")
        baska_token = await login(auth_client, "baska@example.com")

        data = (
            await auth_client.get(
                "/api/v1/analytics/best-times", headers=auth_header(baska_token)
            )
        ).json()["data"]

        assert data["total_clicks"] == 0

    async def test_gecersiz_saat_dilimi_422(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/best-times?tz=Mars/Olympus")
        assert response.status_code == 422
        assert "Mars/Olympus" in response.text

    async def test_gecersiz_gun_sayisi_422(self, auth_client):
        assert (
            await auth_client.get("/api/v1/analytics/best-times?days=0")
        ).status_code == 422
        assert (
            await auth_client.get("/api/v1/analytics/best-times?days=91")
        ).status_code == 422


class TestTarihAraligi:
    """Serbest tarih araligi: `days` yerine `start`/`end`.

    `days` yalnizca "son N gun" sorusunu cevapliyordu; belirli bir
    kampanyanin penceresine bakmak mumkun degildi.
    """

    async def test_aralik_disindaki_olaylar_sayilmiyor(self, auth_client, app):
        kid = await kullanici_id(auth_client)
        bugun = utcnow().date()

        # Aralik: 10 gun once - 8 gun once (uc gun).
        await olay_yaz(app, kid, utcnow() - timedelta(days=12), adet=5)  # once
        await olay_yaz(app, kid, utcnow() - timedelta(days=9), adet=3)  # icinde
        await olay_yaz(app, kid, utcnow() - timedelta(days=6), adet=7)  # sonra

        start = (bugun - timedelta(days=10)).isoformat()
        end = (bugun - timedelta(days=8)).isoformat()
        response = await auth_client.get(
            f"/api/v1/analytics/timeseries?start={start}&end={end}"
        )

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["total_clicks"] == 3
        assert data["days"] == 3
        assert data["start_date"] == start
        assert data["end_date"] == end
        assert len(data["points"]) == 3

    async def test_iki_ucu_da_dahil(self, auth_client, app):
        kid = await kullanici_id(auth_client)
        bugun = utcnow().date()
        start_gun = bugun - timedelta(days=5)
        end_gun = bugun - timedelta(days=3)

        # Tam sinirlarda, gunun basinda ve sonuna cok yakin.
        await olay_yaz(app, kid, datetime.combine(start_gun, time(0, 0), tzinfo=UTC))
        await olay_yaz(
            app,
            kid,
            datetime.combine(end_gun, time(23, 59, 59, 999999), tzinfo=UTC),
        )

        response = await auth_client.get(
            "/api/v1/analytics/timeseries"
            f"?start={start_gun.isoformat()}&end={end_gun.isoformat()}"
        )

        # Ust siniri "23:59:59" diye yazmak son mikrosaniyeyi disarida
        # birakirdi; sinir ertesi gunun basi ve disarida.
        assert response.json()["data"]["total_clicks"] == 2

    async def test_dort_ucta_da_calisiyor(self, auth_client, app):
        kid = await kullanici_id(auth_client)
        bugun = utcnow().date()
        await olay_yaz(app, kid, utcnow() - timedelta(days=20), adet=4)
        await olay_yaz(app, kid, utcnow() - timedelta(days=2), adet=6)

        start = (bugun - timedelta(days=25)).isoformat()
        end = (bugun - timedelta(days=15)).isoformat()

        for yol in (
            "timeseries",
            "timeseries/by-link",
            "referrers",
            "best-times",
        ):
            response = await auth_client.get(
                f"/api/v1/analytics/{yol}?start={start}&end={end}"
            )
            assert response.status_code == 200, f"{yol}: {response.text}"
            data = response.json()["data"]
            assert data["start_date"] == start, yol
            assert data["end_date"] == end, yol
            assert data["days"] == 11, yol

    async def test_referrers_araligin_disini_saymiyor(self, auth_client, app):
        """Bu test SQL'deki ust siniri olcuyor.

        /timeseries ve /timeseries/by-link araligin gunlerini zaten
        Python'da geziyor, dolayisiyla aralik disi bir gun ciktiya hic
        giremiyor -- oralarda ust sinir bir hizlandirma. /referrers ile
        /best-times ise repository'den gelen butun satirlari topluyor;
        ust sinir olmazsa "end"den sonraki tiklamalar da sayiliyor.
        """
        kid = await kullanici_id(auth_client)
        bugun = utcnow().date()

        await olay_yaz(app, kid, utcnow() - timedelta(days=9), adet=3)
        await olay_yaz(app, kid, utcnow() - timedelta(days=2), adet=7)

        start = (bugun - timedelta(days=10)).isoformat()
        end = (bugun - timedelta(days=8)).isoformat()
        response = await auth_client.get(
            f"/api/v1/analytics/referrers?start={start}&end={end}"
        )

        assert response.status_code == 200, response.text
        # Ust sinir olmadan 10 olurdu.
        assert response.json()["data"]["total_clicks"] == 3

    async def test_best_times_araligin_disini_saymiyor(self, auth_client, app):
        kid = await kullanici_id(auth_client)
        bugun = utcnow().date()

        await olay_yaz(app, kid, utcnow() - timedelta(days=9), adet=3)
        await olay_yaz(app, kid, utcnow() - timedelta(days=2), adet=7)

        start = (bugun - timedelta(days=10)).isoformat()
        end = (bugun - timedelta(days=8)).isoformat()
        response = await auth_client.get(
            f"/api/v1/analytics/best-times?start={start}&end={end}"
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["total_clicks"] == 3

    async def test_tek_basina_start_reddediliyor(self, auth_client):
        # "start'tan bugune" mi, "start'tan days gun" mu belirsiz.
        bugun = utcnow().date().isoformat()
        response = await auth_client.get(f"/api/v1/analytics/timeseries?start={bugun}")

        assert response.status_code == 422

    async def test_tek_basina_end_reddediliyor(self, auth_client):
        bugun = utcnow().date().isoformat()
        response = await auth_client.get(f"/api/v1/analytics/timeseries?end={bugun}")

        assert response.status_code == 422

    async def test_ters_aralik_reddediliyor(self, auth_client):
        bugun = utcnow().date()
        response = await auth_client.get(
            "/api/v1/analytics/timeseries"
            f"?start={bugun.isoformat()}"
            f"&end={(bugun - timedelta(days=3)).isoformat()}"
        )

        assert response.status_code == 422

    async def test_cok_uzun_aralik_reddediliyor(self, auth_client):
        from services.analytics.analytics_service import MAX_DAYS

        bugun = utcnow().date()
        start = bugun - timedelta(days=MAX_DAYS)  # MAX_DAYS + 1 gun eder

        response = await auth_client.get(
            "/api/v1/analytics/timeseries"
            f"?start={start.isoformat()}&end={bugun.isoformat()}"
        )

        assert response.status_code == 422

    async def test_tam_sinirdaki_aralik_kabul_ediliyor(self, auth_client):
        from services.analytics.analytics_service import MAX_DAYS

        bugun = utcnow().date()
        start = bugun - timedelta(days=MAX_DAYS - 1)

        response = await auth_client.get(
            "/api/v1/analytics/timeseries"
            f"?start={start.isoformat()}&end={bugun.isoformat()}"
        )

        assert response.status_code == 200
        assert response.json()["data"]["days"] == MAX_DAYS

    async def test_bozuk_tarih_reddediliyor(self, auth_client):
        response = await auth_client.get(
            "/api/v1/analytics/timeseries?start=17-09-2026&end=2026-09-18"
        )

        assert response.status_code == 422

    async def test_start_end_verilince_days_yok_sayiliyor(self, auth_client, app):
        kid = await kullanici_id(auth_client)
        bugun = utcnow().date()
        await olay_yaz(app, kid, utcnow() - timedelta(days=20), adet=2)

        start = (bugun - timedelta(days=25)).isoformat()
        end = (bugun - timedelta(days=15)).isoformat()
        response = await auth_client.get(
            f"/api/v1/analytics/timeseries?days=7&start={start}&end={end}"
        )

        # days=7 son yedi gunu verirdi ve bu olay orada degil.
        assert response.json()["data"]["total_clicks"] == 2
        assert response.json()["data"]["days"] == 11

    async def test_days_hala_calisiyor(self, auth_client, app):
        # Geriye donuk uyumluluk: arayuzun hazir araliklari days kullaniyor.
        kid = await kullanici_id(auth_client)
        await olay_yaz(app, kid, utcnow() - timedelta(days=2), adet=3)
        await olay_yaz(app, kid, utcnow() - timedelta(days=20), adet=9)

        response = await auth_client.get("/api/v1/analytics/timeseries?days=7")

        assert response.status_code == 200
        assert response.json()["data"]["total_clicks"] == 3
        assert response.json()["data"]["days"] == 7
