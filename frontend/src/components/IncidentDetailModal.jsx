import { X } from "lucide-react";
import { palette } from "../lib/palette.js";
import { evidenceUrl } from "../lib/api.js";
import StatusPill from "./StatusPill.jsx";

export default function IncidentDetailModal({ incident, onClose }) {
  if (!incident) return null;
  const imgUrl = evidenceUrl(incident.event.evidence_path);

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-10"
      style={{ backgroundColor: "#00000088" }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[420px] rounded-sm border p-4"
        style={{ backgroundColor: palette.panel, borderColor: palette.borderLight }}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-[13px] font-medium" style={{ color: palette.textPrimary }}>Incident detail</span>
          <button onClick={onClose} style={{ color: palette.textMuted }}><X size={16} /></button>
        </div>

        {imgUrl && (
          <img src={imgUrl} alt="Evidence" className="w-full rounded-sm mb-3 border" style={{ borderColor: palette.border }} />
        )}

        <div className="ibvap-mono text-[12px] space-y-1.5" style={{ color: palette.textSecondary }}>
          <div>id: <span style={{ color: palette.textPrimary }}>{incident.id}</span></div>
          <div>zone: <span style={{ color: palette.textPrimary }}>{incident.event.zone_name || "—"}</span></div>
          <div>camera: <span style={{ color: palette.textPrimary }}>{incident.event.camera_id}</span></div>
          <div>track: <span style={{ color: palette.textPrimary }}>{incident.event.track_id ?? "—"}</span></div>
          <div>class: <span style={{ color: palette.textPrimary }}>{incident.event.cls ?? "—"}</span></div>
          <div>confidence: <span style={{ color: palette.textPrimary }}>
            {incident.event.confidence != null ? `${Math.round(incident.event.confidence * 100)}%` : "—"}
          </span></div>
          <div>created: <span style={{ color: palette.textPrimary }}>{new Date(incident.created_at).toLocaleString()}</span></div>
        </div>

        <div className="mt-4"><StatusPill status={incident.status} /></div>
        {/* <div className="flex items-center gap-2 mt-4">
          {incident.status !== "ACKNOWLEDGED" && incident.status !== "RESOLVED" && (
            <button
              onClick={() => onUpdateStatus(incident.id, "ACKNOWLEDGED")}
              className="text-[12px] px-2.5 py-1 rounded-sm border hover:bg-white/[0.03]"
              style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
            >
              Acknowledge
            </button>
          )}
          {incident.status !== "RESOLVED" && (
            <button
              onClick={() => onUpdateStatus(incident.id, "RESOLVED")}
              className="text-[12px] px-2.5 py-1 rounded-sm border hover:bg-white/[0.03]"
              style={{ borderColor: palette.borderLight, color: palette.resolved }}
            >
              Resolve
            </button>
          )}
        </div> */}
      </div>
    </div>
  );
}
