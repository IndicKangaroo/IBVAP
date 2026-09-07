import { palette } from "../lib/palette.js";
import { evidenceUrl } from "../lib/api.js";

export default function CameraPanel({ cameraId, incidents }) {
  const latestWithEvidence = incidents.find(
    (i) => i.event.camera_id === cameraId && i.event.evidence_path
  );
  const imgUrl = latestWithEvidence ? evidenceUrl(latestWithEvidence.event.evidence_path) : null;

  return (
    // <div className="flex-1 min-w-0 p-4 overflow-auto">
    <div className="w-[55%] p-4 overflow-auto">

      <div className="ibvap-mono text-[12px] mb-2" style={{ color: palette.textSecondary }}>
        {cameraId || "No camera selected"}
      </div>
      <div className="rounded-sm overflow-hidden border" style={{ borderColor: palette.border, backgroundColor: "#0B0F14" }}>
        {imgUrl ? (
          <img src={imgUrl} alt={`Latest evidence snapshot for ${cameraId}`} className="w-full h-auto block" />
        ) : (
          <div
            className="w-full flex items-center justify-center ibvap-mono text-[12px]"
            style={{ height: 320, color: palette.textMuted }}
          >
            no evidence snapshot yet for this camera
          </div>
        )}
        <div
          className="ibvap-mono text-[11px] px-3 py-2 border-t flex items-center justify-between"
          style={{ borderColor: palette.border, color: palette.textMuted, backgroundColor: palette.panel }}
        >
          <span>{imgUrl ? "latest evidence snapshot" : "no snapshot available"}</span>
          <span>live overlay stream: not yet implemented (see blueprint §5)</span>
        </div>
      </div>
    </div>
  );
}
