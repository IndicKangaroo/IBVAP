// REST client for the IBVAP backend. Deliberately thin — no caching,
// no retry logic here (that lives in useLiveBackend.js, closer to
// where it actually matters for the reconnect story). Every function
// here maps 1:1 to an endpoint documented in FRONTEND_BLUEPRINT.md §2.

export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
export const WS_URL = BACKEND_URL.replace(/^http/, "ws") + "/ws";

async function request(path, options = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${options.method || "GET"} ${path} -> HTTP ${res.status}: ${body}`);
  }
  return res.json();
}

export function getHealth() {
  return request("/health");
}

export function getIncidents({ status, limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("limit", String(limit));
  return request(`/api/incidents?${params}`);
}

export function patchIncidentStatus(id, status) {
  return request(`/api/incidents/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getEvents({ cameraId, limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (cameraId) params.set("camera_id", cameraId);
  params.set("limit", String(limit));
  return request(`/api/events?${params}`);
}

export function getCameras() {
  return request("/api/cameras");
}

export function getANPRResults({ cameraId, limit = 100 } = {}) {
  const params = new URLSearchParams();
  if (cameraId) params.set("camera_id", cameraId);
  params.set("limit", String(limit));
  return request(`/api/anpr?${params}`);
}

// Evidence images are served as static files with paths like
// "data/evidence/<id>.jpg" — the value returned by the API is already
// the correct URL path, just needs the backend origin prepended.
export function evidenceUrl(evidencePath) {
  if (!evidencePath) return null;
  return `${BACKEND_URL}/${evidencePath}`;
}

// --- Camera/pipeline management ("no terminal" layer) ---

export function getSampleVideos() {
  return request("/api/sample-videos");
}

export function previewFrameUrl(source) {
  return `${BACKEND_URL}/api/preview-frame?source=${encodeURIComponent(source)}`;
}

export function createZone({ cameraId, kind, zoneId, name, polygon }) {
  return request("/api/zones", {
    method: "POST",
    body: JSON.stringify({ camera_id: cameraId, kind, zone_id: zoneId, name, polygon }),
  });
}

export function startPipeline({ cameraId, source, zonesPath, anprZonesPath, device = "auto", ocrGpu = "auto" }) {
  return request("/api/pipelines", {
    method: "POST",
    body: JSON.stringify({
      camera_id: cameraId, source,
      zones_path: zonesPath || null, anpr_zones_path: anprZonesPath || null,
      device, ocr_gpu: ocrGpu,
    }),
  });
}

export function getPipelines() {
  return request("/api/pipelines");
}

export function stopPipeline(cameraId) {
  return request(`/api/pipelines/${cameraId}`, { method: "DELETE" });
}

export function getPipelineLog(cameraId, lines = 50) {
  return request(`/api/pipelines/${cameraId}/log?lines=${lines}`);
}
