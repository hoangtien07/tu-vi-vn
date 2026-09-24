"""profiles + product_events (SPEC_V02 §2, §7)

Revision ID: 0003_profiles_events
Revises: 0002_compat_partner
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_profiles_events"
down_revision: str | Sequence[str] | None = "0002_compat_partner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner_key", sa.Text(), nullable=False, server_default="local"),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("relationship", sa.Text(), nullable=True),
        sa.Column("chart_snapshot_id", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["chart_snapshot_id"],
            ["chart_snapshots.id"],
            name="fk_profiles_chart_snapshot_id",
        ),
    )
    op.create_index("ix_profiles_owner_key", "profiles", ["owner_key"])
    op.create_index("ix_profiles_chart_snapshot_id", "profiles", ["chart_snapshot_id"])

    op.create_table(
        "product_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=True),
        sa.Column("chart_snapshot_id", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_product_events_event", "product_events", ["event"])


def downgrade() -> None:
    op.drop_index("ix_product_events_event", table_name="product_events")
    op.drop_table("product_events")
    op.drop_index("ix_profiles_chart_snapshot_id", table_name="profiles")
    op.drop_index("ix_profiles_owner_key", table_name="profiles")
    op.drop_table("profiles")
