import type { PalaceView } from "../adapters/dto-to-view";

const MUTAGEN_STYLE: Record<string, string> = {
  "Lộc": "text-emerald-700 bg-emerald-50",
  "Quyền": "text-amber-700 bg-amber-50",
  "Khoa": "text-sky-700 bg-sky-50",
  "Kỵ": "text-rose-700 bg-rose-50",
};

export function PalaceCell({ palace }: { palace: PalaceView }) {
  const isSoul = palace.nameKey === "soulPalace";
  return (
    <div
      className={`flex min-h-28 flex-col rounded border p-1.5 text-xs ${
        isSoul ? "border-amber-500 bg-amber-50/40" : "border-zinc-200 bg-white"
      }`}
    >
      <div className="flex-1 space-y-0.5">
        {palace.majorStars.map((s) => (
          <div key={s.key} className="flex items-center gap-1 font-medium">
            <span className={s.mutagen === "Kỵ" ? "text-rose-700" : ""}>
              {s.name}
            </span>
            {s.mutagen && (
              <span
                className={`rounded px-0.5 text-[10px] leading-4 ${MUTAGEN_STYLE[s.mutagen] ?? ""}`}
              >
                {s.mutagen}
              </span>
            )}
            {s.brightness && (
              <span className="text-[10px] text-zinc-400">{s.brightness}</span>
            )}
          </div>
        ))}
        {palace.minorStars.map((s) => (
          <div key={s.key} className="flex items-center gap-1 text-zinc-600">
            <span>{s.name}</span>
            {s.mutagen && (
              <span
                className={`rounded px-0.5 text-[10px] leading-4 ${MUTAGEN_STYLE[s.mutagen] ?? ""}`}
              >
                {s.mutagen}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="mt-1 flex items-end justify-between text-[10px] text-zinc-500">
        <span>
          {palace.decadalRange && `${palace.decadalRange[0]}–${palace.decadalRange[1]}`}
        </span>
        <span className="font-medium text-zinc-700">
          {palace.name}
          {palace.isBodyPalace && " (Thân)"}
        </span>
        <span>{palace.stemBranch}</span>
      </div>
    </div>
  );
}
