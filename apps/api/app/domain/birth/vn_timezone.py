"""Versioned VN civil-timezone rule table — replaces IANA zone resolution.

`Asia/Hanoi` does not exist in tzdata rearguard and PyPI `tzdata` wheels, so
rules are encoded explicitly (source: tzdb backzone + Trần, SPEC §5).

History (minutes east of UTC):
- North (Hà Nội):   +08 until 1954-10 (exact day unknown → flagged ambiguous),
                    then +07 continuously.
- South (Sài Gòn):  +08 until 1955-07-01, +07 until 1960-01-01,
                    +08 until 1975-06-12 23:00 local, then +07.
- Central:          follows South (southern administration during divergence).

Divergence windows (north +07 vs south +08) — birthRegion is REQUIRED here:
(a) 1954-10-01 → 1955-07-01   (b) 1960-01-01 → 1975-06-12 23:00
"""

import datetime as dt
from typing import Literal

from app.domain.birth.contracts import BirthRegion

VN_TZ_VERSION = "vn-tst-v1"
VICTNAM_REGION = Literal["north", "central", "south"]

_NORTH_SWITCH = dt.datetime(1954, 10, 1)  # ambiguous day within October 1954
_SOUTH_FIRST_SWITCH = dt.datetime(1955, 7, 1)
_SOUTH_PLUS8_START = dt.datetime(1960, 1, 1)
_UNIFICATION_SWITCH = dt.datetime(1975, 6, 12, 23, 0)

DIVERGENCE_WINDOWS = (
    (_NORTH_SWITCH, _SOUTH_FIRST_SWITCH),
    (_SOUTH_PLUS8_START, _UNIFICATION_SWITCH),
)


class BirthRegionRequiredError(ValueError):
    """Birth falls in a north/south offset divergence window without birthRegion."""


def in_divergence_window(local_dt: dt.datetime) -> bool:
    return any(start <= local_dt < end for start, end in DIVERGENCE_WINDOWS)


def resolve_offset_minutes(
    local_dt: dt.datetime, region: BirthRegion | None
) -> tuple[int, list[str]]:
    """Return (offset minutes east of UTC, provenance warnings)."""
    if in_divergence_window(local_dt) and region is None:
        raise BirthRegionRequiredError(
            "birth falls in a 1954–1975 north/south timezone divergence window; "
            "birthRegion is required"
        )

    warnings: list[str] = []
    effective_region: BirthRegion = region or "south"

    if effective_region == "north":
        if local_dt < _NORTH_SWITCH:
            return 480, warnings
        if local_dt < dt.datetime(1954, 11, 1):
            warnings.append(
                "ambiguous north offset boundary: exact switch day in October 1954 "
                "is not recorded in tzdb"
            )
        return 420, warnings

    # south + central
    if local_dt < _SOUTH_FIRST_SWITCH or _SOUTH_PLUS8_START <= local_dt < _UNIFICATION_SWITCH:
        return 480, warnings
    return 420, warnings
