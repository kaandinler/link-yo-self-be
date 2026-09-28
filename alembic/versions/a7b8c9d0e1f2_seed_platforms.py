"""seed platforms

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-20 10:00:00.000000

NEDEN SEED GEREKIYOR: platforms tablosu ilk migration'da olusturuldu ama
hicbir zaman doldurulmadi. SocialAccount.platform_id bir FOREIGN KEY
oldugu icin, tablo bosken hicbir sosyal hesap eklenemez -- yani uclar
teknik olarak calisir, pratikte hicbir sey yapilamaz.

Liste sabit ve kodda: platform ekleme/cikarma icin admin ucu yok (bkz.
PR notu). Yeni platform yeni bir migration demek.

NEDEN "ON CONFLICT DO NOTHING" DEGIL de once okuyup sonra yaziyoruz:
migration hem PostgreSQL hem SQLite altinda calisiyor (testler SQLite
kullaniyor) ve ikisinin upsert sozdizimi ayni degil. Mevcut adlari
okuyup eksikleri eklemek her iki veritabaninda da ayni sekilde
davraniyor ve migration'i yeniden calistirilabilir yapiyor.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: str | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (name, display_name). `name` UNIQUE ve makine tarafi; display_name
# arayuzde gosterilen ad.
PLATFORMLAR: list[tuple[str, str]] = [
    ("behance", "Behance"),
    ("discord", "Discord"),
    ("dribbble", "Dribbble"),
    ("facebook", "Facebook"),
    ("github", "GitHub"),
    ("instagram", "Instagram"),
    ("linkedin", "LinkedIn"),
    ("medium", "Medium"),
    ("pinterest", "Pinterest"),
    ("reddit", "Reddit"),
    ("snapchat", "Snapchat"),
    ("spotify", "Spotify"),
    ("telegram", "Telegram"),
    ("threads", "Threads"),
    ("tiktok", "TikTok"),
    ("twitch", "Twitch"),
    ("website", "Website"),
    ("whatsapp", "WhatsApp"),
    ("x", "X (Twitter)"),
    ("youtube", "YouTube"),
]


def upgrade() -> None:
    baglanti = op.get_bind()

    mevcut = {
        satir[0]
        for satir in baglanti.execute(sa.text("SELECT name FROM platforms"))
    }

    eklenecek = [
        {"name": ad, "display_name": gosterim, "is_deleted": False}
        for ad, gosterim in PLATFORMLAR
        if ad not in mevcut
    ]

    if not eklenecek:
        return

    # is_deleted bagli parametre olarak veriliyor: kolonun server_default'u
    # yok ve `false` literali her lehcede ayni yazilmiyor.
    baglanti.execute(
        sa.text(
            "INSERT INTO platforms (name, display_name, is_deleted) "
            "VALUES (:name, :display_name, :is_deleted)"
        ),
        eklenecek,
    )


def downgrade() -> None:
    baglanti = op.get_bind()

    # Yalnizca bu migration'in ekledigi adlar siliniyor. Sonradan elle
    # eklenmis bir platform varsa ona dokunulmuyor.
    #
    # Bir platforma bagli sosyal hesap varsa FOREIGN KEY ... ON DELETE
    # CASCADE o hesaplari da siler; downgrade zaten veri kaybi demek.
    baglanti.execute(
        sa.text("DELETE FROM platforms WHERE name IN :adlar").bindparams(
            sa.bindparam("adlar", value=[ad for ad, _ in PLATFORMLAR], expanding=True)
        )
    )
