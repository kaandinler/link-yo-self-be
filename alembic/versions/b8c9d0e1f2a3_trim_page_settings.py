"""trim redundant columns from user_page_settings

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-20 12:00:00.000000

NEDEN DUSURULUYOR: user_page_settings uc kolonu users tablosundakilerle
ayni seyi anlatiyordu:

    background_color      <-> background_type='color'  + background_value
    background_image_url  <-> background_type='image'  + background_value
    profile_image_url     <-> profile_image_url        (birebir ayni)

users tarafi ustelik daha yetenekli: background_type 'gradient'i de
destekliyor, PageSettings'in iki kolonu bunu hic ifade edemiyor. Ikisini
birden acik birakmak, ayni gorunumu iki yerden okunabilir yapardi ve
hangisinin kazandigi cagri sirasina kalirdi.

Kolonlar tabloda kaliyor gibi gorunup kullanilmasin diye yorum degil
migration tercih edildi: silinen kolon yanlislikla kullanilamaz.

VERI KAYBI YOK: tablo hicbir zaman yazilmadi (uretimde 0 satir; kod
tabaninda models.py disinda PageSettings'e dokunan tek satir yoktu).
Geriye kalan iki kolon -- adult_warning_enabled ve extra_settings --
users'ta karsiligi olmayanlar; PageSettings artik yalnizca onlari
tutuyor.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: str | None = 'a7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('user_page_settings', 'background_color')
    op.drop_column('user_page_settings', 'background_image_url')
    op.drop_column('user_page_settings', 'profile_image_url')


def downgrade() -> None:
    # Kolonlar geri geliyor ama icerikleri gelmiyor: zaten bos idiler.
    op.add_column(
        'user_page_settings',
        sa.Column('profile_image_url', sa.String(), nullable=True),
    )
    op.add_column(
        'user_page_settings',
        sa.Column('background_image_url', sa.String(), nullable=True),
    )
    op.add_column(
        'user_page_settings',
        sa.Column('background_color', sa.String(length=20), nullable=True),
    )
