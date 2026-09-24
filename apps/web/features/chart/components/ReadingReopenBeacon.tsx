"use client";

import { useEffect } from "react";

import { trackEvent } from "../../../lib/api";

export function ReadingReopenBeacon({ chartId }: { chartId: string }) {
  useEffect(() => {
    trackEvent("reading_reopened", { chartId });
  }, [chartId]);
  return null;
}
