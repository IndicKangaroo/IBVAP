import { Check } from "lucide-react";
import { palette } from "../lib/palette.js";
import StatusPill from "./StatusPill.jsx";

export default function IncidentTable({ incidents, onUpdateStatus }) {
  return (
    <table className="w-full ibvap-mono text-[12px]">
      <thead>
        <tr className="text-left" style={{ color: palette.textMuted }}>
          <th className="px-3 py-1.5 font-normal">Zone</th>
          <th className="px-3 py-1.5 font-normal">Camera</th>
          <th className="px-3 py-1.5 font-normal">Track</th>
          <th className="px-3 py-1.5 font-normal">Severity</th>
          <th className="px-3 py-1.5 font-normal">Status</th>
          <th className="px-3 py-1.5 font-normal">Resolved at</th>
          <th className="px-3 py-1.5 font-normal">Actions</th>
        </tr>
      </thead>
      <tbody>
        {incidents.length === 0 && (
          <tr>
            <td colSpan={7} className="px-3 py-3" style={{ color: palette.textMuted }}>No incidents yet.</td>
          </tr>
        )}
        {incidents.map((inc) => (
          <tr key={inc.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: palette.border }}>
            <td className="px-3 py-1.5">{inc.event.zone_name || "—"}</td>
            <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{inc.event.camera_id}</td>
            <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{inc.event.track_id ?? "—"}</td>
            <td className="px-3 py-1.5" style={{ color: inc.severity === "HIGH" ? palette.high : palette.medium }}>{inc.severity}</td>
            <td className="px-3 py-1.5"><StatusPill status={inc.status} /></td>
            <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>
              {inc.resolved_at ? new Date(inc.resolved_at).toLocaleTimeString() : "—"}
            </td>
            <td className="px-3 py-1.5">
              <div className="flex gap-1.5">
                {inc.status !== "ACKNOWLEDGED" && inc.status !== "RESOLVED" && (
                  <button
                    onClick={() => onUpdateStatus(inc.id, "ACKNOWLEDGED")}
                    className="px-2 py-0.5 rounded-sm border hover:bg-white/[0.03]"
                    style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
                  >
                    Acknowledge
                  </button>
                )}
                {inc.status !== "RESOLVED" && (
                  <button
                    onClick={() => onUpdateStatus(inc.id, "RESOLVED")}
                    className="px-2 py-0.5 rounded-sm border hover:bg-white/[0.03] flex items-center gap-1"
                    style={{ borderColor: palette.borderLight, color: palette.resolved }}
                  >
                    <Check size={11} />Resolve
                  </button>
                )}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
