"""add publish_at and expire_at to links

Revision ID: c7d8e9f0a1b2
Revises: b8c9d0e1f2a3
Create Date: 2026-09-17 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: str | None = 'b8c9d0e1f2a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Kolonlar nullable: migration'dan onceki linklerin zaman sinirlamasi
    # yok; NULL'in kendisi "sinirsiz" anlamina geliyor. Timezone-aware:
    # "etkinlik bitince gizlenir" gibi kararlar zaman dilimi bilmeden
    # dogru verilemez.
    op.add_column(
        'links',
        sa.Column('publish_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'links',
        sa.Column('expire_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('links', 'expire_at')
    op.drop_column('links', 'publish_at')
