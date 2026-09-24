"use client";

import { useActionState, useState } from "react";

import { submitBirth, type FormState } from "../../../app/actions";

const INPUT =
  "w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const LABEL = "text-xs font-medium text-zinc-600 dark:text-zinc-400";

export function BirthForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(
    submitBirth,
    {},
  );
  const [calendar, setCalendar] = useState<"solar" | "lunar">("solar");
  const [timeUnknown, setTimeUnknown] = useState(false);

  return (
    <form action={action} className="space-y-4">
      <div className="flex gap-3">
        {(["solar", "lunar"] as const).map((c) => (
          <label key={c} className="flex items-center gap-1.5 text-sm">
            <input
              type="radio"
              name="calendar"
              value={c}
              checked={calendar === c}
              onChange={() => setCalendar(c)}
            />
            {c === "solar" ? "Dương lịch" : "Âm lịch"}
          </label>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className={LABEL} htmlFor="date">
            Ngày sinh {calendar === "lunar" ? "(âm)" : "(dương)"}
          </label>
          <input id="date" name="date" type="date" required className={INPUT} />
        </div>
        <div className="space-y-1">
          <label className={LABEL} htmlFor="time">
            Giờ sinh
          </label>
          <input
            id="time"
            name="time"
            type="time"
            required={!timeUnknown}
            disabled={timeUnknown}
            className={INPUT}
          />
          <label className="flex items-center gap-1.5 text-xs text-zinc-500">
            <input
              type="checkbox"
              name="timeUnknown"
              checked={timeUnknown}
              onChange={(e) => setTimeUnknown(e.target.checked)}
            />
            Không rõ giờ
          </label>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className={LABEL} htmlFor="gender">
            Giới tính
          </label>
          <select id="gender" name="gender" className={INPUT}>
            <option value="male">Nam</option>
            <option value="female">Nữ</option>
          </select>
        </div>
        <div className="space-y-1">
          <label className={LABEL} htmlFor="placeName">
            Nơi sinh
          </label>
          <input
            id="placeName"
            name="placeName"
            placeholder="Hà Nội"
            className={INPUT}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className={LABEL} htmlFor="longitude">
            Kinh độ (cho giờ chân thái dương)
          </label>
          <input
            id="longitude"
            name="longitude"
            type="number"
            step="0.01"
            min={-180}
            max={180}
            placeholder="105.85"
            className={INPUT}
          />
        </div>
        <div className="space-y-1">
          <label className={LABEL} htmlFor="birthRegion">
            Miền sinh (bắt buộc nếu sinh 1954–1975)
          </label>
          <select id="birthRegion" name="birthRegion" className={INPUT}>
            <option value="">—</option>
            <option value="north">Miền Bắc</option>
            <option value="central">Miền Trung</option>
            <option value="south">Miền Nam</option>
          </select>
        </div>
      </div>

      <div className="flex gap-4 text-sm">
        {calendar === "lunar" && (
          <label className="flex items-center gap-1.5">
            <input type="checkbox" name="leapMonth" /> Tháng nhuận
          </label>
        )}
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            name="trueSolarTimeEnabled"
            defaultChecked
          />
          Điều chỉnh giờ chân thái dương
        </label>
      </div>

      {state.error && (
        <p className="rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {state.error}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="w-full rounded bg-amber-600 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
      >
        {pending ? "Đang lập lá số…" : "Lập lá số"}
      </button>
    </form>
  );
}
