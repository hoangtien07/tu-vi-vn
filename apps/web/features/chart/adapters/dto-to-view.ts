/** CanonicalChartDTO → Renhuai-style view model (adapter boundary — SPEC Phase 4). */

export interface StarView {
  key: string;
  name: string;
  brightness?: string;
  mutagen?: string;
}

export interface PalaceView {
  index: number;
  name: string;
  nameKey: string;
  stemBranch: string;
  isBodyPalace: boolean;
  majorStars: StarView[];
  minorStars: StarView[];
  decadalRange?: [number, number];
  ages: number[];
}

export interface ChartView {
  palaces: PalaceView[];
  sign: string;
  zodiac: string;
  fiveElementsClass: string;
  lunarDate: string;
  solarDate: string;
  soul: string;
  body: string;
  patternNames: string[];
}

interface RawStar {
  key: string;
  name?: string;
  brightness?: string;
  mutagen?: string;
}

interface RawPalace {
  index: number;
  name: string;
  nameKey: string;
  heavenlyStem: string;
  earthlyBranch: string;
  isBodyPalace: boolean;
  majorStars: RawStar[];
  minorStars: RawStar[];
  decadal?: { range?: [number, number] };
  ages: number[];
}

function star(s: RawStar): StarView {
  return {
    key: s.key,
    name: s.name ?? s.key,
    brightness: s.brightness || undefined,
    mutagen: s.mutagen || undefined,
  };
}

export function toChartView(chartJson: {
  chart: Record<string, unknown>;
}): ChartView {
  const c = chartJson.chart;
  const palaces = (c.palaces as RawPalace[]).map((p) => ({
    index: p.index,
    name: p.name,
    nameKey: p.nameKey,
    stemBranch: `${p.heavenlyStem} ${p.earthlyBranch}`,
    isBodyPalace: p.isBodyPalace,
    majorStars: p.majorStars.map(star),
    minorStars: p.minorStars.map(star),
    decadalRange: p.decadal?.range,
    ages: p.ages ?? [],
  }));
  const patterns = (c.patterns as { name?: string }[] | undefined) ?? [];
  return {
    palaces,
    sign: String(c.sign ?? ""),
    zodiac: String(c.zodiac ?? ""),
    fiveElementsClass: String(c.fiveElementsClass ?? ""),
    lunarDate: String(c.lunarDate ?? ""),
    solarDate: String(c.solarDate ?? ""),
    soul: String(c.soul ?? ""),
    body: String(c.body ?? ""),
    patternNames: patterns.map((p) => p.name ?? "").filter(Boolean),
  };
}
