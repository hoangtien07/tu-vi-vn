"""initial schema + seed iztro-default-v1 engine profile

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_ENGINE_PROFILE = {
    "id": "iztro-default-v1",
    "engine": "x-iztro",
    "engineVersion": "0.6.1",
    "fixLeap": True,
    "yearDivide": "normal",
    "horoscopeDivide": "normal",
    "ageDivide": "normal",
    "dayDivide": "forward",
    "algorithm": "default",
    "astroType": "heaven",
    "mutagenTableVersion": "builtin",
    "brightnessTableVersion": "builtin",
}

Jsonb = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
TS = sa.DateTime(timezone=True)
CREATED = sa.Column("created_at", TS, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "birth_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        CREATED,
    )
    op.create_table(
        "engine_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("content", Jsonb, nullable=False),
        CREATED,
    )
    op.create_table(
        "raw_birth_inputs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "birth_profile_id", sa.Text(), sa.ForeignKey("birth_profiles.id"), nullable=False
        ),
        sa.Column("payload", Jsonb, nullable=False),
        CREATED,
    )
    op.create_index("ix_raw_birth_inputs_birth_profile_id", "raw_birth_inputs", ["birth_profile_id"])
    op.create_table(
        "normalized_birth_moments",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "raw_birth_input_id", sa.Text(), sa.ForeignKey("raw_birth_inputs.id"), nullable=False
        ),
        sa.Column("payload", Jsonb, nullable=False),
        CREATED,
    )
    op.create_index(
        "ix_normalized_birth_moments_raw_birth_input_id",
        "normalized_birth_moments",
        ["raw_birth_input_id"],
    )
    op.create_table(
        "chart_snapshots",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "birth_profile_id", sa.Text(), sa.ForeignKey("birth_profiles.id"), nullable=False
        ),
        sa.Column(
            "normalized_birth_moment_id",
            sa.Text(),
            sa.ForeignKey("normalized_birth_moments.id"),
            nullable=False,
        ),
        sa.Column("engine", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column(
            "engine_profile_id", sa.Text(), sa.ForeignKey("engine_profiles.id"), nullable=False
        ),
        sa.Column("chart_hash", sa.Text(), nullable=False),
        sa.Column("dto_schema_version", sa.Integer(), nullable=False),
        sa.Column("chart_json", Jsonb, nullable=False),
        sa.Column("pattern_hits", Jsonb, nullable=False),
        sa.Column("share_token", sa.Text(), nullable=False),
        CREATED,
    )
    op.create_index("ix_chart_snapshots_birth_profile_id", "chart_snapshots", ["birth_profile_id"])
    op.create_index(
        "ix_chart_snapshots_normalized_birth_moment_id",
        "chart_snapshots",
        ["normalized_birth_moment_id"],
    )
    op.create_index("ix_chart_snapshots_chart_hash", "chart_snapshots", ["chart_hash"], unique=True)
    op.create_index("ix_chart_snapshots_share_token", "chart_snapshots", ["share_token"], unique=True)
    op.create_table(
        "conversations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "chart_snapshot_id", sa.Text(), sa.ForeignKey("chart_snapshots.id"), nullable=False
        ),
        CREATED,
    )
    op.create_index("ix_conversations_chart_snapshot_id", "conversations", ["chart_snapshot_id"])
    op.create_table(
        "evidence_bundles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "chart_snapshot_id", sa.Text(), sa.ForeignKey("chart_snapshots.id"), nullable=False
        ),
        sa.Column("context_hash", sa.Text()),
        sa.Column("payload", Jsonb, nullable=False),
        CREATED,
    )
    op.create_index(
        "ix_evidence_bundles_chart_snapshot_id", "evidence_bundles", ["chart_snapshot_id"]
    )
    op.create_table(
        "interpretation_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "chart_snapshot_id", sa.Text(), sa.ForeignKey("chart_snapshots.id"), nullable=False
        ),
        sa.Column("evidence_bundle_id", sa.Text(), sa.ForeignKey("evidence_bundles.id")),
        sa.Column("conversation_id", sa.Text(), sa.ForeignKey("conversations.id")),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("version_meta", Jsonb, nullable=False),
        sa.Column("claims", Jsonb, nullable=False, server_default="[]"),
        sa.Column("output_text", sa.Text()),
        CREATED,
    )
    op.create_index(
        "ix_interpretation_runs_chart_snapshot_id", "interpretation_runs", ["chart_snapshot_id"]
    )
    op.create_index(
        "ix_interpretation_runs_evidence_bundle_id",
        "interpretation_runs",
        ["evidence_bundle_id"],
    )
    op.create_index(
        "ix_interpretation_runs_idempotency_key",
        "interpretation_runs",
        ["idempotency_key"],
        unique=True,
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id", sa.Text(), sa.ForeignKey("conversations.id"), nullable=False
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        CREATED,
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    engine_profiles = sa.table(
        "engine_profiles", sa.column("id", sa.Text), sa.column("content", Jsonb)
    )
    op.bulk_insert(engine_profiles, [{"id": "iztro-default-v1", "content": DEFAULT_ENGINE_PROFILE}])


def downgrade() -> None:
    for table in (
        "messages",
        "interpretation_runs",
        "evidence_bundles",
        "conversations",
        "chart_snapshots",
        "normalized_birth_moments",
        "raw_birth_inputs",
        "engine_profiles",
        "birth_profiles",
    ):
        op.drop_table(table)
