import type { ReactNode } from "react";

export function Pill({
  tone,
  children,
  title,
}: {
  tone: string;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      className={`pill ${tone}${title ? " has-tip" : ""}`}
      data-tip={title}
      tabIndex={title ? 0 : undefined}
    >
      {children}
    </span>
  );
}

export function Metric({
  label,
  value,
  band,
  verdict,
  hint,
  tip,
}: {
  label: string;
  value: string;
  band?: "low" | "mid" | "high";
  /** Plain-language readout shown above the number (e.g. Thin, High). */
  verdict?: string;
  /** One-line “so what” under the value. */
  hint?: string;
  /** Hover tooltip (e.g. why a value is dashed). */
  tip?: string;
}) {
  return (
    <div
      className={`metric${tip ? " has-tip" : ""}`}
      data-tip={tip || undefined}
      tabIndex={tip ? 0 : undefined}
    >
      <span className="label">{label}</span>
      {verdict && <span className={`verdict ${band || ""}`}>{verdict}</span>}
      <span className={`value ${band || ""}`}>{value}</span>
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}
