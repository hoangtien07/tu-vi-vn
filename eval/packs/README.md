# eval/packs — tournament knowledge packs

Knowledge packs for the SPEC_V04 tournament. **Lore only — never chart data (I19).**
Packs feed `KnowledgeRegistry` excerpts that the LLM may rephrase; every LLM claim
still cites deterministic `[E###]` evidence from the chart engine.

## Selection (I17)

`KNOWLEDGE_PACK` env var, resolved at app boot (`create_app`):

| value | effect |
|---|---|
| `builtin` (default) | x-iztro zh-CN pack |
| `none` | ablation — excerpts return `None`, `version_info.id = "none"` |
| any other string | path to a pack JSON file, loaded via `KnowledgePack.from_dict` |

`/health` exposes the active pack as `knowledgePack`. Selection is per-process —
there is no per-request pack parameter (out of scope V04).

## File schema

x-iztro `KnowledgePack.from_dict` shape:

```jsonc
{
  "id": "vn-seed-v1",          // shown in /health + pinned into run metadata
  "version": "1.0.0",
  "language": "vi-VN",
  "source": { "url": "...", "commit": "...", "license": "MIT — ..." },
  "schema": 1,
  "palaces":  { "<palaceKey>": { "name": "...", "intro": "..." } },
  "stars":    { "<starKey>":   { "name": "...", "category": "major|minor|adjective|dec",
                                 "intro": "...", "attributes": {}, "combinations": {} } },
  "patterns": { "<patternKey>":{ "name": "...", "quotes": ["..."], "conditions": "...",
                                 "intro": "..." } },
  "mutagens": { "sihuaLu|sihuaQuan|sihuaKe|sihuaJi": { "name": "...", "intro": "..." } },
  "concepts": {},
  "extends": null
}
```

Entity keys are x-iztro nameKeys (`ziweiMaj`, `careerPalace`, `sha_po_lang`, ...) —
the composer looks them up from deterministic chart/horoscope evidence, so a pack
only helps when its keys match what the frozen corpus actually cites. Excerpts fed
to the LLM: star → `intro` (≤300 chars), palace → `intro`, pattern → `quotes` (≤3).

## Packs

- `vn-seed-v1.json` — Vietnamese seed pack covering the entity keys most cited in
  `eval/bench/reports/` (12 palaces, 14 majors, 17 minors, 20 patterns, 4 mutagens).
  Vietnamese lore adapted from the MIT zh-CN pack; same keys so excerpts swap cleanly.

## Running the tournament

```bash
python eval/tournament/run_tournament.py --smoke          # boot/health check only
python eval/tournament/run_tournament.py --suite static   # full frozen corpus
```

Decision gate (I18): a challenger wins only with **0 grounding failures AND rubric
mean ≥ baseline** on the frozen 24-chart corpus. The gate is advisory — switching
the production pack is a human decision, never automatic.
