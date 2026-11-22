"""add kind and is_featured to links

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-11-22 20:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Bu iki kolon models.py'ye migration'siz girmisti (link gruplama,
    # parca 1/2): testler tablolari create_all ile kurdugu icin eksik
    # fark edilmedi, ama migration ile kurulan veritabaninda kolonlar
    # yoktu ve links tablosuna giden her sorgu hata verirdi.
    #
    # server_default sart: tabloda satir varken NOT NULL kolon eklenemez.
    # Degerler modeldekilerle ayni (kind="link", is_featured=false).
    op.add_column(
        "links",
        sa.Column("kind", sa.String(length=20), server_default="link", nullable=False),
    )
    op.add_column(
        "links",
        sa.Column(
            "is_featured", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("links", "is_featured")
    op.drop_column("links", "kind")
