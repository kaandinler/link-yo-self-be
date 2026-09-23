"""E-posta gonderimi.

SMTP ayarlari verilmemisse (gelistirme ortami) e-posta gonderilmez, icerik
log'a yazilir. Boylece sifre sifirlama akisi bir SMTP saglayicisi secilmeden
de uctan uca calisir ve test edilebilir; canliya cikarken settings'e SMTP
bilgilerini girmek yeterli.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from settings import settings

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(
        self,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        from_address: str,
        use_tls: bool,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.use_tls = use_tls

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    async def send(self, to: str, subject: str, body: str) -> None:
        """E-postayi gonderir; SMTP yapilandirilmamissa log'a yazar.

        Gonderim hatasi cagiran tarafa yansitilmaz: sifre sifirlama ucu, mail
        gidip gitmediginden bagimsiz olarak ayni yaniti donmeli (bkz.
        AuthService.request_password_reset).

        NEDEN ASYNC + IS PARCACIGI: smtplib senkron. Onceki hali async
        uclarin icinden dogrudan cagriliyordu, yani SMTP konusmasi boyunca
        OLAY DONGUSU DURUYORDU -- o surede sunucu baska hicbir kullaniciya
        yanit vermiyordu. Olculdu: her mesaji 2 sn'de kabul eden bir SMTP
        sunucusuyla, sifre sifirlama istegi havadayken atilan alakasiz bir
        GET / 1732 ms bekledi. Gercek bir saglayicida bir gonderim
        genellikle 0,5-2 sn; askida kalan bir sunucuda timeout (10 sn)
        her socket islemi icin ayri isliyor.

        Konusma artik asyncio.to_thread ile ayri bir is parcaciginda;
        cagiran istek yine gonderimin bitmesini bekliyor (davranis ayni),
        ama digerleri beklemiyor.
        """
        if not self.is_configured:
            logger.warning(
                "SMTP yapilandirilmamis, e-posta gonderilmedi. "
                "Alici: %s | Konu: %s\n%s",
                to,
                subject,
                body,
            )
            return

        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            await asyncio.to_thread(self._smtp_ile_gonder, message)
        except Exception:
            logger.exception("E-posta gonderilemedi. Alici: %s", to)

    def _smtp_ile_gonder(self, message: EmailMessage) -> None:
        """SMTP konusmasinin kendisi. Bloklayici; olay dongusunde CAGRILMAZ."""
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


def build_email_sender() -> EmailSender:
    return EmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_address=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )
