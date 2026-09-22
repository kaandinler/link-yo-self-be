"""Tiklama tekillestirme.

NEDEN: olculdu, tekillestirme yokken tek bir ziyaretcinin ~2 saniyede
yaptigi 10 istek 10 tiklama olarak sayiliyordu. Cift tiklama, sabirsiz
tekrar dokunuslar ve geri gelip yeniden tiklama, sahibinin gordugu
sayiyi oldugundan buyuk gosteriyordu.

Burada olculen iki sey birlikte anlamli:
  1. Tekrarlanan tiklama SAYILMIYOR.
  2. Ziyaretci YINE DE hedefe gidiyor -- her yanit 200 ve redirect_url
     tasiyor. Sadece birincisini olcen bir test, ziyaretcinin linke
     gitmesini engelleyen bozuk bir uygulamadan da gecerdi.
"""

import asyncio

import pytest

from tests.test_links import create_link


async def _tikla(client, link_id: int, referrer: str | None = None):
    return await client.post(
        f"/api/v1/links/{link_id}/click", json={"referrer": referrer}
    )


async def _sayac(client, link_id: int) -> int:
    linkler = (await client.get("/api/v1/links/")).json()["data"]
    return next(link["click_count"] for link in linkler if link["id"] == link_id)


@pytest.mark.asyncio
class TestTekillestirme:
    async def test_ayni_ziyaretcinin_tekrari_sayilmiyor(self, auth_client):
        client = auth_client
        link = await create_link(client)

        yanitlar = [await _tikla(client, link["id"]) for _ in range(10)]

        assert await _sayac(client, link["id"]) == 1

        # ...ama hicbiri reddedilmedi ve hepsi hedefi verdi.
        assert [y.status_code for y in yanitlar] == [200] * 10
        for yanit in yanitlar:
            assert yanit.json()["data"]["redirect_url"] == link["url"]

    async def test_farkli_linkler_ayri_sayiliyor(self, auth_client):
        """Anahtar linke ozel.

        Tek bir "bu ziyaretci tikladi" anahtari da ilk testi gecerdi
        ama ayni kisinin iki farkli linke tiklamasini tek tiklama
        sayardi -- yani link kirilimi bozulurdu.
        """
        client = auth_client
        birinci = await create_link(client)
        ikinci = await create_link(client, title="Ikinci", url="https://ornek.test/2")

        await _tikla(client, birinci["id"])
        await _tikla(client, ikinci["id"])

        assert await _sayac(client, birinci["id"]) == 1
        assert await _sayac(client, ikinci["id"]) == 1

    async def test_olay_da_tekillestiriliyor(self, auth_client):
        """Sayac ve olay BIRLIKTE atlanmali.

        Pano toplami sayactan, "son N gun" grafigi olaylardan okuyor.
        Yalnizca biri tekillestirilseydi iki ekran farkli sayi
        gosterirdi ve hangisinin dogru oldugu belirsiz kalirdi.
        """
        client = auth_client
        link = await create_link(client)

        for _ in range(5):
            await _tikla(client, link["id"])

        seri = (await client.get("/api/v1/analytics/timeseries?days=1")).json()["data"]

        assert seri["total_clicks"] == 1
        assert await _sayac(client, link["id"]) == 1

    async def test_pencere_dolunca_yeniden_sayiliyor(self, auth_client, monkeypatch):
        """Tekillestirme kalici bir engel degil, kayan bir pencere.

        Pencere hic dolmasaydi bir ziyaretci bir linke omur boyu tek
        kez tiklayabilirdi; ertesi gun gelen ayni kisi sayilmazdi.
        """
        from settings import settings as ayarlar

        monkeypatch.setattr(ayarlar, "click_dedup_seconds", 1)
        client = auth_client
        link = await create_link(client)

        await _tikla(client, link["id"])
        await _tikla(client, link["id"])
        assert await _sayac(client, link["id"]) == 1

        await asyncio.sleep(1.2)
        await _tikla(client, link["id"])

        assert await _sayac(client, link["id"]) == 2

    async def test_kapatilabiliyor(self, auth_client, monkeypatch):
        """0 = kapali.

        Anahtar calismiyorsa bir ise yaramaz; varligini degil etkisini
        olcuyoruz.
        """
        from settings import settings as ayarlar

        monkeypatch.setattr(ayarlar, "click_dedup_seconds", 0)
        client = auth_client
        link = await create_link(client)

        for _ in range(4):
            await _tikla(client, link["id"])

        assert await _sayac(client, link["id"]) == 4

    async def test_farkli_ziyaretciler_ayri_sayiliyor(self, auth_client, monkeypatch):
        """ASIL RISK BU TESTTE.

        Tekillestirme fazla genis olsaydi -- ornegin anahtar yalnizca
        link olsaydi -- "tekrar sayilmiyor" testleri yine gecerdi ama
        urun bozulurdu: ayni linke tiklayan HERKES tek kisi sayilirdi.

        Farkli ziyaretciler X-Forwarded-For ile benzetiliyor; bunun
        okunabilmesi icin guvenilir vekil sayisi 1 yapiliyor (varsayilan
        0 ve basligin varsayilan olarak OKUNMADIGI ayrica test ediliyor,
        bkz. test_rate_limit.py).
        """
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 1)
        client = auth_client
        link = await create_link(client)

        for adres in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
            yanit = await client.post(
                f"/api/v1/links/{link['id']}/click",
                json={"referrer": None},
                headers={"X-Forwarded-For": adres},
            )
            assert yanit.status_code == 200

        assert await _sayac(client, link["id"]) == 3
