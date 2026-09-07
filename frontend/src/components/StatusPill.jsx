import { palette } from "../lib/palette.js";

export default function StatusPill({ status }) {
  const color = status === "ACTIVE" ? palette.high : status === "ACKNOWLEDGED" ? palette.medium : palette.resolved;
  const label = status === "ACTIVE" ? "Active" : status === "ACKNOWLEDGED" ? "Acknowledged" : "Resolved";
  return (
    <span
      className="ibvap-mono text-[11px] px-2 py-0.5 rounded-sm border inline-flex items-center gap-1.5 whitespace-nowrap"
      style={{ color, borderColor: color + "55", backgroundColor: color + "14" }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
