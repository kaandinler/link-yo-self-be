"""utils/time_utils.utcnow testleri.

NEDEN BU KUCUK FONKSIYON TEST EDILIYOR: donusunun saat dilimli olmasi
bir ayrinti degil, bu kodun her yerinde varsayilan bir sozlesme. Token
son kullanma kontrolleri (refresh_token, password_reset,
email_verification) ve analytics zaman araliklari, veritabanindan gelen
degerle utcnow()'i karsilastiriyor. Fonksiyon bir gun naive bir deger
dondurmeye baslarsa hata "TypeError: can't compare offset-naive and
offset-aware datetimes" olarak, uc farkli akista birden cikar -- ve
sebebi buradaki tek satir olur.

Modulde ayrica hicbir yerden cagrilmayan bir `format_datetime` vardi;
olu kod oldugu icin kaldirildi (kullanim aramasi: yalnizca kendi
tanimi).
"""

from datetime import UTC, datetime, timedelta

from utils.time_utils import utcnow


class TestUtcnow:
    def test_saat_dilimi_bilgisi_TASIYOR(self):
        """Asil sozlesme bu: naive deger donmuyor."""
        simdi = utcnow()

        assert simdi.tzinfo is not None
        assert simdi.utcoffset() == timedelta(0)

    def test_saat_dilimli_bir_degerle_karsilastirilabiliyor(self):
        """Naive bir deger burada TypeError verirdi."""
        gecmis = datetime(2020, 1, 1, tzinfo=UTC)

        assert utcnow() > gecmis

    def test_gercekten_su_ani_veriyor(self):
        """Sabit ya da kaymis bir deger donmedigini olcuyor."""
        once = datetime.now(UTC)
        olculen = utcnow()
        sonra = datetime.now(UTC)

        assert once <= olculen <= sonra

    def test_ilerliyor(self):
        """Ardisik iki cagri geriye gitmiyor."""
        birinci = utcnow()
        ikinci = utcnow()

        assert ikinci >= birinci
