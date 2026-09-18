"""Ilk admini olusturur (ya da var olan bir kullaniciyi admin yapar).

NEDEN GEREKIYOR: admin olusturmanin tek yolu admin panelinden gecmek,
panele girmenin tek yolu da admin olmak. Self-servis kayit ucunda
`is_admin` bilincli olarak yok -- olsaydi herkes kendini admin yapardi
(bkz. UserCreateAdmin). Yani bos bir veritabaninda panele hic kimse
giremiyordu; ilk admini acmanin yolu elle SQL yazmakti.

Bu betik o bosluğu dolduruyor. Surecin icinden degil, sunucuya erisimi
olan birinin elinden calisiyor: HTTP yuzeyine yeni bir sey acmiyor.

Kullanim:

    python -m scripts.create_admin --username kaan \
        --email kaan@example.com --password 'Gizli.Parola1'

Ya da ortam degiskenleriyle (CI icin daha rahat):

    ADMIN_USERNAME=... ADMIN_EMAIL=... ADMIN_PASSWORD=... \
        python -m scripts.create_admin

Ayni degerlerle ikinci kez calistirmak guvenli: kullanici varsa
yeniden olusturulmuyor, yalnizca admin degilse admin yapiliyor. Bu
yuzden kurulum betiklerine ve CI adimlarina konabiliyor.
"""

import argparse
import asyncio
import os
import sys

from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.auth.password import hash_password
from core.validators import validate_password, validate_username
from models import User
from settings import settings


class _EPosta(BaseModel):
    """E-postayi uygulamanin kendi kuraliyla dogrular.

    NEDEN: ilk denemede `example.test` ile bir admin acildi ve betik
    memnuniyetle "olusturuldu" dedi; sonra /users/ ucu 500 verdi, cunku
    yanit modelindeki EmailStr `.test`i kabul etmiyor. Betigin gecirdigi
    bir kaydi API'nin serilestirememesi, hatayi kurulumdan cok sonra ve
    alakasiz bir yerde gosteriyordu.
    """

    adres: EmailStr


def _arguman_coz() -> argparse.Namespace:
    ayristirici = argparse.ArgumentParser(
        description="Ilk admin kullanicisini olusturur ya da var olani admin yapar.",
    )
    ayristirici.add_argument("--username", default=os.getenv("ADMIN_USERNAME"))
    ayristirici.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    # NEDEN ARGUMANDA DA VAR: CI'da ortam degiskeni daha rahat, elle
    # kullanimda argüman. Ikisi de yoksa asagida anlasilir bir hata
    # veriliyor -- parola sorulmasi otomatik kosmayi bozardi.
    ayristirici.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    return ayristirici.parse_args()


async def admin_olustur(username: str, email: str, password: str) -> str:
    """Kullaniciyi olusturur ya da admin yapar; ne yapildigini anlatir."""
    motor = create_async_engine(settings.database_url, future=True)
    oturum_fabrikasi = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)

    try:
        async with oturum_fabrikasi() as oturum:
            # Kullanici adi VE e-posta ile ariyoruz: ikisi de UNIQUE, biri
            # tutup digeri tutmazsa INSERT patlar. Onceden gorup anlasilir
            # bir mesaj vermek daha iyi.
            mevcut = (
                await oturum.execute(
                    select(User).where(
                        (User.username == username) | (User.email == email)
                    )
                )
            ).scalar_one_or_none()

            if mevcut is None:
                kullanici = User(
                    username=username,
                    email=email,
                    hashed_password=hash_password(password),
                    is_admin=True,
                    # Panel disinda bir sey yapmasi beklenmiyor; sihirbaz
                    # her giriste onune cikmasin.
                    onboarding_completed=True,
                )
                oturum.add(kullanici)
                await oturum.commit()
                return f"admin olusturuldu: {username}"

            if mevcut.username != username or mevcut.email != email:
                raise SystemExit(
                    "Bu kullanici adi ya da e-posta baska bir kayitta kullaniliyor: "
                    f"username={mevcut.username} email={mevcut.email}"
                )

            if mevcut.is_admin and not mevcut.is_deleted:
                return f"zaten admin, dokunulmadi: {username}"

            # Silinmis bir kaydi geri acmak sessizce yapilacak bir sey
            # degil; ne olduğu ciktida yaziyor.
            mevcut.is_admin = True
            mevcut.is_deleted = False
            await oturum.commit()
            return f"var olan kullanici admin yapildi: {username}"
    finally:
        await motor.dispose()


def main() -> None:
    arg = _arguman_coz()

    eksikler = [
        ad
        for ad, deger in (
            ("username", arg.username),
            ("email", arg.email),
            ("password", arg.password),
        )
        if not deger
    ]
    if eksikler:
        raise SystemExit(
            "Su alanlar eksik: "
            + ", ".join(eksikler)
            + " (arguman ya da ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD)"
        )

    # Uygulamanin kendi kurallari: panelden acilan hesapla ayni esikte
    # olsun. Zayif parolali bir admin, en yetkili hesabi en zayif halka
    # yapardi.
    # validate_username kucuk harfe ceviriyor; donen degeri kullanmak
    # sart, yoksa "Kaan" ile acilan hesap "kaan" ile aranip bulunamazdi.
    username = validate_username(arg.username)
    validate_password(arg.password)

    try:
        email = str(_EPosta(adres=arg.email).adres).lower()
    except ValidationError as hata:
        raise SystemExit(f"Gecersiz e-posta: {arg.email}\n{hata}") from hata

    sonuc = asyncio.run(admin_olustur(username, email, arg.password))
    print(sonuc)


if __name__ == "__main__":
    sys.exit(main())
