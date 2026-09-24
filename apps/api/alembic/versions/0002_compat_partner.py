"""interpretation_runs: + partner_chart_snapshot_id (hợp bàn, SPEC_COMPAT §3.1)

Revision ID: 0002_compat_partner
Revises: 0001_initial
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_compat_partner"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch mode: SQLite can't ALTER a FK constraint in place — copy-and-move
    # keeps this migration working on both sqlite (dev/tests) and postgres.
    with op.batch_alter_table("interpretation_runs") as batch:
        batch.add_column(
            sa.Column("partner_chart_snapshot_id", sa.Text(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_interpretation_runs_partner_chart_snapshot_id",
            "chart_snapshots",
            ["partner_chart_snapshot_id"],
            ["id"],
        )
        batch.create_index(
            "ix_interpretation_runs_partner_chart_snapshot_id",
            ["partner_chart_snapshot_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("interpretation_runs") as batch:
        batch.drop_index("ix_interpretation_runs_partner_chart_snapshot_id")
        batch.drop_constraint("fk_interpretation_runs_partner_chart_snapshot_id")
        batch.drop_column("partner_chart_snapshot_id")
