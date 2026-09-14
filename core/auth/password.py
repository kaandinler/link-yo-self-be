"""Sifre ozetleme yardimcilari.

Hem AuthService (kayit, sifre sifirlama) hem de UserService (admin CRUD)
sifre ozetlemek zorunda. UserService'in AuthService'i kullanmasi dairesel
import olustururdu -- AuthService zaten UserService'e bagimli -- bu yuzden
ortak kod burada duruyor.
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Duz metin sifreyi bcrypt ile ozetler."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Duz metin sifreyi kayitli ozetle karsilastirir."""
    return pwd_context.verify(plain_password, hashed_password)
