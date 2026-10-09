"""Depo uygulamalari (core/storage)."""

import boto3
import pytest
from moto import mock_aws

from core.storage import avatar_anahtari, avatar_anahtari_mi, depo_olustur
from core.storage.s3 import S3Depo
from core.storage.yerel import YerelDepo
from settings import settings


class TestAnahtar:
    def test_uretilen_anahtar_kaliba_uyuyor(self):
        assert avatar_anahtari_mi(avatar_anahtari(7, "jpg"), 7)

    def test_her_seferinde_yeni_ad(self):
        assert avatar_anahtari(7, "jpg") != avatar_anahtari(7, "jpg")

    @pytest.mark.parametrize(
        "anahtar",
        [
            "avatars/8/" + "a" * 32 + ".jpg",  # baska kullanici
            "avatars/7/../8/" + "a" * 32 + ".jpg",
            "avatars/7/" + "a" * 32 + ".webp",  # uretilmeyen tur
            "avatars/7/" + "a" * 32 + ".jpg.html",
            "avatars/7/kisa.jpg",
            "../avatars/7/" + "a" * 32 + ".jpg",
            "",
        ],
    )
    def test_kalip_disi_reddediliyor(self, anahtar):
        assert not avatar_anahtari_mi(anahtar, 7)


class TestAnahtarBul:
    depo = YerelDepo("/tmp/kullanilmiyor", "https://cdn.example.com/media/")

    def test_kendi_adresi(self):
        anahtar = avatar_anahtari(3, "png")
        assert self.depo.anahtar_bul(self.depo.adres(anahtar), 3) == anahtar

    @pytest.mark.parametrize(
        "adres",
        [
            None,
            "",
            "https://example.com/a.png",
            # onek benziyor ama ayni kok degil
            "https://cdn.example.com/mediax/avatars/3/" + "a" * 32 + ".jpg",
            "https://cdn.example.com/media/avatars/4/" + "a" * 32 + ".jpg",
        ],
    )
    def test_baskasinin_ya_da_dis_adres(self, adres):
        assert self.depo.anahtar_bul(adres, 3) is None


class TestYerelDepo:
    async def test_kaydet_ve_sil(self, tmp_path):
        depo = YerelDepo(str(tmp_path), "http://x/media")
        anahtar = avatar_anahtari(1, "jpg")

        adres = await depo.kaydet(anahtar, b"veri", "image/jpeg")

        assert adres == f"http://x/media/{anahtar}"
        assert (tmp_path / anahtar).read_bytes() == b"veri"
        # Gecici dosya kalmiyor.
        assert [p.name for p in (tmp_path / anahtar).parent.iterdir()] == [
            anahtar.rsplit("/", 1)[1]
        ]

        await depo.sil(anahtar)
        assert not (tmp_path / anahtar).exists()
        await depo.sil(anahtar)  # olmayan dosya hata vermiyor

    async def test_kok_disina_yazilamiyor(self, tmp_path):
        depo = YerelDepo(str(tmp_path / "kok"), "http://x/media")
        with pytest.raises(ValueError):
            await depo.kaydet("../disarida.jpg", b"x", "image/jpeg")
        assert not (tmp_path / "disarida.jpg").exists()


@pytest.fixture
def s3_kova():
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="avatarlar")
        yield "avatarlar"


class TestS3Depo:
    async def test_kaydet_ve_sil(self, s3_kova):
        depo = S3Depo(
            kova=s3_kova, kok_adres="https://cdn.example.com/", bolge="us-east-1"
        )
        istemci = boto3.client("s3", region_name="us-east-1")
        anahtar = avatar_anahtari(5, "jpg")

        adres = await depo.kaydet(anahtar, b"jpeg", "image/jpeg")

        assert adres == f"https://cdn.example.com/{anahtar}"
        nesne = istemci.get_object(Bucket=s3_kova, Key=anahtar)
        assert nesne["Body"].read() == b"jpeg"
        assert nesne["ContentType"] == "image/jpeg"
        assert "immutable" in nesne["CacheControl"]

        await depo.sil(anahtar)
        assert istemci.list_objects_v2(Bucket=s3_kova).get("KeyCount") == 0
        await depo.sil(anahtar)  # olmayan nesne hata vermiyor


class TestDepoOlustur:
    def test_varsayilan_yerel(self):
        assert isinstance(depo_olustur(), YerelDepo)

    def test_s3_eksik_ayarla_baslamiyor(self, monkeypatch):
        monkeypatch.setattr(settings, "storage_backend", "s3")
        monkeypatch.setattr(settings, "s3_bucket", "kova")
        monkeypatch.setattr(settings, "s3_public_url", None)
        with pytest.raises(RuntimeError, match="S3_PUBLIC_URL"):
            depo_olustur()

    def test_s3(self, monkeypatch):
        monkeypatch.setattr(settings, "storage_backend", "s3")
        monkeypatch.setattr(settings, "s3_bucket", "kova")
        monkeypatch.setattr(settings, "s3_public_url", "https://cdn.example.com")
        monkeypatch.setattr(settings, "s3_region", "auto")
        depo = depo_olustur()
        assert isinstance(depo, S3Depo)
        assert depo.kok_adres == "https://cdn.example.com"
