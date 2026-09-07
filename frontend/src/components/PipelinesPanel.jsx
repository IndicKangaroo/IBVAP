import { useEffect, useState } from "react";
import { Square, Plus, FileText, X } from "lucide-react";
import { palette } from "../lib/palette.js";
import * as api from "../lib/api.js";

function LogViewer({ cameraId, onClose }) {
  const [log, setLog] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLog = () =>
      api.getPipelineLog(cameraId, 100)
        .then((r) => setLog(r.log || "(no output yet)"))
        .catch((e) => setError(e.message));
    fetchLog();
    const id = setInterval(fetchLog, 2000);
    return () => clearInterval(id);
  }, [cameraId]);

  return (
    <div className="fixed inset-0 flex items-center justify-center z-30" style={{ backgroundColor: "#00000088" }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[640px] max-h-[70vh] flex flex-col rounded-sm border p-3"
        style={{ backgroundColor: palette.panel, borderColor: palette.borderLight }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="ibvap-mono text-[12px]" style={{ color: palette.textPrimary }}>{cameraId} — pipeline log (live, refreshes every 2s)</span>
          <button onClick={onClose} style={{ color: palette.textMuted }}><X size={16} /></button>
        </div>
        <pre
          className="ibvap-mono text-[11px] whitespace-pre-wrap overflow-auto flex-1 p-2 rounded-sm"
          style={{ backgroundColor: "#0B0F14", color: error ? palette.high : palette.textSecondary }}
        >
          {error || log}
        </pre>
        <p className="ibvap-mono text-[10px] mt-2" style={{ color: palette.textMuted }}>
          Empty for a while after starting is usually cold model loading (torch/YOLO/EasyOCR) — this can take
          anywhere from a few seconds to around a minute depending on the machine, not a hang by itself. If it's
          still empty after a couple of minutes, or you see a Python traceback above, something's actually wrong.
        </p>
      </div>
    </div>
  );
}

export default function PipelinesPanel({ onAddCamera }) {
  const [pipelines, setPipelines] = useState([]);
  const [stoppingId, setStoppingId] = useState(null);
  const [viewingLogFor, setViewingLogFor] = useState(null);

  const refresh = () => api.getPipelines().then(setPipelines).catch(() => {});

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, []);

  const handleStop = async (cameraId) => {
    setStoppingId(cameraId);
    try {
      await api.stopPipeline(cameraId);
      await refresh();
    } catch (e) {
      alert(`Failed to stop ${cameraId}: ${e.message}`);
    } finally {
      setStoppingId(null);
    }
  };

  return (
    <div className="border-b" style={{ borderColor: palette.border }}>
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-[11px] uppercase tracking-wide" style={{ color: palette.textMuted }}>
          Running pipelines
        </span>
        <button
          onClick={onAddCamera}
          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-sm border hover:bg-white/[0.03]"
          style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
        >
          <Plus size={11} /> Add camera
        </button>
      </div>
      {pipelines.length === 0 ? (
        <div className="px-3 pb-2 ibvap-mono text-[11px]" style={{ color: palette.textMuted }}>
          No cameras running. Add one — no terminal needed.
        </div>
      ) : (
        <div className="pb-1">
          {pipelines.map((p) => (
            <div key={p.camera_id} className="flex items-center justify-between px-3 py-1">
              <div className="ibvap-mono text-[11px]" style={{ color: palette.textSecondary }}>
                <span style={{ color: palette.textPrimary }}>{p.camera_id}</span>
                {" · "}
                <span style={{ color: p.running ? palette.resolved : palette.high }}>
                  {p.running ? "running" : "stopped"}
                </span>
                {" · pid "}{p.pid}
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setViewingLogFor(p.camera_id)}
                  className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-sm border"
                  style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
                  title="View this camera's pipeline output — no terminal needed"
                >
                  <FileText size={9} /> Log
                </button>
                <button
                  onClick={() => handleStop(p.camera_id)}
                  disabled={stoppingId === p.camera_id}
                  className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-sm border disabled:opacity-40"
                  style={{ borderColor: palette.borderLight, color: palette.high }}
                  title="Stop this camera's pipeline"
                >
                  <Square size={9} /> Stop
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {viewingLogFor && (
        <LogViewer cameraId={viewingLogFor} onClose={() => setViewingLogFor(null)} />
      )}
    </div>
  );
}
