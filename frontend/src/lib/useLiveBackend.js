import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api.js";
import { createReconnectingSocket } from "./reconnectingSocket.js";

// Central data hook for the whole app: fetches the REST snapshot on
// mount, opens the live WebSocket, and — this is the part that isn't
// optional — re-fetches the REST snapshot on every reconnect, because
// the backend's WS broadcast has no history (FRONTEND_BLUEPRINT.md §3).
// Verified against the real backend in scripts/test-reconnect.mjs
// before this hook was wired up around it.
export function useLiveBackend() {
  const [incidents, setIncidents] = useState([]);
  const [anprResults, setAnprResults] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [loadError, setLoadError] = useState(null);
  const socketRef = useRef(null);

  const refreshSnapshot = useCallback(async () => {
    try {
      const [incidentsRes, anprRes, camerasRes] = await Promise.all([
        api.getIncidents({ limit: 100 }),
        api.getANPRResults({ limit: 100 }),
        api.getCameras(),
      ]);
      setIncidents(incidentsRes);
      setAnprResults(anprRes);
      setCameras(camerasRes);
      setLoadError(null);
    } catch (e) {
      setLoadError(e.message);
    }
  }, []);

  const upsertIncident = useCallback((incident) => {
    setIncidents((prev) => {
      const idx = prev.findIndex((i) => i.id === incident.id);
      if (idx === -1) return [incident, ...prev];
      const next = [...prev];
      next[idx] = incident;
      return next;
    });
  }, []);

  const upsertAnpr = useCallback((result) => {
    setAnprResults((prev) => {
      const idx = prev.findIndex((r) => r.id === result.id);
      if (idx === -1) return [result, ...prev];
      const next = [...prev];
      next[idx] = result;
      return next;
    });
  }, []);

  useEffect(() => {
    refreshSnapshot();

    const conn = createReconnectingSocket({
      url: api.WS_URL,
      onStatusChange: (status) => {
        setConnectionStatus(status);
        if (status === "reconnected") {
          // We may have missed messages while disconnected — the
          // socket reconnecting says nothing about what happened
          // during the gap, so re-sync from the source of truth.
          refreshSnapshot();
        }
      },
      onMessage: (msg) => {
        if (msg.type === "incident_created" || msg.type === "incident_updated") {
          upsertIncident(msg.data);
        } else if (msg.type === "anpr_result") {
          upsertAnpr(msg.data);
        }
      },
    });
    socketRef.current = conn;

    return () => conn.close();
  }, [refreshSnapshot, upsertIncident, upsertAnpr]);

  const updateIncidentStatus = useCallback(async (id, status) => {
    // Optimistic update, reconciled with the server's response —
    // matches the real PATCH semantics exactly (including that
    // resolved_at is cleared when status moves away from RESOLVED),
    // since we apply the server's returned object, not a guessed one.
    const prev = incidents.find((i) => i.id === id);
    if (prev) {
      upsertIncident({ ...prev, status, resolved_at: status === "RESOLVED" ? new Date().toISOString() : null });
    }
    try {
      const updated = await api.patchIncidentStatus(id, status);
      upsertIncident(updated);
    } catch (e) {
      // Roll back on failure rather than leaving an unconfirmed optimistic state
      if (prev) upsertIncident(prev);
      throw e;
    }
  }, [incidents, upsertIncident]);

  return {
    incidents,
    anprResults,
    cameras,
    connectionStatus,
    loadError,
    updateIncidentStatus,
    refreshSnapshot,
  };
}
