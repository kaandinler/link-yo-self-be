"""Hiz siniri.

NEDEN BU DOSYA: sinir eklenmeden once olculdu, hicbir uc korunmuyordu
-- 30 yanlis sifre denemesinin hepsi 401 dondu, tek bir 429 yok; 20
sifre sifirlama istegi 20 e-posta uretti; 15 kayit denemesinin 15'i de
hesap acti.

Bu testlerin isi iki sey: sinirin GERCEKTEN calistigi ve mesru
kullanimi BOZMADIGI. Ikincisi olmadan birincisi tehlikeli -- her seyi
reddeden bir sinirlayici da butun "429 dondu mu" testlerini gecerdi.
"""

import pytest

from core.rate_limit import GIRIS_HESAP, KAYIT_IP, SIFIRLAMA_HESAP
from tests.conftest import DEFAULT_USER, register_user, yakala_epostalar


async def _giris_dene(client, sifre: str, eposta: str | None = None):
    return await client.post(
        "/api/v1/auth/token",
        data={
            "username": eposta or DEFAULT_USER["email"],
            "password": sifre,
        },
    )


@pytest.mark.asyncio
class TestGiris:
    async def test_yanlis_sifre_limiti_dolunca_429(self, client):
        await register_user(client)

        kodlar = [
            (await _giris_dene(client, f"Yanlis{i}1")).status_code
            for i in range(GIRIS_HESAP.limit + 1)
        ]

        # Ilk `limit` deneme normal sekilde reddediliyor...
        assert kodlar[:-1] == [401] * GIRIS_HESAP.limit, kodlar
        # ...sonraki artik degerlendirilmiyor.
        assert kodlar[-1] == 429, kodlar

    async def test_429_retry_after_tasiyor(self, client):
        """Istemcinin ne zaman yeniden deneyecegini bilmesi gerekiyor."""
        await register_user(client)

        for i in range(GIRIS_HESAP.limit):
            await _giris_dene(client, f"Yanlis{i}1")

        yanit = await _giris_dene(client, "Yanlis999")

        assert yanit.status_code == 429
        assert "retry-after" in yanit.headers
        assert int(yanit.headers["retry-after"]) > 0

    async def test_basarili_girisler_sayilmiyor(self, client):
        """ASIL KRITIK TEST.

        Sinir her istegi saysaydi, sik giris yapan mesru bir kullanici
        kendini disari kilitlerdi -- ve bu, urunu gunluk kullanimda
        bozan bir gerileme olurdu. Limitin iki kati kadar DOGRU giris
        yapiliyor; hicbiri sayilmamali.
        """
        await register_user(client)

        kodlar = [
            (await _giris_dene(client, DEFAULT_USER["password"])).status_code
            for _ in range(GIRIS_HESAP.limit * 2)
        ]

        assert kodlar == [200] * (GIRIS_HESAP.limit * 2), kodlar

    async def test_bir_hesabin_limiti_digerini_etkilemiyor(self, client):
        """Anahtarlar gercekten ayri mi.

        Tek bir global sayac da "limit dolunca 429" testini gecerdi ama
        bir kullanicinin hatalari butun kullanicilari disari atardi.
        """
        await register_user(client)
        await register_user(client, username="baskasi", email="baskasi@example.com")

        for i in range(GIRIS_HESAP.limit + 1):
            await _giris_dene(client, f"Yanlis{i}1")

        # Ilk hesap kilitli...
        assert (await _giris_dene(client, "Yanlis!1")).status_code == 429
        # ...ikincisi etkilenmemis.
        ikinci = await _giris_dene(
            client, DEFAULT_USER["password"], eposta="baskasi@example.com"
        )
        assert ikinci.status_code == 200

    async def test_x_forwarded_for_koru_korune_guvenilmiyor(self, client):
        """SINIRIN TIYATRO OLMADIGINI OLCEN TEST.

        Basligi istemci uydurabilir. Sinirlayici ona koru korune
        guvenseydi, her istekte farkli bir deger yazan saldirgan IP
        katmanini tamamen atlatirdi. Varsayilan yapilandirmada
        (trusted_proxy_count = 0) baslik hic okunmuyor.

        Burada hesap katmani devrede kaliyor ve zaten yetiyor; olculen
        sey, uydurma basligin sinirdan KACIRMADIGI.
        """
        await register_user(client)

        kodlar = []
        for i in range(GIRIS_HESAP.limit + 1):
            yanit = await client.post(
                "/api/v1/auth/token",
                data={"username": DEFAULT_USER["email"], "password": f"Yanlis{i}1"},
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )
            kodlar.append(yanit.status_code)

        assert kodlar[-1] == 429, kodlar


@pytest.mark.asyncio
class TestSifreSifirlama:
    async def test_limit_dolunca_eposta_gitmiyor(self, client, app):
        """429 dondurup e-postayi yine de gondermek ise yaramazdi.

        Bu ucun bedeli yanitin kendisi degil, uretilen posta: adresin
        sahibi onu yiyor ve saglayicinin gozunde gonderen itibarimiz
        dusuyor. O yuzden olculen sey durum kodu DEGIL, gonderim.
        """
        await register_user(client)

        with yakala_epostalar(app) as gonderilen:
            for _ in range(SIFIRLAMA_HESAP.limit):
                yanit = await client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": DEFAULT_USER["email"]},
                )
                assert yanit.status_code == 204

            izin_verilen = len(gonderilen)

            asilan = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": DEFAULT_USER["email"]},
            )

        assert asilan.status_code == 429
        assert len(gonderilen) == izin_verilen, (
            "limit asildiktan sonra e-posta gonderilmemeli"
        )

    async def test_kayitli_olmayan_adres_de_sinirlaniyor(self, client):
        """Sinir, adresin kayitli olup olmadigini SIZDIRMIYOR.

        Sayac cagiranin kendi istek sayisina bakiyor; kayitli olmayan
        bir adres de ayni esikte 429 aliyor. Farkli davransaydi, uc
        adres dogrulama aracina donerdi -- ucun 204 donmesindeki
        ozenin tam tersi.
        """
        kodlar = []
        for _ in range(SIFIRLAMA_HESAP.limit + 1):
            yanit = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "hic-kayitli-degil@example.com"},
            )
            kodlar.append(yanit.status_code)

        assert kodlar[:-1] == [204] * SIFIRLAMA_HESAP.limit, kodlar
        assert kodlar[-1] == 429, kodlar


@pytest.mark.asyncio
class TestKayit:
    async def test_limit_dolunca_hesap_acilmiyor(self, client):
        kodlar = []
        for i in range(KAYIT_IP.limit + 1):
            yanit = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"spam{i}",
                    "email": f"spam{i}@example.com",
                    "password": "Secret123",
                },
            )
            kodlar.append(yanit.status_code)

        assert kodlar[:-1] == [201] * KAYIT_IP.limit, kodlar
        assert kodlar[-1] == 429, kodlar


class TestIstemciAdresi:
    """X-Forwarded-For nasil cozuluyor.

    NEDEN AYRI VE AYRINTILI: burasi sinirin guvenlik mantiginin
    tamami. Yanlis elemani almak, saldirganin yazabildigi bir degere
    guvenmek demek ve sinirlayici tamamen atlatilir -- uc hala 429
    dondurdugu icin de gerileme sessiz olur. Ilk olcumde bu dosyanin
    kapsami %71'di ve kapsanmayan satirlar tam olarak bunlardi.
    """

    @staticmethod
    def _istek(baslik: str | None = None, adres: str | None = "203.0.113.9"):
        from starlette.requests import Request

        basliklar = []
        if baslik is not None:
            basliklar.append((b"x-forwarded-for", baslik.encode()))

        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": basliklar,
                "client": (adres, 1234) if adres else None,
            }
        )

    def test_vekil_yokken_baslik_okunmuyor(self, monkeypatch):
        """Varsayilan davranis.

        Baslik dolu ve tamamen uydurma; yine de baglantinin kendi
        adresi kullanilmali. Aksi halde her istekte farkli bir deger
        yazan saldirgan IP katmanini bedavaya atlatirdi.
        """
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 0)

        assert keys._ham_ip(self._istek("1.2.3.4, 5.6.7.8")) == "203.0.113.9"

    def test_tek_vekilde_SAGDAKI_aliniyor(self, monkeypatch):
        """Soldaki degil sagdaki.

        Vekiller gordukleri adresi SAGA ekliyor. Soldaki eleman
        istemcinin kendi yazdigi sey olabilir; guvenilir vekilimizin
        gordugu adres en sagdaki.
        """
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 1)

        # "1.2.3.4" saldirganin uydurmasi, "198.51.100.7" vekilimizin gordugu.
        assert keys._ham_ip(self._istek("1.2.3.4, 198.51.100.7")) == "198.51.100.7"

    def test_iki_vekilde_sagdan_ikinci(self, monkeypatch):
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 2)

        adres = keys._ham_ip(self._istek("1.2.3.4, 198.51.100.7, 10.0.0.1"))
        assert adres == "198.51.100.7"

    def test_baslik_beklenenden_kisa_ise_baglantiya_dusuluyor(self, monkeypatch):
        """Guvenli tarafa dusme.

        Iki vekil bekleniyor ama baslikta tek eleman var -- yani zincir
        beklendigi gibi degil. O tek elemani almak, saldirganin
        yazdigina guvenmek olurdu.
        """
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 2)

        assert keys._ham_ip(self._istek("1.2.3.4")) == "203.0.113.9"

    def test_adres_hic_yoksa_sabit_anahtar(self, monkeypatch):
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 0)

        assert keys._ham_ip(self._istek(adres=None)) == keys.BILINMEYEN

    def test_anahtar_ham_adresi_tasimiyor(self, monkeypatch):
        """Anahtarda IP'nin kendisi gorunmemeli."""
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 0)

        anahtar = keys.ip_anahtari(self._istek(), "giris")

        assert "203.0.113.9" not in anahtar
        assert anahtar.startswith("giris:ip:")

    def test_ayni_adres_ayni_anahtar(self, monkeypatch):
        """Ozet olmasi sayimi bozmamali."""
        from core.rate_limit import keys

        monkeypatch.setattr(keys.settings, "trusted_proxy_count", 0)

        assert keys.ip_anahtari(self._istek(), "giris") == keys.ip_anahtari(
            self._istek(), "giris"
        )
        assert keys.ip_anahtari(self._istek(), "giris") != keys.ip_anahtari(
            self._istek(adres="198.51.100.1"), "giris"
        )


@pytest.mark.asyncio
class TestKapatmaAnahtari:
    async def test_kapaliyken_sinir_uygulanmiyor(self, client, monkeypatch):
        """Yuk testi icin kapatilabiliyor.

        Anahtar calismiyorsa bir ise yaramaz; varligini degil etkisini
        olcuyoruz.
        """
        from core.rate_limit import deps

        await register_user(client)
        monkeypatch.setattr(deps.settings, "rate_limit_enabled", False)

        kodlar = [
            (await _giris_dene(client, f"Yanlis{i}1")).status_code
            for i in range(GIRIS_HESAP.limit + 5)
        ]

        assert 429 not in kodlar, kodlar

    async def test_kapaliyken_kayit_ve_sifirlama_da_serbest(self, client, monkeypatch):
        """FE'nin E2E is akisi RATE_LIMIT_ENABLED=false ile kosuyor, cunku
        yuzlerce test kullanicisi kaydediyor ve kayit siniri onlari
        dusuruyordu. Anahtar yalnizca giriste calissaydi o is akisi
        yeniden kirilirdi -- ve bu yol daha once hic olculmemisti."""
        from core.rate_limit import deps

        monkeypatch.setattr(deps.settings, "rate_limit_enabled", False)

        kayitlar = [
            (
                await client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": f"kapali{i}",
                        "email": f"kapali{i}@example.com",
                        "password": "Secret123",
                    },
                )
            ).status_code
            for i in range(KAYIT_IP.limit + 3)
        ]
        sifirlamalar = [
            (
                await client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": "kapali0@example.com"},
                )
            ).status_code
            for _ in range(SIFIRLAMA_HESAP.limit + 3)
        ]

        assert 429 not in kayitlar, kayitlar
        assert 429 not in sifirlamalar, sifirlamalar


class TestBellekTavani:
    """Sayac belleginin saldirgan tarafindan buyutulememesi.

    NEDEN: her yeni IP yeni bir anahtar demek ve IP dondurmek ucuz.
    Tavan olmasaydi, sinirlayicinin kendisi bir bellek tuketme
    saldirisina donerdi -- yani korumak icin eklenen sey yeni bir acik
    olurdu.
    """

    def test_tavan_asilmiyor(self):
        from core.rate_limit.limiter import BellekDeposu

        h = BellekDeposu(anahtar_tavani=10)

        for i in range(200):
            h.dene(f"ip-{i}", limit=5, pencere_sn=60)

        assert len(h._damgalar) <= 10

    def test_once_bosalmis_anahtarlar_atiliyor(self):
        """Eskimis kayitlar, hala canli olanlardan once gitmeli.

        Aksi halde tavan dolunca aktif bir kullanicinin sayaci
        silinirdi ve sinir onun icin sifirlanirdi.
        """
        from core.rate_limit.limiter import BellekDeposu

        h = BellekDeposu(anahtar_tavani=3)

        # Suresi cok kisa: damgalar hemen eskiyor.
        h.dene("eski-1", limit=5, pencere_sn=0)
        h.dene("eski-2", limit=5, pencere_sn=0)
        # Bu anahtar canli kalmali.
        h.dene("canli", limit=5, pencere_sn=3600)

        # Tavani zorla: yeni anahtar eklenirken yer acilir.
        h.dene("yeni", limit=5, pencere_sn=3600)

        assert "canli" in h._damgalar
        assert len(h._damgalar) <= 3

    def test_suresi_gecen_damga_hak_geri_veriyor(self):
        """Pencere kayiyor mu -- sinirin kalici bir yasak olmadigi."""
        from core.rate_limit.limiter import BellekDeposu

        h = BellekDeposu()

        assert h.dene("a", limit=1, pencere_sn=0).izinli
        # pencere_sn=0 ile onceki damga aninda eskiyor.
        assert h.dene("a", limit=1, pencere_sn=0).izinli

    def test_suresi_dolmus_anahtar_canli_sayactan_once_gidiyor(self):
        """REGRESYON: tavan dolunca CANLI bir sayac siliniyor ve hakki
        sifirlaniyordu. Yalnizca kuyrugu bos anahtarlar "suresi dolmus"
        sayiliyordu; kuyruk ise ancak dokunulunca temizleniyor. Ayrica
        "en eski dokunulan" aslinda en eski EKLENENDI.
        """
        import time

        from core.rate_limit.limiter import BellekDeposu

        h = BellekDeposu(anahtar_tavani=3)
        h.dene("canli", limit=1, pencere_sn=3600)  # hakki bitti
        h.dene("eski-1", limit=5, pencere_sn=1)
        h.dene("eski-2", limit=5, pencere_sn=1)
        time.sleep(1.1)  # eskilerin suresi doldu, kuyruklari hala dolu

        h.dene("yeni", limit=5, pencere_sn=3600)  # tavan dolu -> yer ac

        assert not h.dene("canli", limit=1, pencere_sn=3600).izinli

    def test_dokunulan_anahtar_tahliye_sirasinda_one_gecmiyor(self):
        """Hicbiri suresi dolmamisken, en uzun suredir DOKUNULMAYAN gider.
        Aktif bir saldirinin sayaci en son dokunulandir; o korunmali."""
        from core.rate_limit.limiter import BellekDeposu

        h = BellekDeposu(anahtar_tavani=3)
        h.dene("hedef", limit=1, pencere_sn=3600)
        h.dene("b", limit=5, pencere_sn=3600)
        h.dene("c", limit=5, pencere_sn=3600)
        h.dene("hedef", limit=1, pencere_sn=3600)  # saldirgan tekrar denedi

        h.dene("d", limit=5, pencere_sn=3600)  # tavan dolu, suresi dolan yok

        assert "b" not in h._damgalar
        assert not h.dene("hedef", limit=1, pencere_sn=3600).izinli
