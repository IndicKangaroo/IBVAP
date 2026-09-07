import { useState, useEffect } from "react";
import { ShieldAlert, Wifi, WifiOff, AlertTriangle } from "lucide-react";
import { palette } from "./lib/palette.js";
import { useLiveBackend } from "./lib/useLiveBackend.js";
import CameraGrid from "./components/CameraGrid.jsx";
import CameraPanel from "./components/CameraPanel.jsx";
import AlertRail from "./components/AlertRail.jsx";
import IncidentTable from "./components/IncidentTable.jsx";
import ANPRTable from "./components/ANPRTable.jsx";
import IncidentDetailModal from "./components/IncidentDetailModal.jsx";
import PipelinesPanel from "./components/PipelinesPanel.jsx";
import AddCameraModal from "./components/AddCameraModal.jsx";

const STATUS_LABEL = {
  connecting: "connecting…",
  connected: "connected",
  reconnected: "connected",
  disconnected: "disconnected — retrying",
  reconnecting: "reconnecting…",
  closed: "closed",
};

function ConnectionIndicator({ status }) {
  const isUp = status === "connected" || status === "reconnected";
  const color = isUp ? palette.live : status === "connecting" ? palette.medium : palette.high;
  const Icon = isUp ? Wifi : WifiOff;
  return (
    <div className="flex items-center gap-1.5 ibvap-mono text-[11px]" style={{ color }}>
      <Icon size={12} />
      {STATUS_LABEL[status] || status}
    </div>
  );
}

export default function App() {
  const {
    incidents,
    anprResults,
    cameras,
    connectionStatus,
    loadError,
    updateIncidentStatus,
    refreshSnapshot,
  } = useLiveBackend();

  const [selectedCameraId, setSelectedCameraId] = useState(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [tab, setTab] = useState("incidents");
  const [showAddCamera, setShowAddCamera] = useState(false);

  // Default the selected camera to the first one once cameras load —
  // can't pick a default before we actually know what cameras exist.
  useEffect(() => {
    if (!selectedCameraId && cameras.length > 0) {
      setSelectedCameraId(cameras[0].id);
    }
  }, [cameras, selectedCameraId]);

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId) || null;

  const handleUpdateStatus = (id, status) => {
    updateIncidentStatus(id, status).catch((e) => {
      console.error("Failed to update incident status:", e);
      alert(`Failed to update incident: ${e.message}`);
    });
  };

  return (
    <div className="ibvap-sans w-full h-full flex flex-col" style={{ backgroundColor: palette.bg, color: palette.textPrimary }}>
      {/* header */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0" style={{ borderColor: palette.border }}>
        <div className="flex items-center gap-2.5">
          <ShieldAlert size={18} style={{ color: palette.medium }} />
          <span className="text-[14px] font-medium">IBVAP · Command center</span>
        </div>
        <ConnectionIndicator status={connectionStatus} />
      </div>

      {loadError && (
        <div
          className="flex items-center gap-2 px-4 py-2 ibvap-mono text-[12px] border-b shrink-0"
          style={{ backgroundColor: palette.high + "14", borderColor: palette.border, color: palette.high }}
        >
          <AlertTriangle size={13} />
          Couldn't reach the backend: {loadError}. Is it running? (`uvicorn backend.main:app --reload`)
        </div>
      )}

      {/* main three-pane layout */}
      <div className="flex flex-1 min-h-0">
        <div className="w-[200px] border-r shrink-0 flex flex-col" style={{ borderColor: palette.border }}>
          <PipelinesPanel onAddCamera={() => setShowAddCamera(true)} />
          <CameraGrid
            cameras={cameras}
            incidents={incidents}
            selectedCameraId={selectedCameraId}
            onSelect={setSelectedCameraId}
          />
        </div>
        <CameraPanel cameraId={selectedCameraId} incidents={incidents} />
        <AlertRail incidents={incidents} onSelect={setSelectedIncidentId} />
      </div>

      {/* bottom: incidents / anpr tabs */}
      <div className="border-t shrink-0" style={{ borderColor: palette.border, height: 220 }}>
        <div className="flex border-b" style={{ borderColor: palette.border }}>
          {[
            { key: "incidents", label: "Incident timeline" },
            { key: "anpr", label: "ANPR log" },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="px-4 py-2 text-[12px] border-b-2 -mb-px transition-colors"
              style={{
                borderColor: tab === t.key ? palette.medium : "transparent",
                color: tab === t.key ? palette.textPrimary : palette.textMuted,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="overflow-auto" style={{ height: 220 - 37 }}>
          {tab === "incidents" ? (
            <IncidentTable incidents={incidents} onUpdateStatus={handleUpdateStatus} />
          ) : (
            <ANPRTable results={anprResults} />
          )}
        </div>
      </div>

      <IncidentDetailModal
        incident={selectedIncident}
        onClose={() => setSelectedIncidentId(null)}
        onUpdateStatus={handleUpdateStatus}
      />

      {showAddCamera && (
        <AddCameraModal
          onClose={() => setShowAddCamera(false)}
          onStarted={() => refreshSnapshot()}
        />
      )}

      <div
        className="ibvap-mono text-[10px] px-4 py-1.5 border-t text-center shrink-0"
        style={{ borderColor: palette.border, color: palette.textMuted }}
      >
        live system · connected to {import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000"}
      </div>
    </div>
  );
}
