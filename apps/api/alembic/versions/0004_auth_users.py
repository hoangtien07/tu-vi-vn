"""auth users + sessions + profiles.user_id

Revision ID: 0004_auth_users
Revises: 0003_profiles_events
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_auth_users"
down_revision: str | None = "0003_profiles_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("user_id", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_profiles_user_id", "users", ["user_id"], ["id"]
        )
        batch.create_index("ix_profiles_user_id", ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_index("ix_profiles_user_id")
        batch.drop_constraint("fk_profiles_user_id", type_="foreignkey")
        batch.drop_column("user_id")
    op.drop_table("auth_sessions")
    op.drop_table("users")
