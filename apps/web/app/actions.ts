"use server";

import { redirect } from "next/navigation";

import { createChart, trackEventServer, type BirthPayload } from "../lib/api";

export interface FormState {
  error?: string;
}

export async function submitBirth(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const payload: BirthPayload = {
    calendar: formData.get("calendar") === "lunar" ? "lunar" : "solar",
    date: String(formData.get("date") ?? ""),
    time: formData.get("time") ? String(formData.get("time")) : undefined,
    timeUnknown: formData.get("timeUnknown") === "on",
    gender: formData.get("gender") === "female" ? "female" : "male",
    placeName: String(formData.get("placeName") ?? "") || undefined,
    birthRegion:
      (formData.get("birthRegion") as BirthPayload["birthRegion"]) || undefined,
    longitude: formData.get("longitude")
      ? Number(formData.get("longitude"))
      : undefined,
    leapMonth: formData.get("leapMonth") === "on",
    trueSolarTimeEnabled: formData.get("trueSolarTimeEnabled") === "on",
  };

  try {
    const chart = await createChart(payload);
    void trackEventServer("chart_created", { chartId: chart.id });
    redirect(`/chart/${chart.id}`);
  } catch (err) {
    if (err instanceof Error && "status" in err) {
      return { error: err.message };
    }
    throw err;
  }
}
