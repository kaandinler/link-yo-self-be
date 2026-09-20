"""add email verification

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-15 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Mevcut kayitlar icin server_default gerekli (nullable=False).
    #
    # DIKKAT: Varsayilan false. Bu migration'dan once kayit olmus kullanicilar
    # dogrulanmamis sayiliyor; adreslerini dogrulamalari icin uygulama onlara
    # "yeniden gonder" secenegi sunuyor.
    op.add_column(
        'users',
        sa.Column(
            'email_verified', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_email_verification_tokens_id'),
        'email_verification_tokens',
        ['id'],
    )
    op.create_index(
        op.f('ix_email_verification_tokens_token_hash'),
        'email_verification_tokens',
        ['token_hash'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_email_verification_tokens_token_hash'),
        table_name='email_verification_tokens',
    )
    op.drop_index(
        op.f('ix_email_verification_tokens_id'),
        table_name='email_verification_tokens',
    )
    op.drop_table('email_verification_tokens')
    op.drop_column('users', 'email_verified')
