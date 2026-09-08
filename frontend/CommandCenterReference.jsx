import React, { useState, useRef, useCallback } from "react";
import { ShieldAlert, Camera as CameraIcon, Check, Wifi, X, RotateCcw } from "lucide-react";

// ---------------------------------------------------------------------
// Design intent (for whoever reads this file next):
// This is an operations console, not a marketing dashboard — modeled on
// the instrument-panel legibility of ATC/SOC monitoring tools rather
// than a generic rounded-card SaaS layout. Deep charcoal-navy base
// (not pure black), IBM Plex Sans for UI chrome / IBM Plex Mono for
// telemetry (IDs, timestamps, coordinates — genuinely data, not
// decoration). Color carries fixed meaning throughout: amber = caution,
// warm red-orange = critical/active, green = resolved/healthy. Severity
// is encoded as a left accent bar; status is a separate text pill — two
// different visual channels for two different axes of the same record.
// ---------------------------------------------------------------------

const palette = {
  bg: "#10141B",
  panel: "#161B24",
  panelAlt: "#1B212C",
  border: "#262E3A",
  borderLight: "#323C4A",
  textPrimary: "#E7EAEE",
  textSecondary: "#8B94A3",
  textMuted: "#5C6472",
  high: "#E8593E",
  medium: "#E3A73E",
  resolved: "#4FA97C",
  live: "#4FA97C",
};

const fontStack = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
  .ibvap-sans { font-family: 'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif; }
  .ibvap-mono { font-family: 'IBM Plex Mono', ui-monospace, 'SF Mono', monospace; }
  @keyframes ibvap-slide-in {
    0% { transform: translateY(-10px); opacity: 0; }
    100% { transform: translateY(0); opacity: 1; }
  }
  .ibvap-new-row { animation: ibvap-slide-in 0.35s ease-out; }
`;

// ---------------------------------------------------------------------
// Mock data — shaped exactly like the real backend's IncidentOut /
// ANPRResultOut / CameraOut (see FRONTEND_BLUEPRINT.md §4). Swap this
// for real fetch() + WebSocket calls against the live backend; nothing
// about the component structure below needs to change to do that.
// ---------------------------------------------------------------------

const INITIAL_CAMERAS = [
  { id: "CAM-01", name: null, location_label: null, status: "ONLINE", last_seen_at: "2026-09-02T14:20:00Z" },
  { id: "CAM-02", name: null, location_label: null, status: "ONLINE", last_seen_at: "2026-09-02T13:55:00Z" },
];

const INITIAL_INCIDENTS = [
  {
    id: "inc-1", event_id: "evt-1", severity: "HIGH", status: "ACTIVE",
    created_at: "2026-09-02T14:20:03.100Z", resolved_at: null,
    event: { id: "evt-1", camera_id: "CAM-01", zone_id: "restricted-1", zone_name: "Restricted Path", track_id: 27, type: "INTRUSION", cls: "person", confidence: 0.91, timestamp: 1788400803.1, evidence_path: null, created_at: "2026-09-02T14:20:03.090Z" },
  },
  {
    id: "inc-2", event_id: "evt-2", severity: "MEDIUM", status: "ACKNOWLEDGED",
    created_at: "2026-09-02T14:11:40.000Z", resolved_at: null,
    event: { id: "evt-2", camera_id: "CAM-01", zone_id: "restricted-1", zone_name: "Restricted Path", track_id: 21, type: "INTRUSION", cls: "person", confidence: 0.62, timestamp: 1788400300.0, evidence_path: null, created_at: "2026-09-02T14:11:39.950Z" },
  },
  {
    id: "inc-3", event_id: "evt-3", severity: "HIGH", status: "RESOLVED",
    created_at: "2026-09-02T13:48:12.000Z", resolved_at: "2026-09-02T13:52:00.000Z",
    event: { id: "evt-3", camera_id: "CAM-02", zone_id: "checkpoint-1", zone_name: "ANPR Checkpoint", track_id: 4, type: "INTRUSION", cls: "truck", confidence: 0.85, timestamp: 1788398892.0, evidence_path: null, created_at: "2026-09-02T13:48:11.900Z" },
  },
];

const INITIAL_ANPR = [
  { id: "anpr-1", camera_id: "CAM-02", track_id: 4, vehicle_type: "truck", vehicle_color: "white", vehicle_color_confidence: 0.74, plate_text: "KA01AB1234", confidence: 0.83, plausible: true, timestamp: 1788398892.0, evidence_path: null, created_at: "2026-09-02T13:48:12.500Z" },
  { id: "anpr-2", camera_id: "CAM-02", track_id: 5, vehicle_type: "car", vehicle_color: "blue", vehicle_color_confidence: 0.70, plate_text: null, confidence: 0.0, plausible: false, timestamp: 1788399200.0, evidence_path: null, created_at: "2026-09-02T13:53:20.000Z" },
];

let nextId = 4;

function timeAgo(iso) {
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function StatusPill({ status }) {
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

function IncidentCard({ incident, onSelect, isNew }) {
  const barColor = incident.severity === "HIGH" ? palette.high : palette.medium;
  return (
    <button
      onClick={() => onSelect(incident.id)}
      className={`w-full text-left flex gap-3 px-3 py-2.5 border-b hover:bg-white/[0.02] transition-colors ${isNew ? "ibvap-new-row" : ""}`}
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
          <span>track {incident.event.track_id}</span>
          <span>{incident.event.cls}</span>
          <span>{(incident.event.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
      <div className="ibvap-mono text-[11px] shrink-0" style={{ color: palette.textMuted }}>
        {timeAgo(incident.created_at)}
      </div>
    </button>
  );
}

function CameraFeedMockup() {
  return (
    <div className="relative rounded-sm overflow-hidden border" style={{ borderColor: palette.border, backgroundColor: "#0B0F14" }}>
      <svg viewBox="0 0 640 360" className="w-full h-auto block">
        <rect width="640" height="360" fill="#0D1218" />
        <rect y="230" width="640" height="130" fill="#161C24" />
        <rect x="40" y="60" width="160" height="170" fill="#1B222C" />
        <rect x="440" y="90" width="150" height="140" fill="#1B222C" />
        {/* restricted zone overlay */}
        <polygon points="230,150 420,150 420,300 230,300" fill={palette.medium + "12"} stroke={palette.medium} strokeDasharray="6,4" strokeWidth="1.5" />
        <text x="234" y="144" fill={palette.medium} fontSize="12" fontFamily="IBM Plex Mono, monospace">Restricted Path</text>
        {/* person with bbox */}
        <rect x="270" y="190" width="34" height="80" fill="none" stroke={palette.high} strokeWidth="1.5" />
        <text x="270" y="184" fill={palette.high} fontSize="11" fontFamily="IBM Plex Mono, monospace">ID 27 person 0.91</text>
        <circle cx="287" cy="215" r="9" fill="#3A4250" />
        <rect x="278" y="226" width="18" height="40" fill="#3A4250" />
        {/* vehicle with bbox, near checkpoint */}
        <rect x="470" y="170" width="70" height="40" fill="none" stroke={palette.resolved} strokeWidth="1.5" />
        <text x="470" y="164" fill={palette.resolved} fontSize="11" fontFamily="IBM Plex Mono, monospace">ID 4 vehicle 0.85</text>
        <rect x="478" y="180" width="54" height="24" rx="3" fill="#3A4250" />
      </svg>
      <div
        className="ibvap-mono text-[11px] px-3 py-2 border-t flex items-center justify-between"
        style={{ borderColor: palette.border, color: palette.textMuted, backgroundColor: palette.panel }}
      >
        <span>reference mockup — not a live feed</span>
        <span>live overlay stream: not yet implemented (see blueprint §5)</span>
      </div>
    </div>
  );
}

export default function IBVAPCommandCenter() {
  const [incidents, setIncidents] = useState(INITIAL_INCIDENTS);
  const [anprResults] = useState(INITIAL_ANPR);
  const [cameras] = useState(INITIAL_CAMERAS);
  const [selectedCameraId, setSelectedCameraId] = useState("CAM-01");
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [tab, setTab] = useState("incidents");
  const [newId, setNewId] = useState(null);
  const timeoutRef = useRef(null);

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId) || null;

  const updateStatus = useCallback((id, status) => {
    // Mirrors the real backend's PATCH /api/incidents/{id} behavior
    // exactly: resolved_at is only ever set when status is RESOLVED,
    // and moving away from RESOLVED clears it — see blueprint §2.
    setIncidents((prev) =>
      prev.map((inc) =>
        inc.id === id
          ? { ...inc, status, resolved_at: status === "RESOLVED" ? new Date().toISOString() : null }
          : inc
      )
    );
  }, []);

  const simulateIncident = useCallback(() => {
    const id = `inc-${nextId}`;
    const camera = Math.random() > 0.5 ? "CAM-01" : "CAM-02";
    const zone = camera === "CAM-01" ? "Restricted Path" : "ANPR Checkpoint";
    const severity = Math.random() > 0.5 ? "HIGH" : "MEDIUM";
    const confidence = severity === "HIGH" ? 0.75 + Math.random() * 0.2 : 0.4 + Math.random() * 0.25;
    const incident = {
      id, event_id: `evt-${nextId}`, severity, status: "ACTIVE",
      created_at: new Date().toISOString(), resolved_at: null,
      event: {
        id: `evt-${nextId}`, camera_id: camera, zone_id: "z", zone_name: zone,
        track_id: 30 + nextId, type: "INTRUSION", cls: Math.random() > 0.5 ? "person" : "car",
        confidence, timestamp: Date.now() / 1000, evidence_path: null, created_at: new Date().toISOString(),
      },
    };
    nextId += 1;
    setIncidents((prev) => [incident, ...prev]);
    setNewId(id);
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setNewId(null), 500);
  }, []);

  const latestEventForCamera = (camId) => {
    const match = incidents.find((i) => i.event.camera_id === camId);
    return match ? timeAgo(match.created_at) : "no events yet";
  };

  return (
    <div className="ibvap-sans w-full h-full min-h-[720px] flex flex-col" style={{ backgroundColor: palette.bg, color: palette.textPrimary }}>
      <style>{fontStack}</style>

      {/* header */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0" style={{ borderColor: palette.border }}>
        <div className="flex items-center gap-2.5">
          <ShieldAlert size={18} style={{ color: palette.medium }} />
          <span className="text-[14px] font-medium">IBVAP · Command center</span>
          <span className="ibvap-mono text-[11px] px-1.5 py-0.5 rounded-sm border" style={{ color: palette.textMuted, borderColor: palette.border }}>reference build</span>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={simulateIncident}
            className="flex items-center gap-1.5 text-[12px] px-2.5 py-1.5 rounded-sm border hover:bg-white/[0.03] transition-colors"
            style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
          >
            <RotateCcw size={12} /> Simulate incident
          </button>
          <div className="flex items-center gap-1.5 ibvap-mono text-[11px]" style={{ color: palette.live }}>
            <Wifi size={12} />
            connected
          </div>
        </div>
      </div>

      {/* main three-pane layout */}
      <div className="flex flex-1 min-h-0">
        {/* camera grid */}
        <div className="w-[200px] border-r shrink-0 flex flex-col" style={{ borderColor: palette.border }}>
          <div className="px-3 py-2 text-[11px] uppercase tracking-wide" style={{ color: palette.textMuted }}>Cameras</div>
          {cameras.map((cam) => (
            <button
              key={cam.id}
              onClick={() => setSelectedCameraId(cam.id)}
              className="text-left px-3 py-2.5 border-t hover:bg-white/[0.02] transition-colors"
              style={{
                borderColor: palette.border,
                backgroundColor: selectedCameraId === cam.id ? palette.panelAlt : "transparent",
              }}
            >
              <div className="flex items-center gap-2">
                <CameraIcon size={13} style={{ color: palette.textSecondary }} />
                <span className="ibvap-mono text-[13px]">{cam.name || cam.id}</span>
              </div>
              <div className="ibvap-mono text-[10px] mt-1" style={{ color: palette.textMuted }}>
                last event: {latestEventForCamera(cam.id)}
              </div>
            </button>
          ))}
        </div>

        {/* selected camera panel */}
        <div className="flex-1 min-w-0 p-4 overflow-auto">
          <div className="ibvap-mono text-[12px] mb-2" style={{ color: palette.textSecondary }}>{selectedCameraId}</div>
          <CameraFeedMockup />
        </div>

        {/* alert rail */}
        <div className="w-[300px] border-l shrink-0 flex flex-col min-h-0" style={{ borderColor: palette.border }}>
          <div className="px-3 py-2 text-[11px] uppercase tracking-wide shrink-0" style={{ color: palette.textMuted }}>Alert feed</div>
          <div className="flex-1 overflow-auto">
            {incidents.map((inc) => (
              <IncidentCard key={inc.id} incident={inc} onSelect={setSelectedIncidentId} isNew={inc.id === newId} />
            ))}
          </div>
        </div>
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
                {incidents.map((inc) => (
                  <tr key={inc.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: palette.border }}>
                    <td className="px-3 py-1.5">{inc.event.zone_name}</td>
                    <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{inc.event.camera_id}</td>
                    <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{inc.event.track_id}</td>
                    <td className="px-3 py-1.5" style={{ color: inc.severity === "HIGH" ? palette.high : palette.medium }}>{inc.severity}</td>
                    <td className="px-3 py-1.5"><StatusPill status={inc.status} /></td>
                    <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{inc.resolved_at ? new Date(inc.resolved_at).toLocaleTimeString() : "—"}</td>
                    <td className="px-3 py-1.5">
                      <div className="flex gap-1.5">
                        {inc.status !== "ACKNOWLEDGED" && inc.status !== "RESOLVED" && (
                          <button onClick={() => updateStatus(inc.id, "ACKNOWLEDGED")} className="px-2 py-0.5 rounded-sm border hover:bg-white/[0.03]" style={{ borderColor: palette.borderLight, color: palette.textSecondary }}>Acknowledge</button>
                        )}
                        {inc.status !== "RESOLVED" && (
                          <button onClick={() => updateStatus(inc.id, "RESOLVED")} className="px-2 py-0.5 rounded-sm border hover:bg-white/[0.03] flex items-center gap-1" style={{ borderColor: palette.borderLight, color: palette.resolved }}><Check size={11} />Resolve</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="w-full ibvap-mono text-[12px]">
              <thead>
                <tr className="text-left" style={{ color: palette.textMuted }}>
                  <th className="px-3 py-1.5 font-normal">Camera</th>
                  <th className="px-3 py-1.5 font-normal">Track</th>
                  <th className="px-3 py-1.5 font-normal">Plate</th>
                  <th className="px-3 py-1.5 font-normal">Confidence</th>
                  <th className="px-3 py-1.5 font-normal">Plausible</th>
                  <th className="px-3 py-1.5 font-normal">Read at</th>
                </tr>
              </thead>
              <tbody>
                {anprResults.map((r) => (
                  <tr key={r.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: palette.border }}>
                    <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{r.camera_id}</td>
                    <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{r.track_id}</td>
                    <td className="px-3 py-1.5">
                      {r.plate_text ? (
                        <span style={{ color: palette.textPrimary }}>{r.plate_text}</span>
                      ) : (
                        <span className="px-1.5 py-0.5 rounded-sm border border-dashed" style={{ color: palette.textMuted, borderColor: palette.border }}>No plate read</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{(r.confidence * 100).toFixed(0)}%</td>
                    <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{r.plausible ? "yes" : "no"}</td>
                    <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{new Date(r.created_at).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* incident detail overlay */}
      {selectedIncident && (
        <div className="fixed inset-0 flex items-center justify-center z-10" style={{ backgroundColor: "#00000088" }} onClick={() => setSelectedIncidentId(null)}>
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-[420px] rounded-sm border p-4"
            style={{ backgroundColor: palette.panel, borderColor: palette.borderLight }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-[13px] font-medium">Incident detail</span>
              <button onClick={() => setSelectedIncidentId(null)} style={{ color: palette.textMuted }}><X size={16} /></button>
            </div>
            <div className="ibvap-mono text-[12px] space-y-1.5" style={{ color: palette.textSecondary }}>
              <div>id: <span style={{ color: palette.textPrimary }}>{selectedIncident.id}</span></div>
              <div>zone: <span style={{ color: palette.textPrimary }}>{selectedIncident.event.zone_name}</span></div>
              <div>camera: <span style={{ color: palette.textPrimary }}>{selectedIncident.event.camera_id}</span></div>
              <div>track: <span style={{ color: palette.textPrimary }}>{selectedIncident.event.track_id}</span></div>
              <div>class: <span style={{ color: palette.textPrimary }}>{selectedIncident.event.cls}</span></div>
              <div>confidence: <span style={{ color: palette.textPrimary }}>{(selectedIncident.event.confidence * 100).toFixed(0)}%</span></div>
              <div>created: <span style={{ color: palette.textPrimary }}>{new Date(selectedIncident.created_at).toLocaleString()}</span></div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <StatusPill status={selectedIncident.status} />
              {selectedIncident.status !== "ACKNOWLEDGED" && selectedIncident.status !== "RESOLVED" && (
                <button onClick={() => updateStatus(selectedIncident.id, "ACKNOWLEDGED")} className="text-[12px] px-2.5 py-1 rounded-sm border hover:bg-white/[0.03]" style={{ borderColor: palette.borderLight, color: palette.textSecondary }}>Acknowledge</button>
              )}
              {selectedIncident.status !== "RESOLVED" && (
                <button onClick={() => updateStatus(selectedIncident.id, "RESOLVED")} className="text-[12px] px-2.5 py-1 rounded-sm border hover:bg-white/[0.03]" style={{ borderColor: palette.borderLight, color: palette.resolved }}>Resolve</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* footer disclaimer */}
      <div className="ibvap-mono text-[10px] px-4 py-1.5 border-t text-center shrink-0" style={{ borderColor: palette.border, color: palette.textMuted }}>
        reference UI · mock data only · not connected to a live backend · see FRONTEND_BLUEPRINT.md for the real API contract
      </div>
    </div>
  );
}
