"""add is_admin to users

Revision ID: a1b2c3d4e5f6
Revises: 676b770fc51c
Create Date: 2026-09-13 10:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '676b770fc51c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Mevcut kayitlar icin server_default gerekli (nullable=False).
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_admin')
