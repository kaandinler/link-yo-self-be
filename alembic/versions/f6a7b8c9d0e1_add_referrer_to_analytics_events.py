"""add referrer to analytics events

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-16 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Kolon nullable: hem bu migration'dan onceki olaylar icin doldurulacak
    # bir deger yok, hem de NULL'in kendisi bir anlam tasiyor -- "dis bir
    # kaynak yok". Bu yuzden sonradan NOT NULL + '' yapilmamali: bos metin
    # ile "bilinmiyor" ayni sey degil.
    op.add_column(
        "analytics_events",
        sa.Column("referrer", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("analytics_events", "referrer")
