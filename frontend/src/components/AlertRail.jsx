import { palette, timeAgo } from "../lib/palette.js";
import StatusPill from "./StatusPill.jsx";

function IncidentCard({ incident, onSelect }) {
  const barColor = incident.severity === "HIGH" ? palette.high : palette.medium;
  return (
    <button
      onClick={() => onSelect(incident.id)}
      className="w-full text-left flex gap-3 px-3 py-2.5 border-b hover:bg-white/[0.02] transition-colors"
      style={{ borderColor: palette.border }}
    >
      <div className="w-1 rounded-full self-stretch shrink-0" style={{ backgroundColor: barColor }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="ibvap-mono text-[13px]" style={{ color: palette.textPrimary }}>
            {incident.event.zone_name || "Unzoned"}
          </span>
          <StatusPill status={incident.status} />
        </div>
        <div className="ibvap-mono text-[11px] mt-1 flex items-center gap-3" style={{ color: palette.textSecondary }}>
          <span>{incident.event.camera_id}</span>
          <span>track {incident.event.track_id ?? "—"}</span>
          <span>{incident.event.cls ?? "—"}</span>
          <span>{incident.event.confidence != null ? `${Math.round(incident.event.confidence * 100)}%` : "—"}</span>
        </div>
      </div>
      <div className="ibvap-mono text-[11px] shrink-0" style={{ color: palette.textMuted }}>
        {timeAgo(incident.created_at)}
      </div>
    </button>
  );
}

export default function AlertRail({ incidents, onSelect }) {
  return (
    <div className="w-[300px] border-l shrink-0 flex flex-col min-h-0" style={{ borderColor: palette.border }}>
      <div className="px-3 py-2 text-[11px] uppercase tracking-wide shrink-0" style={{ color: palette.textMuted }}>
        Alert feed
      </div>
      <div className="flex-1 overflow-auto">
        {incidents.length === 0 && (
          <div className="px-3 py-3 text-[12px]" style={{ color: palette.textMuted }}>
            No incidents yet.
          </div>
        )}
        {incidents.map((inc) => (
          <IncidentCard key={inc.id} incident={inc} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}
