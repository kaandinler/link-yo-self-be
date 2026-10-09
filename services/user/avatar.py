"""Yuklenen avatarin islenmesi.

Gelen dosya OLDUGU GIBI SAKLANMIYOR; her zaman yeniden kodlaniyor:

- Kare kirpiliyor ve en fazla BOYUT x BOYUT'a indiriliyor.
- JPEG olarak (saydamlik varsa PNG) yeniden yaziliyor. Yeniden yazilan
  dosyada yalnizca pikseller var: EXIF (telefon fotograflarinda GPS
  konumu dahil) ve gorselin icine gizlenmis baska icerik (ornegin
  gorsel + HTML/JS "polyglot" dosyalar) yeni dosyaya tasinmiyor.
- Uzanti ve istemcinin yazdigi content-type'a bakilmiyor; tur dosyanin
  kendisinden okunuyor.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

# Avatar en buyuk 96x96 (profil sayfasi, 2x ekranda 192) ve paylasim
# kartinda 160 px gosteriliyor. 400, 2x ekranlarda da keskin kalacak
# kadar buyuk; saklanan dosya ~25 KB (olculdu, 12 MP bir fotograftan).
BOYUT = 400

# Kabul edilen bicimler. GIF'in yalnizca ilk karesi aliniyor.
KABUL_EDILEN = frozenset({"JPEG", "PNG", "WEBP", "GIF"})

# Cozulmeden ONCE, dosyanin basligindaki olcuye bakilarak reddediliyor.
# NEDEN: birkac KB'lik bir PNG, bellege acildiginda gigabaytlarca yer
# tutan bir gorsel tanimlayabilir ("decompression bomb"). 40 MP, gunluk
# fotograflari rahatca kapsiyor; RGBA'da acildiginda ~160 MB.
AZAMI_PIKSEL = 40_000_000


class GecersizGorsel(ValueError):
    """Dosya kabul edilebilir bir gorsel degil. Mesaj istemciye gidiyor."""


@dataclass(frozen=True)
class IslenmisAvatar:
    veri: bytes
    uzanti: str
    icerik_turu: str


def avatar_isle(ham: bytes) -> IslenmisAvatar:
    """Ham dosyayi saklanacak gorsele cevirir.

    NEDEN WebP DEGIL: paylasim kartini cizen Satori (next/og) WebP'yi
    cozemiyor; avatarli kart istegi "a is not iterable" ile dusuyordu
    (olculdu, e2e). JPEG ve PNG'yi hem tarayicilar hem Satori okuyor.
    Saydamlik yoksa JPEG, varsa PNG (JPEG saydamligi tasimiyor). Olculdu,
    12 MP bir fotograftan uretilen ayni avatar: JPEG 24 KB, PNG 216 KB.

    CPU yogun (cozme + yeniden kodlama); olay dongusunden degil bir
    is parcacigindan cagrilmali.
    """
    try:
        with Image.open(io.BytesIO(ham)) as gorsel:
            if gorsel.format not in KABUL_EDILEN:
                raise GecersizGorsel(
                    "Unsupported image format. Use JPEG, PNG, WebP or GIF."
                )

            genislik, yukseklik = gorsel.size
            if genislik * yukseklik > AZAMI_PIKSEL:
                raise GecersizGorsel("Image dimensions are too large.")

            # JPEG'i tam cozunurlukte cozmek gereksiz: draft, cozucuye
            # gorseli 1/2, 1/4 veya 1/8 olcekte acmasini soyluyor (hedefin
            # altina inmeden). Olculdu, 12 MP bir fotograf, 7 kosunun medyani:
            # ~235 -> ~45 ms.
            # Diger bicimlerde etkisi yok.
            gorsel.draft("RGB", (BOYUT, BOYUT))

            # Telefonlar fotografi dondurmek yerine EXIF'e "yon" yaziyor.
            # Uygulanmazsa yan yatmis avatarlar cikiyor -- ve EXIF yeni
            # dosyaya tasinmadigi icin tarayici da duzeltemez.
            gorsel = ImageOps.exif_transpose(gorsel)

            saydam = gorsel.mode in ("RGBA", "LA", "PA") or (
                gorsel.mode == "P" and "transparency" in gorsel.info
            )
            gorsel = gorsel.convert("RGBA" if saydam else "RGB")

            # Kucuk gorsel buyutulmuyor; buyutmek dosyayi buyutur, gorseli
            # keskinlestirmez.
            kenar = min(BOYUT, gorsel.width, gorsel.height)
            gorsel = ImageOps.fit(
                gorsel, (kenar, kenar), method=Image.Resampling.LANCZOS
            )

            cikti = io.BytesIO()
            if saydam:
                gorsel.save(cikti, format="PNG", optimize=True)
                return IslenmisAvatar(cikti.getvalue(), "png", "image/png")
            gorsel.save(cikti, format="JPEG", quality=85, optimize=True)
            return IslenmisAvatar(cikti.getvalue(), "jpg", "image/jpeg")
    except GecersizGorsel:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError):
        raise GecersizGorsel("File is not a valid image.") from None
    except (OSError, SyntaxError, ValueError):
        # Bozuk/kesik dosyalar Pillow'da bu uc turden biriyle dusuyor
        # (basligi saglam, govdesi bozuk bir PNG ornegin OSError).
        raise GecersizGorsel("File is not a valid image.") from None
