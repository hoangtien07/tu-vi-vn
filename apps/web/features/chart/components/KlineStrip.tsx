"use client";

import { useEffect, useState } from "react";
import {
  getTemporalDecade,
  type TemporalDecade,
} from "@/lib/api";

const KINDS = ["Lộc", "Quyền", "Khoa", "Kỵ"] as const;
const KIND_SHORT = ["L", "Q", "K", "Kỵ"] as const;
const KIND_CLS = [
  "bg-emerald-500/90",
  "bg-amber-500/90",
  "bg-sky-500/90",
  "bg-rose-500/90",
] as const;

function MutagenCells({ stars }: { stars: string[] }) {
  return (
    <div className="grid grid-cols-2 gap-0.5">
      {KINDS.map((kind, i) => {
        const star = stars[i];
        return star ? (
          <span
            key={kind}
            title={`${kind} — ${star}`}
            className={`flex h-4 w-4 items-center justify-center rounded-sm text-[9px] font-bold text-white ${KIND_CLS[i]}`}
          >
            {KIND_SHORT[i]}
          </span>
        ) : (
          <span
            key={kind}
            className="flex h-4 w-4 items-center justify-center rounded-sm bg-zinc-200 text-[9px] text-zinc-400 dark:bg-zinc-700"
          >
            ·
          </span>
        );
      })}
    </div>
  );
}

export function KlineStrip({
  chartId,
  selectedYear,
  onSelectYear,
}: {
  chartId: string;
  selectedYear: number;
  onSelectYear: (year: number) => void;
}) {
  const [center, setCenter] = useState(selectedYear);
  const [data, setData] = useState<TemporalDecade | null>(null);
  const [failed, setFailed] = useState(false);
  const currentYear = new Date().getFullYear();

  // Follow the navigator's selected year without an effect (render-time
  // state adjustment is the documented pattern for props-derived state).
  const [prevSelected, setPrevSelected] = useState(selectedYear);
  if (prevSelected !== selectedYear) {
    setPrevSelected(selectedYear);
    setCenter(selectedYear);
  }

  useEffect(() => {
    let cancelled = false;
    getTemporalDecade(chartId, center)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [chartId, center]);

  const loading = data === null && !failed;
  const shift = (d: number) => setCenter((c) => c + d);

  if (failed) return null;

  const dec = data?.decadal;
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <button
          onClick={() => shift(-10)}
          disabled={loading}
          className="rounded border border-zinc-300 px-1.5 py-0.5 text-zinc-500 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-600 dark:hover:bg-zinc-800"
          aria-label="Đại hạn trước"
        >
          ←
        </button>
        <span className="font-semibold uppercase tracking-wide text-amber-700">
          {dec ? `${dec.name} ${dec.heavenlyStem ?? ""} ${dec.earthlyBranch ?? ""}` : "Đại hạn"}
        </span>
        {dec?.palaceName && (
          <span className="text-zinc-500">· {dec.palaceName}</span>
        )}
        {dec?.ageRange && (
          <span className="text-zinc-400">
            · {dec.ageRange[0]}–{dec.ageRange[1]} tuổi
          </span>
        )}
        {dec && dec.mutagen.length > 0 && (
          <span className="flex items-center gap-1 text-zinc-500">
            · Tứ hóa:
            <MutagenCells stars={dec.mutagen} />
          </span>
        )}
        <button
          onClick={() => shift(10)}
          disabled={loading}
          className="rounded border border-zinc-300 px-1.5 py-0.5 text-zinc-500 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-600 dark:hover:bg-zinc-800"
          aria-label="Đại hạn sau"
        >
          →
        </button>
      </div>
      <div className="flex gap-1 overflow-x-auto pb-1">
        {(data?.years ?? []).map((y) => {
          const selected = y.year === selectedYear;
          return (
            <button
              key={y.year}
              onClick={() => onSelectYear(y.year)}
              title={`${y.year} · ${y.heavenlyStem ?? ""} ${y.earthlyBranch ?? ""} · ${y.palaceName ?? ""}`}
              className={`flex w-14 shrink-0 flex-col items-center gap-1 rounded-md border px-1 py-1.5 text-center transition-colors ${
                selected
                  ? "border-amber-500 bg-amber-50 dark:bg-amber-950/30"
                  : "border-zinc-200 hover:border-amber-300 dark:border-zinc-700"
              }`}
            >
              <span className="text-[10px] text-zinc-400">
                {y.heavenlyStem}
                {y.earthlyBranch}
              </span>
              <span
                className={`text-sm font-semibold ${selected ? "text-amber-700" : "text-zinc-700 dark:text-zinc-300"}`}
              >
                {y.year}
                {y.year === currentYear && (
                  <span className="ml-0.5 inline-block h-1 w-1 rounded-full bg-emerald-500 align-middle" />
                )}
              </span>
              <MutagenCells stars={y.mutagen} />
              <span className="max-w-full truncate text-[10px] text-zinc-500">
                {y.palaceName}
              </span>
            </button>
          );
        })}
        {loading && !data && (
          <span className="py-4 text-xs text-zinc-400">Đang tính vận trình…</span>
        )}
      </div>
      <div className="mt-1 flex gap-2 text-[10px] text-zinc-400">
        {KINDS.map((k, i) => (
          <span key={k} className="flex items-center gap-1">
            <span
              className={`inline-block h-2 w-2 rounded-sm ${KIND_CLS[i]}`}
            />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}
