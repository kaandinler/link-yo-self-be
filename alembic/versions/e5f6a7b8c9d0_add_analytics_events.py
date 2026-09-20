"""add analytics events

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-15 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DIKKAT: Bu tablo bostan basliyor. Mevcut sayaclar (links.click_count,
    # users.profile_view_count) gecmisin toplamini biliyor ama ne zaman
    # oldugunu bilmiyor; geriye donuk olay uretilemez. Dolayisiyla zaman
    # serisi grafigi yalnizca bu migration'dan sonrasini gosterir.
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("link_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # Link silinince olay kalmali; gecmis bir gunun toplami degismemeli.
        sa.ForeignKeyConstraint(["link_id"], ["links.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analytics_events_id"), "analytics_events", ["id"])
    # Zaman serisi sorgusu her zaman "bir kullanicinin su tarihten sonraki
    # olaylari" seklinde.
    op.create_index(
        "ix_analytics_events_user_created",
        "analytics_events",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_analytics_events_user_created", table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_id"), table_name="analytics_events")
    op.drop_table("analytics_events")
