"""Locate repo-root files robustly in dev checkouts and the API image."""

from pathlib import Path


def repo_file(*parts: str) -> Path:
    """Return the first existing `parts` path found walking up from this file.

    Works from the source tree (repo/packages/...) and the Docker image where
    the package is copied under /srv/packages while code lives in /srv/app.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent.joinpath(*parts)
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parents[-1].joinpath(*parts)
