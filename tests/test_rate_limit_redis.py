"""Hiz sinirinin Redis deposu.

NEDEN: bellek deposunda sinirlar SUREC BASINA. Olculdu -- hesap basina
10 yanlis sifre kuralinda, 60 denemeden sifre kontrolune ulasan
(429'lar yok sayilarak, gercek bir saldirgan gibi):

    1 isci -> 10     2 isci -> 20     4 isci -> 31-33

Redis deposu butun isciler icin tek sayac tutuyor. Buradaki testler
"iki isci" durumunu IKI AYRI HizSiniri ornegiyle kuruyor: her isci
kendi ornegini olusturuyor, paylastiklari tek sey Redis.

REDIS NEREDEN: TEST_REDIS_URL. Yerelde yoksa testler atlaniyor; CI'da
(CI ortam degiskeni varken) yoksa DUSUYOR -- sessizce atlanan bir
Redis testi, hic yazilmamis bir testten farksiz.
"""

import asyncio
import logging
import os
import uuid

import pytest
import pytest_asyncio

from core.rate_limit.limiter import HizSiniri

REDIS_URL = os.environ.get("TEST_REDIS_URL")

if not REDIS_URL:
    if os.environ.get("CI"):
        raise RuntimeError("CI'da TEST_REDIS_URL verilmeli (bkz. tests.yml)")
    pytest.skip("TEST_REDIS_URL yok; Redis testleri atlandi", allow_module_level=True)


# loop_scope="function": pytest.ini fikstur dongusunu oturum geneline
# ayarliyor, testler ise kendi donguleriyle kosuyor. Redis baglanti havuzu
# olustugu donguye bagli; kapatma baska bir dongude yapilirsa "Event loop
# is closed" veriyor. Fikstur testle ayni dongude kalmali.
@pytest_asyncio.fixture(loop_scope="function")
async def isciler():
    """Ayni Redis'i paylasan bagimsiz ornekler -- ayri surecler gibi."""
    olusanlar: list[HizSiniri] = []

    def yeni() -> HizSiniri:
        h = HizSiniri(REDIS_URL)
        olusanlar.append(h)
        return h

    yield yeni
    for h in olusanlar:
        await h.kapat()


def anahtar() -> str:
    # Testler ayni Redis'i paylasiyor; her test kendi anahtariyla.
    return f"test:{uuid.uuid4().hex}"


class TestTemelDavranis:
    async def test_limite_kadar_izin_sonra_red(self, isciler):
        h = isciler()
        a = anahtar()

        kararlar = [await h.dene(a, limit=3, pencere_sn=60) for _ in range(4)]

        assert [k.izinli for k in kararlar] == [True, True, True, False]
        assert [k.kalan for k in kararlar[:3]] == [3, 2, 1]
        assert 1 <= kararlar[3].yeniden_dene <= 61

    async def test_bak_saymiyor_isaretle_sayiyor(self, isciler):
        """Giris yalnizca BASARISIZLIGI sayiyor: bak + isaretle ayrimi
        bellek deposundakiyle ayni olmali."""
        h = isciler()
        a = anahtar()

        for _ in range(5):
            assert (await h.bak(a, limit=2, pencere_sn=60)).izinli

        await h.isaretle(a, pencere_sn=60)
        await h.isaretle(a, pencere_sn=60)

        assert not (await h.bak(a, limit=2, pencere_sn=60)).izinli

    async def test_pencere_dolunca_hak_geri_geliyor(self, isciler):
        h = isciler()
        a = anahtar()

        assert (await h.dene(a, limit=1, pencere_sn=1)).izinli
        assert not (await h.dene(a, limit=1, pencere_sn=1)).izinli
        await asyncio.sleep(1.1)
        assert (await h.dene(a, limit=1, pencere_sn=1)).izinli

    async def test_anahtar_suresi_doluyor(self, isciler):
        """Bos kalan anahtar Redis'te birikmemeli; bellekteki anahtar
        tavaninin karsiligi bu."""
        h = isciler()
        a = anahtar()
        await h.dene(a, limit=5, pencere_sn=60)

        ttl = await h._redis._istemci.pttl("hs:" + a)

        assert 0 < ttl <= 60_000


class TestIsciler:
    async def test_iki_isci_ayni_sayaci_goruyor(self, isciler):
        """ASIL MESELE. Bellek deposunda her isci 10'ar hak verirdi."""
        birinci, ikinci = isciler(), isciler()
        a = anahtar()

        for _ in range(5):
            assert (await birinci.dene(a, limit=10, pencere_sn=60)).izinli
        for _ in range(5):
            assert (await ikinci.dene(a, limit=10, pencere_sn=60)).izinli

        assert not (await birinci.dene(a, limit=10, pencere_sn=60)).izinli
        assert not (await ikinci.dene(a, limit=10, pencere_sn=60)).izinli

    async def test_es_zamanli_isteklerde_sinir_asilmiyor(self, isciler):
        """Kontrol ve isaretleme tek Lua betiginde. Ayri komutlar olsaydi
        birden fazla isci ayni anda "9 < 10" gorup hepsi isaretlerdi.

        5 isci, her biri 20 istek, hepsi AYNI ANDA; limit 10.
        """
        ornekler = [isciler() for _ in range(5)]
        a = anahtar()

        kararlar = await asyncio.gather(
            *(h.dene(a, limit=10, pencere_sn=60) for h in ornekler for _ in range(20))
        )

        assert sum(k.izinli for k in kararlar) == 10

    async def test_bellek_deposunda_ayni_durum_sinir_asiyor(self):
        """Karsilastirma: Redis'siz, ayni iki-isci senaryosu. Bu test
        duzeltmenin neyi degistirdigini belgeliyor."""
        birinci, ikinci = HizSiniri(), HizSiniri()
        a = anahtar()

        gecen = 0
        for h in (birinci, ikinci):
            for _ in range(10):
                gecen += (await h.dene(a, limit=10, pencere_sn=60)).izinli

        assert gecen == 20


class TestSifirlama:
    async def test_sifirla_yalnizca_kendi_anahtarlarini_siliyor(self, isciler):
        h = isciler()
        a = anahtar()
        await h.dene(a, limit=1, pencere_sn=60)
        await h._redis._istemci.set("baska:uygulama", "dokunma")

        await h.sifirla()

        assert (await h.dene(a, limit=1, pencere_sn=60)).izinli
        assert await h._redis._istemci.get("baska:uygulama") == b"dokunma"
        await h._redis._istemci.delete("baska:uygulama")


class TestRedisDusunce:
    async def test_redis_yoksa_bellege_dusup_yine_sinirliyor(self, caplog):
        """Kesinti sirasinda sinir SIFIRLANMAMALI (kaba kuvvete kapi) ve
        butun istekler de REDDEDILMEMELI (kimse giris yapamaz)."""
        # Dinleyen yok: baglanti hemen reddediliyor.
        h = HizSiniri("redis://127.0.0.1:1/0")
        a = anahtar()

        with caplog.at_level(logging.WARNING, logger="core.rate_limit.limiter"):
            kararlar = [await h.dene(a, limit=3, pencere_sn=60) for _ in range(4)]

        assert [k.izinli for k in kararlar] == [True, True, True, False]
        # Uyari kesinti boyunca her istekte degil, bir kez.
        assert caplog.text.count("Redis'e ulasamadi") == 1
        await h.kapat()

    async def test_redis_yoksa_giris_akisi_da_sinirlaniyor(self):
        """Giris dene degil bak + isaretle kullaniyor (yalnizca BASARISIZLIK
        sayiliyor). Geri dusus o iki yolda da calismali; yalnizca dene'yi
        olcmek, en cok korunmasi gereken ucu disarida birakirdi."""
        h = HizSiniri("redis://127.0.0.1:1/0")
        a = anahtar()

        for _ in range(3):
            assert (await h.bak(a, limit=3, pencere_sn=60)).izinli
            await h.isaretle(a, pencere_sn=60)

        assert not (await h.bak(a, limit=3, pencere_sn=60)).izinli
        await h.kapat()
