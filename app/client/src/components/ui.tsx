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
}: {
  label: string;
  value: string;
  band?: "low" | "mid" | "high";
}) {
  return (
    <div className="metric">
      <span className="label">{label}</span>
      <span className={`value ${band || ""}`}>{value}</span>
    </div>
  );
}
