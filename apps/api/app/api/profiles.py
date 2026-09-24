"""SPEC_V02 §5 — profile library wrapping chart snapshots."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import ChartSnapshot, Profile
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

ALLOWED_RELATIONSHIPS = {"self", "partner", "mother", "father", "child", "friend", "other"}
ALLOWED_VISIBILITY = {"private", "shared-link"}
OWNER_KEY = "local"  # single-tenant; auth in v0.3 swaps this for a user id


class ProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    relationship: str | None = Field(default=None, max_length=32)
    chart_id: str
    visibility: str = "private"


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    relationship: str | None = Field(default=None, max_length=32)
    visibility: str | None = None


def _serialize(p: Profile) -> dict[str, object]:
    return {
        "id": p.id,
        "displayName": p.display_name,
        "relationship": p.relationship,
        "chartId": p.chart_snapshot_id,
        "visibility": p.visibility,
        "createdAt": p.created_at,
        "updatedAt": p.updated_at,
    }


@router.get("")
def list_profiles(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    rows = session.scalars(
        select(Profile).where(Profile.owner_key == OWNER_KEY).order_by(Profile.created_at)
    ).all()
    return [_serialize(p) for p in rows]


@router.post("", status_code=201)
def create_profile(
    body: ProfileCreate, session: Session = Depends(get_session)
) -> dict[str, object]:
    if session.get(ChartSnapshot, body.chart_id) is None:
        raise HTTPException(status_code=404, detail="chart not found")
    if body.relationship is not None and body.relationship not in ALLOWED_RELATIONSHIPS:
        raise HTTPException(status_code=422, detail="unknown relationship")
    if body.visibility not in ALLOWED_VISIBILITY:
        raise HTTPException(status_code=422, detail="unknown visibility")
    p = Profile(
        id=f"pf_{uuid4().hex[:16]}",
        owner_key=OWNER_KEY,
        display_name=body.display_name,
        relationship=body.relationship,
        chart_snapshot_id=body.chart_id,
        visibility=body.visibility,
    )
    session.add(p)
    session.commit()
    return _serialize(p)


@router.get("/{profile_id}")
def get_profile(
    profile_id: str, session: Session = Depends(get_session)
) -> dict[str, object]:
    p = session.get(Profile, profile_id)
    if p is None or p.owner_key != OWNER_KEY:
        raise HTTPException(status_code=404, detail="profile not found")
    return _serialize(p)


@router.patch("/{profile_id}")
def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    p = session.get(Profile, profile_id)
    if p is None or p.owner_key != OWNER_KEY:
        raise HTTPException(status_code=404, detail="profile not found")
    if body.display_name is not None:
        p.display_name = body.display_name
    if body.relationship is not None:
        if body.relationship not in ALLOWED_RELATIONSHIPS:
            raise HTTPException(status_code=422, detail="unknown relationship")
        p.relationship = body.relationship
    if body.visibility is not None:
        if body.visibility not in ALLOWED_VISIBILITY:
            raise HTTPException(status_code=422, detail="unknown visibility")
        p.visibility = body.visibility
    session.commit()
    return _serialize(p)


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: str, session: Session = Depends(get_session)
) -> None:
    p = session.get(Profile, profile_id)
    if p is None or p.owner_key != OWNER_KEY:
        raise HTTPException(status_code=404, detail="profile not found")
    session.delete(p)
    session.commit()
