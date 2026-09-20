"""utils/referrer.py - referrer URL'inden gosterilebilir kaynak host'u.

Bu testler veritabanina dokunmuyor: fonksiyon saf ve hatalarinin cogu
(sema, port, "www.", cop girdi) tam burada yakalanabiliyor.
"""

import pytest

from utils.referrer import host_ayikla, kaynak_host


class TestHostAyikla:
    @pytest.mark.parametrize(
        ("adres", "beklenen"),
        [
            ("https://instagram.com/p/abc", "instagram.com"),
            # "www." atiliyor: ayni kaynagin iki satir olmasi gurultu.
            ("https://www.instagram.com/p/abc", "instagram.com"),
            # Yol ve sorgu kismi saklanmiyor.
            ("https://google.com/search?q=linkyoself&utm_source=x", "google.com"),
            # Port host'un parcasi degil.
            ("http://example.com:8080/a", "example.com"),
            # Buyuk harf normalize ediliyor.
            ("HTTPS://WWW.GOOGLE.COM/", "google.com"),
            # Mobil uygulamalarin urettigi referrer da bir kaynak.
            ("android-app://com.instagram.android", "com.instagram.android"),
            # Tek etiketli host gecerli (gelistirme ortami).
            ("http://localhost:3000/en/kaan", "localhost"),
            # Sema unutulmus olabilir; tarayici boyle gondermiyor ama API'yi
            # elle cagiran biri gonderebilir.
            ("instagram.com/p/abc", "instagram.com"),
        ],
    )
    def test_host_cikariliyor(self, adres, beklenen):
        assert host_ayikla(adres) == beklenen

    @pytest.mark.parametrize(
        "adres",
        [
            None,
            "",
            "   ",
            # Host yok.
            "hello world",
            # Sema var ama host yok: "javascript" bir kaynak degil.
            "javascript:void(0)",
            "mailto:biri@example.com",
            # IPv6: panoda anlamsiz, "Direct" saymak dogru.
            "http://[::1]:8000/x",
        ],
    )
    def test_ayrastirilamayan_girdi_none(self, adres):
        assert host_ayikla(adres) is None

    def test_kolona_sigmayan_host_eleniyor(self):
        # Kirpmak uydurma bir alan adi yaratirdi.
        assert host_ayikla("https://" + "a" * 300 + ".com/x") is None


class TestKaynakHost:
    def test_dis_site_korunuyor(self):
        assert (
            kaynak_host("https://instagram.com/p/abc", ic_hostlar={"linkyoself.com"})
            == "instagram.com"
        )

    def test_site_ici_gezinme_dogrudan_sayiliyor(self):
        # Kendi ana sayfamizdan gelmek bir trafik kaynagi degil; listede en
        # ust sirada kendi alan adimizi gormek paneli yaniltirdi.
        assert (
            kaynak_host(
                "https://linkyoself.com/en/welcome", ic_hostlar={"linkyoself.com"}
            )
            is None
        )

    def test_ic_host_karsilastirmasi_normalize_edilmis_deger_uzerinden(self):
        # kendi_hostlarimiz() da host_ayikla'dan geciyor, yani "www." ve
        # buyuk harf iki tarafta da ayni sekilde temizleniyor.
        assert (
            kaynak_host("https://WWW.linkyoself.com/en", ic_hostlar={"linkyoself.com"})
            is None
        )

    def test_referrer_yoksa_none(self):
        assert kaynak_host("", ic_hostlar={"linkyoself.com"}) is None
