import type { ChartView } from "../adapters/dto-to-view";
import { PalaceCell } from "./PalaceCell";

// Board positions are fixed by palace index (index 0 is always Dần,
// branches run 0→11 = Dần→Sửu). Standard 12-palace layout.
const GRID: (number | null)[] = [
  3, 4, 5, 6,
  2, null, null, 7,
  1, null, null, 8,
  0, 11, 10, 9,
];

export function ChartBoard({ view }: { view: ChartView }) {
  const byIndex = new Map(view.palaces.map((p) => [p.index, p]));
  return (
    <div className="grid grid-cols-4 gap-1">
      {GRID.map((idx, i) =>
        idx === null ? (
          i === 5 ? (
            <div
              key="center"
              className="col-span-2 row-span-2 flex flex-col items-center justify-center gap-1 rounded border border-zinc-200 bg-zinc-50 p-3 text-center text-xs text-zinc-600"
            >
              <div className="text-sm font-semibold text-zinc-900">
                {view.sign} · {view.zodiac}
              </div>
              <div>{view.fiveElementsClass}</div>
              <div>
                {view.solarDate} · Âm: {view.lunarDate}
              </div>
              <div>
                Mệnh chủ: {view.soul} · Thân chủ: {view.body}
              </div>
              {view.patternNames.length > 0 && (
                <div className="mt-1 text-[10px]">
                  Cách cục: {view.patternNames.join(", ")}
                </div>
              )}
            </div>
          ) : null
        ) : (
          <PalaceCell key={idx} palace={byIndex.get(idx)!} />
        ),
      )}
    </div>
  );
}
