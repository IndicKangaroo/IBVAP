import { useEffect, useState } from "react";
import { X, Loader2 } from "lucide-react";
import { palette } from "../lib/palette.js";
import * as api from "../lib/api.js";
import ZoneCanvasEditor from "./ZoneCanvasEditor.jsx";

const STEPS = ["source", "intrusion-zone", "anpr-zone", "review"];

export default function AddCameraModal({ onClose, onStarted }) {
  const [step, setStep] = useState(0);
  const [sampleVideos, setSampleVideos] = useState([]);
  const [cameraId, setCameraId] = useState("");
  const [sourceMode, setSourceMode] = useState("sample"); // "sample" | "webcam" | "custom"
  const [selectedSample, setSelectedSample] = useState("");
  const [webcamIndex, setWebcamIndex] = useState("0");
  const [customSource, setCustomSource] = useState("");
  const [intrusionPoints, setIntrusionPoints] = useState([]);
  const [anprPoints, setAnprPoints] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getSampleVideos().then(setSampleVideos).catch(() => {});
  }, []);

  const source =
    sourceMode === "sample" ? selectedSample : sourceMode === "webcam" ? webcamIndex : customSource;

  const canProceedFromSource = cameraId.trim().length > 0 && source.trim().length > 0;

  const handleStart = async () => {
    setBusy(true);
    setError(null);
    try {
      let zonesPath = null;
      let anprZonesPath = null;

      if (intrusionPoints.length >= 3) {
        const res = await api.createZone({
          cameraId, kind: "intrusion", zoneId: "restricted-1",
          name: "Restricted Zone", polygon: intrusionPoints,
        });
        zonesPath = res.path;
      }
      if (anprPoints.length >= 3) {
        const res = await api.createZone({
          cameraId, kind: "anpr", zoneId: "checkpoint-1",
          name: "ANPR Checkpoint", polygon: anprPoints,
        });
        anprZonesPath = res.path;
      }

      await api.startPipeline({ cameraId, source, zonesPath, anprZonesPath });
      onStarted?.(cameraId);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center z-20" style={{ backgroundColor: "#00000088" }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[560px] max-h-[85vh] overflow-auto rounded-sm border p-4"
        style={{ backgroundColor: palette.panel, borderColor: palette.borderLight }}
      >
        <div className="flex items-center justify-between mb-4">
          <span className="text-[14px] font-medium" style={{ color: palette.textPrimary }}>Add camera</span>
          <button onClick={onClose} style={{ color: palette.textMuted }}><X size={16} /></button>
        </div>

        {STEPS[step] === "source" && (
          <div className="space-y-3">
            <div>
              <label className="ibvap-mono text-[11px] block mb-1" style={{ color: palette.textMuted }}>Camera ID</label>
              <input
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                placeholder="CAM-03"
                className="ibvap-mono w-full text-[13px] px-2 py-1.5 rounded-sm border bg-transparent"
                style={{ borderColor: palette.borderLight, color: palette.textPrimary }}
              />
            </div>

            <div>
              <label className="ibvap-mono text-[11px] block mb-1" style={{ color: palette.textMuted }}>Source</label>
              <div className="flex gap-2 mb-2">
                {[["sample", "Sample clip"], ["webcam", "Webcam"], ["custom", "Custom path"]].map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setSourceMode(key)}
                    className="text-[11px] px-2.5 py-1 rounded-sm border"
                    style={{
                      borderColor: sourceMode === key ? palette.medium : palette.borderLight,
                      color: sourceMode === key ? palette.textPrimary : palette.textMuted,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {sourceMode === "sample" && (
                <select
                  value={selectedSample}
                  onChange={(e) => setSelectedSample(e.target.value)}
                  className="ibvap-mono w-full text-[13px] px-2 py-1.5 rounded-sm border bg-transparent"
                  style={{ borderColor: palette.borderLight, color: palette.textPrimary }}
                >
                  <option value="" style={{ color: "#000" }}>Select a clip…</option>
                  {sampleVideos.map((v) => (
                    <option key={v} value={v} style={{ color: "#000" }}>{v}</option>
                  ))}
                </select>
              )}
              {sourceMode === "webcam" && (
                <input
                  value={webcamIndex}
                  onChange={(e) => setWebcamIndex(e.target.value)}
                  placeholder="0"
                  className="ibvap-mono w-full text-[13px] px-2 py-1.5 rounded-sm border bg-transparent"
                  style={{ borderColor: palette.borderLight, color: palette.textPrimary }}
                />
              )}
              {sourceMode === "custom" && (
                <input
                  value={customSource}
                  onChange={(e) => setCustomSource(e.target.value)}
                  placeholder="path/to/video.mp4 or rtsp://..."
                  className="ibvap-mono w-full text-[13px] px-2 py-1.5 rounded-sm border bg-transparent"
                  style={{ borderColor: palette.borderLight, color: palette.textPrimary }}
                />
              )}
            </div>

            <p className="ibvap-mono text-[11px]" style={{ color: palette.textMuted }}>
              Zone drawing next is optional — skip it if you just want detection/tracking with no intrusion or ANPR zones yet.
            </p>
          </div>
        )}

        {STEPS[step] === "intrusion-zone" && (
          <div>
            <p className="ibvap-mono text-[11px] mb-2" style={{ color: palette.textMuted }}>
              Click to outline a restricted zone (optional). Skip if not needed for this camera.
            </p>
            <ZoneCanvasEditor source={source} onPolygonChange={setIntrusionPoints} />
          </div>
        )}

        {STEPS[step] === "anpr-zone" && (
          <div>
            <p className="ibvap-mono text-[11px] mb-2" style={{ color: palette.textMuted }}>
              Click to outline an ANPR checkpoint zone (optional, only relevant for vehicle traffic).
            </p>
            <ZoneCanvasEditor source={source} onPolygonChange={setAnprPoints} />
          </div>
        )}

        {STEPS[step] === "review" && (
          <div className="ibvap-mono text-[12px] space-y-1.5" style={{ color: palette.textSecondary }}>
            <div>camera id: <span style={{ color: palette.textPrimary }}>{cameraId}</span></div>
            <div>source: <span style={{ color: palette.textPrimary }}>{source}</span></div>
            <div>intrusion zone: <span style={{ color: palette.textPrimary }}>{intrusionPoints.length >= 3 ? `${intrusionPoints.length} points` : "none"}</span></div>
            <div>ANPR zone: <span style={{ color: palette.textPrimary }}>{anprPoints.length >= 3 ? `${anprPoints.length} points` : "none"}</span></div>
            <p className="pt-2" style={{ color: palette.textMuted }}>
              Model loading (YOLO/tracker, and OCR if an ANPR zone was drawn) can take anywhere from a few seconds to
              around a minute depending on the machine — the camera will show as running immediately, but events may
              take a moment to start appearing. That's normal, not a hang.
            </p>
          </div>
        )}

        {error && (
          <div className="ibvap-mono text-[11px] mt-3 p-2 rounded-sm border" style={{ borderColor: palette.high, color: palette.high, backgroundColor: palette.high + "14" }}>
            {error}
          </div>
        )}

        <div className="flex items-center justify-between mt-5">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="text-[12px] px-3 py-1.5 rounded-sm border disabled:opacity-40"
            style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
          >
            Back
          </button>

          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={step === 0 && !canProceedFromSource}
              className="text-[12px] px-3 py-1.5 rounded-sm border disabled:opacity-40"
              style={{ borderColor: palette.medium, color: palette.textPrimary }}
            >
              {step === 0 ? "Continue" : "Next"}
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={busy}
              className="text-[12px] px-3 py-1.5 rounded-sm border flex items-center gap-1.5"
              style={{ borderColor: palette.resolved, color: palette.resolved }}
            >
              {busy && <Loader2 size={12} className="animate-spin" />}
              {busy ? "Starting…" : "Start camera"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
