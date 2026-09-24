from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on postgres, plain JSON on sqlite (tests)
Jsonb = JSONB().with_variant(JSON(), "sqlite")


class Base(DeclarativeBase):
    pass


class BirthProfile(Base):
    __tablename__ = "birth_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RawBirthInputRow(Base):
    __tablename__ = "raw_birth_inputs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    birth_profile_id: Mapped[str] = mapped_column(ForeignKey("birth_profiles.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(Jsonb)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NormalizedBirthMomentRow(Base):
    __tablename__ = "normalized_birth_moments"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_birth_input_id: Mapped[str] = mapped_column(ForeignKey("raw_birth_inputs.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(Jsonb)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EngineProfileRow(Base):
    __tablename__ = "engine_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[dict[str, Any]] = mapped_column(Jsonb)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChartSnapshot(Base):
    __tablename__ = "chart_snapshots"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    birth_profile_id: Mapped[str] = mapped_column(ForeignKey("birth_profiles.id"), index=True)
    normalized_birth_moment_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_birth_moments.id"), index=True
    )
    engine: Mapped[str] = mapped_column(Text)
    engine_version: Mapped[str] = mapped_column(Text)
    engine_profile_id: Mapped[str] = mapped_column(ForeignKey("engine_profiles.id"))
    chart_hash: Mapped[str] = mapped_column(Text, unique=True, index=True)
    dto_schema_version: Mapped[int] = mapped_column(Integer)
    chart_json: Mapped[dict[str, Any]] = mapped_column(Jsonb)
    pattern_hits: Mapped[list[Any]] = mapped_column(Jsonb)
    share_token: Mapped[str] = mapped_column(Text, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chart_snapshot_id: Mapped[str] = mapped_column(ForeignKey("chart_snapshots.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceBundle(Base):
    __tablename__ = "evidence_bundles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chart_snapshot_id: Mapped[str] = mapped_column(ForeignKey("chart_snapshots.id"), index=True)
    context_hash: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(Jsonb)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterpretationRun(Base):
    __tablename__ = "interpretation_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chart_snapshot_id: Mapped[str] = mapped_column(ForeignKey("chart_snapshots.id"), index=True)
    # Hợp bàn runs keep chart_a here and chart_b on partner_* (SPEC_COMPAT §3.1).
    partner_chart_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("chart_snapshots.id"), index=True
    )
    evidence_bundle_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_bundles.id"), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"))
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True, index=True)
    topic: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    version_meta: Mapped[dict[str, Any]] = mapped_column(Jsonb)
    claims: Mapped[list[Any]] = mapped_column(Jsonb, default=list)
    output_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # Single-tenant self-hosted deployments use "local"; real auth (v0.3)
    # replaces this with the authenticated user id.
    owner_key: Mapped[str] = mapped_column(Text, default="local", index=True)
    display_name: Mapped[str] = mapped_column(Text)
    relationship: Mapped[str | None] = mapped_column(Text)
    chart_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("chart_snapshots.id"), index=True
    )
    visibility: Mapped[str] = mapped_column(Text, default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProductEvent(Base):
    __tablename__ = "product_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    event: Mapped[str] = mapped_column(Text, index=True)
    profile_id: Mapped[str | None] = mapped_column(Text)
    chart_snapshot_id: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
