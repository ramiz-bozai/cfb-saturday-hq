export function unitLabel(group: string | null | undefined): string {
  if (!group) return "—";
  if (group === "DB") return "Secondary";
  if (group === "ST") return "Special teams";
  return group;
}

export function fmtPct(value: unknown): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "—";
  return `${Math.round(n * 100)}%`;
}

export function fmtNum(value: unknown, digits = 1): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

/** Whole counts: yards, attempts, TDs, tackles, stars, etc. */
export function fmtInt(value: unknown): string {
  const n = Number(value);
  if (value == null || Number.isNaN(n)) return "—";
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

export function riskTone(risk: string | null | undefined): string {
  const r = (risk || "").toLowerCase();
  if (r === "high") return "danger";
  if (r === "elevated") return "amber";
  if (r === "manageable") return "ok";
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
