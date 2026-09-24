#!/usr/bin/env python3
"""Generate packages/knowledge/glossary-vi.md from x-iztro's i18n table.

Canonical zh→vi terminology map for prompt injection and GroundingValidator
surface-form checks (SPEC §7). Regenerate on x-iztro upgrade:

    uv --directory apps/api run python ../../scripts/gen_glossary.py
"""

import sys
from pathlib import Path

from x_iztro.i18n import all_keys, translate

OUT = (
    Path(__file__).resolve().parent.parent
    / "packages/knowledge/glossary-vi.md"
)


def main() -> int:
    keys = sorted(all_keys())
    lines = [
        "# Glossary — canonical zh→vi terminology (generated)",
        "",
        "Source: x-iztro 0.6.1 i18n table. Do not edit by hand; run",
        "`scripts/gen_glossary.py`. Keys are language-independent identifiers;",
        "LLM output must use the vi surface form.",
        "",
        "| key | zh-CN | vi-VN |",
        "|---|---|---|",
    ]
    missing = 0
    for key in keys:
        zh = translate(key, "zh-CN") or ""
        vi = translate(key, "vi-VN") or ""
        if not vi:
            missing += 1
        lines.append(f"| {key} | {zh} | {vi} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(keys)} keys, {missing} missing vi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
