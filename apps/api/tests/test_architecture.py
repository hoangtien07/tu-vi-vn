"""CI import-lint: x_iztro may only be imported under app/infrastructure/xiztro/ (SPEC §6)."""

from pathlib import Path

APP_DIR = Path(__file__).parent.parent / "app"
ALLOWED_DIR = APP_DIR / "infrastructure" / "xiztro"


def test_xiztro_import_boundary() -> None:
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if ALLOWED_DIR in path.parents:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("import x_iztro", "from x_iztro")):
                offenders.append(f"{path}:{lineno}")
    assert offenders == [], f"x_iztro imported outside infrastructure/xiztro: {offenders}"
