export function unitLabel(group: string | null | undefined): string {
  if (!group) return "-";
  if (group === "DB") return "Secondary";
  if (group === "ST") return "Special Teams";
  return group;
}

export function fmtPct(value: unknown): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "-";
  return `${Math.round(n * 100)}%`;
}

export function fmtNum(value: unknown, digits = 1): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "-";
  return n.toFixed(digits);
}

/** Whole counts: yards, attempts, TDs, tackles, stars, etc. */
export function fmtInt(value: unknown): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "-";
  return String(Math.round(n));
}

export type Band = "low" | "mid" | "high";

/** For returning % / continuity 0-100 or 0-1. */
export function bandFromScore(value: unknown, asPercent = false): Band {
  let n = Number(value);
  if (value == null || Number.isNaN(n)) return "mid";
  if (!asPercent && n <= 1.5) n = n * 100;
  if (n >= 70) return "high";
  if (n >= 40) return "mid";
  return "low";
}

/** Fan-facing verdict for continuity / returning scores (higher = better). */
export function continuityVerdict(value: unknown, asPercent = false): string {
  const band = bandFromScore(value, asPercent);
  if (band === "high") return "Strong";
  if (band === "mid") return "Mixed";
  return "Thin";
}

/**
 * Transfer dependency is inverted: high score = more risk.
 * Returns band for coloring (low=danger) plus a verdict word.
 */
export function dependencyBand(value: unknown): Band {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "mid";
  if (n >= 70) return "low";
  if (n >= 40) return "mid";
  return "high";
}

export function dependencyVerdict(value: unknown): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "-";
  if (n >= 70) return "Heavy";
  if (n >= 40) return "Moderate";
  return "Light";
}

/** Signed production delta (prior production score units). */
export function netProductionVerdict(value: unknown): { band: Band; verdict: string } {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return { band: "mid", verdict: "Even" };
  if (n > 5) return { band: "high", verdict: "Gained" };
  if (n < -5) return { band: "low", verdict: "Lost" };
  return { band: "mid", verdict: "Even" };
}

/** Average talent delta on ~0-1 recruiting scale. */
export function netTalentVerdict(value: unknown): { band: Band; verdict: string } {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return { band: "mid", verdict: "Even" };
  if (n > 0.02) return { band: "high", verdict: "Gained" };
  if (n < -0.02) return { band: "low", verdict: "Lost" };
  return { band: "mid", verdict: "Even" };
}

/** @deprecated Prefer netProductionVerdict / netTalentVerdict. */
export function netVerdict(value: unknown): { band: Band; verdict: string } {
  return netProductionVerdict(value);
}

export function riskTone(risk: string | null | undefined): string {
  const r = (risk || "").toLowerCase();
  if (r === "high") return "danger";
  if (r === "elevated") return "amber";
  if (r === "manageable") return "ok";
  return "muted";
}

export function impactTone(cls: string | null | undefined, kind: "in" | "out" = "in"): string {
  const c = (cls || "").toLowerCase();
  if (c === "impact") return kind === "out" ? "danger" : "amber";
  if (c === "unknown") return "muted";
  return "muted";
}

export function qbTone(cls: string | null | undefined): string {
  const c = cls || "";
  if (c === "Major uncertainty") return "danger";
  if (c === "Unproven competition") return "amber";
  if (c === "High-upside transfer") return "amber";
  if (c === "Experienced but limited") return "muted";
  if (c.startsWith("Proven elite")) return "trust";
  if (c.startsWith("Proven")) return "ok";
  return "muted";
}

export const QB_CLASS_ORDER = [
  "Major uncertainty",
  "Unproven competition",
  "High-upside transfer",
  "Experienced but limited",
  "Proven average starter",
  "Proven elite starter",
];
