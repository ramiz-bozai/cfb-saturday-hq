import type { ReactNode } from "react";

export function Pill({
  tone,
  children,
}: {
  tone: string;
  children: ReactNode;
}) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function Metric({
  label,
  value,
  band,
  verdict,
  hint,
}: {
  label: string;
  value: string;
  band?: "low" | "mid" | "high";
  /** Plain-language readout shown above the number (e.g. Thin, High). */
  verdict?: string;
  /** One-line “so what” under the value. */
  hint?: string;
}) {
  return (
    <div className="metric">
      <span className="label">{label}</span>
      {verdict && <span className={`verdict ${band || ""}`}>{verdict}</span>}
      <span className={`value ${band || ""}`}>{value}</span>
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}
