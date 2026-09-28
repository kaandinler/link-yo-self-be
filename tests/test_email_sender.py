"""E-posta gondericisinin GERCEK SMTP yolu.

NEDEN: core/email/sender.py kapsamda %61'deydi ve eksik kalan satirlar
tam olarak gercek gonderimdi -- yani uretimde sifre sifirlama ve e-posta
dogrulamayi tasiyan yol. Testler SMTP_HOST vermedigi icin gondericinin
yalnizca "log'a yaz" dali calisiyordu.

Olcum sirasinda bir de kusur cikti: gonderim senkrondu ve async uclarin
icinden cagriliyordu; SMTP konusmasi boyunca TUM sunucu duruyordu (bkz.
TestOlayDongusuBloklanmiyor).

Buradaki SMTP sunucusu taklit degil: aiosmtpd, gercek protokolu
konusan bir sunucu. smtplib'i taklit etmek, gondericinin smtplib'i
dogru kullandigini degil yalnizca cagirdigini olcerdi.
"""

import asyncio
import logging
import socket
import time
from email import message_from_bytes, policy

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from core.email.sender import EmailSender


class Toplayici:
    """Gelen mesajlari saklayan SMTP isleyicisi."""

    def __init__(self, gecikme: float = 0.0):
        self.mesajlar = []
        self.gecikme = gecikme

    async def handle_DATA(self, server, session, envelope):
        if self.gecikme:
            await asyncio.sleep(self.gecikme)
        self.mesajlar.append(
            {
                "kimden": envelope.mail_from,
                "kime": envelope.rcpt_tos,
                "mesaj": message_from_bytes(envelope.content, policy=policy.default),
                "kimlik": getattr(session, "auth_data", None),
            }
        )
        return "250 OK"


def dogrulayici(server, session, envelope, mechanism, auth_data):
    if isinstance(auth_data, LoginPassword) and (
        auth_data.login,
        auth_data.password,
    ) == (b"kullanici", b"parola"):
        return AuthResult(success=True)
    return AuthResult(success=False, handled=False)


def bos_port() -> int:
    """Isletim sisteminden bos bir port.

    aiosmtpd'nin Controller'i port=0 ile calismiyor: hazir oldugunu
    anlamak icin verilen porta baglanmayi deniyor.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def smtp_sunucusu(request):
    """Gercek bir SMTP sunucusu. Parametre: (gecikme, kimlik_dogrulama)."""
    gecikme, kimlik = getattr(request, "param", (0.0, False))
    isleyici = Toplayici(gecikme)
    secenekler = {}
    if kimlik:
        secenekler = {
            "authenticator": dogrulayici,
            # Testte TLS yok; kimlik dogrulamayi duz baglantida kabul et.
            "auth_require_tls": False,
        }
    port = bos_port()
    kontrol = Controller(isleyici, hostname="127.0.0.1", port=port, **secenekler)
    kontrol.start()
    try:
        yield isleyici, port
    finally:
        kontrol.stop()


def gonderici(port: int, **kw) -> EmailSender:
    ayar = {
        "host": "127.0.0.1",
        "port": port,
        "username": None,
        "password": None,
        "from_address": "no-reply@linkyoself.test",
        "use_tls": False,
    }
    ayar.update(kw)
    return EmailSender(**ayar)


class TestGercekGonderim:
    async def test_mesaj_gercekten_ulasiyor(self, smtp_sunucusu):
        isleyici, port = smtp_sunucusu

        await gonderici(port).send(
            to="ada@example.com",
            subject="Reset your LinkYoSelf password",
            body="Use the link below:\nhttps://ornek.test/x",
        )

        assert len(isleyici.mesajlar) == 1
        gelen = isleyici.mesajlar[0]
        assert gelen["kimden"] == "no-reply@linkyoself.test"
        assert gelen["kime"] == ["ada@example.com"]
        assert gelen["mesaj"]["Subject"] == "Reset your LinkYoSelf password"
        assert "https://ornek.test/x" in gelen["mesaj"].get_content()

    async def test_turkce_karakterler_bozulmuyor(self, smtp_sunucusu):
        """Kullanici adinda ya da metinde ı, ş, ğ olabilir; SMTP 7 bitlik
        bir protokol, kodlama yanlis yapilirsa alici "?" gorur."""
        isleyici, port = smtp_sunucusu

        await gonderici(port).send(
            to="seyma@example.com",
            subject="Şifre sıfırlama",
            body="Merhaba Şeyma, bağlantı ığüşöç",
        )

        mesaj = isleyici.mesajlar[0]["mesaj"]
        assert mesaj["Subject"] == "Şifre sıfırlama"
        assert "Merhaba Şeyma, bağlantı ığüşöç" in mesaj.get_content()

    @pytest.mark.parametrize("smtp_sunucusu", [(0.0, True)], indirect=True)
    async def test_kimlik_bilgisi_varsa_oturum_aciliyor(self, smtp_sunucusu):
        """Saglayicilarin neredeyse hepsi kimlik istiyor; login atlanirsa
        sunucu mesaji reddeder ve hata yalnizca log'da kalir."""
        isleyici, port = smtp_sunucusu

        await gonderici(port, username="kullanici", password="parola").send(
            to="ada@example.com", subject="x", body="y"
        )

        assert len(isleyici.mesajlar) == 1


class TestHataCagiraniEtkilemiyor:
    """Sifre sifirlama ucu, mail gidip gitmesinden bagimsiz AYNI yaniti
    donmeli; aksi halde hangi e-postalarin kayitli oldugu yanit farkindan
    anlasilir. Bu yuzden gonderim hatasi yukari cikmiyor -- ama log'a
    DUSUYOR."""

    async def test_ulasilamayan_sunucu_hata_firlatmiyor(self, caplog):
        # 1 numarali port: dinleyen yok, baglanti hemen reddediliyor.
        with caplog.at_level(logging.ERROR, logger="core.email.sender"):
            await gonderici(1).send(to="ada@example.com", subject="x", body="y")

        assert "E-posta gonderilemedi" in caplog.text
        assert "ada@example.com" in caplog.text

    async def test_tls_istenip_sunucu_desteklemiyorsa_hata_yutuluyor(
        self, smtp_sunucusu, caplog
    ):
        """use_tls=True STARTTLS istiyor; bu sunucu desteklemiyor. Mesaj
        GITMEMELI (duz metin gonderip "TLS istendi" ayarini sessizce
        ciğnemek en kotu sonuc olurdu) ve hata log'a dusmeli."""
        isleyici, port = smtp_sunucusu

        with caplog.at_level(logging.ERROR, logger="core.email.sender"):
            await gonderici(port, use_tls=True).send(
                to="ada@example.com", subject="x", body="y"
            )

        assert isleyici.mesajlar == []
        assert "E-posta gonderilemedi" in caplog.text

    async def test_yapilandirilmamissa_baglanti_kurulmuyor(self, caplog):
        with caplog.at_level(logging.WARNING, logger="core.email.sender"):
            await EmailSender(
                host=None,
                port=0,
                username=None,
                password=None,
                from_address="x@y",
                use_tls=False,
            ).send(to="ada@example.com", subject="Konu", body="Govde")

        assert "SMTP yapilandirilmamis" in caplog.text
        assert "Govde" in caplog.text


class TestOlayDongusuBloklanmiyor:
    """REGRESYON: SMTP konusmasi olay dongusunu durduruyordu.

    Gonderim senkron smtplib ile, async uclarin icinden yapiliyordu. Olculdu
    (gercek uygulama, HTTP uzerinden, her mesaji 2 sn'de kabul eden bir
    SMTP sunucusu): sifre sifirlama istegi havadayken atilan alakasiz bir
    GET / 1732 ms bekledi. Duzeltmeden sonra 6 ms.
    """

    @pytest.mark.parametrize("smtp_sunucusu", [(1.0, False)], indirect=True)
    async def test_gonderim_surerken_diger_isler_ilerliyor(self, smtp_sunucusu):
        _, port = smtp_sunucusu
        tik = 0

        async def saat():
            nonlocal tik
            while True:
                await asyncio.sleep(0.05)
                tik += 1

        gorev = asyncio.create_task(saat())
        t0 = time.perf_counter()
        await gonderici(port).send(to="ada@example.com", subject="x", body="y")
        sure = time.perf_counter() - t0
        gorev.cancel()

        # Gonderim ~1 sn surdu; o sirada 50 ms'lik saat ~20 kez atmali.
        # Dongu bloklansaydi 0-1 kez atardi.
        assert sure >= 0.9
        assert tik >= 10, f"gonderim sirasinda olay dongusu {tik} kez dondu"
