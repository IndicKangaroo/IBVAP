import { Camera as CameraIcon } from "lucide-react";
import { palette, timeAgo } from "../lib/palette.js";

export default function CameraGrid({ cameras, incidents, selectedCameraId, onSelect }) {
  const latestEventFor = (camId) => {
    const match = incidents.find((i) => i.event.camera_id === camId);
    return match ? timeAgo(match.created_at) : "no events yet";
  };

  return (
    <>
      <div className="px-3 py-2 text-[11px] uppercase tracking-wide" style={{ color: palette.textMuted }}>
        Cameras
      </div>
      {cameras.length === 0 && (
        <div className="px-3 py-2 text-[12px]" style={{ color: palette.textMuted }}>
          No cameras registered yet — add one above.
        </div>
      )}
      {cameras.map((cam) => (
        <button
          key={cam.id}
          onClick={() => onSelect(cam.id)}
          className="text-left px-3 py-2.5 border-t hover:bg-white/[0.02] transition-colors"
          style={{
            borderColor: palette.border,
            backgroundColor: selectedCameraId === cam.id ? palette.panelAlt : "transparent",
          }}
        >
          <div className="flex items-center gap-2">
            <CameraIcon size={13} style={{ color: palette.textSecondary }} />
            {/* cam.name is always null today (no endpoint sets it yet) — falls back to the raw id */}
            <span className="ibvap-mono text-[13px]" style={{ color: palette.textPrimary }}>{cam.name || cam.id}</span>
          </div>
          <div className="ibvap-mono text-[10px] mt-1" style={{ color: palette.textMuted }}>
            last event: {latestEventFor(cam.id)}
          </div>
        </button>
      ))}
    </>
  );
}
