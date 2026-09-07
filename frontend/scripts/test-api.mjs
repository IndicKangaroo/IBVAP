// Loads src/lib/api.js through Vite's own module transform (so
// import.meta.env resolves exactly as it would in the browser) and
// fires real requests at a live backend. Run with the backend up:
//   node scripts/test-api.mjs
import { createServer } from "vite";

const server = await createServer({
  configFile: new URL("../vite.config.js", import.meta.url).pathname,
  server: { middlewareMode: true },
  appType: "custom",
});

const api = await server.ssrLoadModule("/src/lib/api.js");

function assert(cond, msg) {
  if (!cond) throw new Error("ASSERTION FAILED: " + msg);
  console.log("PASS:", msg);
}

try {
  console.log("BACKEND_URL:", api.BACKEND_URL);
  console.log("WS_URL:", api.WS_URL);

  const health = await api.getHealth();
  assert(health.status === "ok", "getHealth() returns status ok");

  const cameras = await api.getCameras();
  assert(Array.isArray(cameras), "getCameras() returns an array");
  console.log("  cameras:", cameras.map((c) => c.id));

  const incidents = await api.getIncidents({ limit: 5 });
  assert(Array.isArray(incidents), "getIncidents() returns an array");
  console.log("  incidents fetched:", incidents.length);

  const anpr = await api.getANPRResults({ limit: 5 });
  assert(Array.isArray(anpr), "getANPRResults() returns an array");
  console.log("  anpr results fetched:", anpr.length);

  assert(api.evidenceUrl(null) === null, "evidenceUrl(null) returns null");
  assert(
    api.evidenceUrl("data/evidence/x.jpg") === `${api.BACKEND_URL}/data/evidence/x.jpg`,
    "evidenceUrl() builds the correct URL"
  );

  // patchIncidentStatus against a real incident, if one exists
  if (incidents.length > 0) {
    const target = incidents[0];
    const newStatus = target.status === "ACTIVE" ? "ACKNOWLEDGED" : "ACTIVE";
    const updated = await api.patchIncidentStatus(target.id, newStatus);
    assert(updated.status === newStatus, `patchIncidentStatus() actually changed status to ${newStatus}`);
    assert(updated.id === target.id, "patchIncidentStatus() returns the same incident id");
  } else {
    console.log("  (no incidents in DB yet — skipping patchIncidentStatus test)");
  }

  console.log("\nALL API TESTS PASSED");
} catch (e) {
  console.error("\nTEST FAILED:", e.message);
  process.exitCode = 1;
} finally {
  await server.close();
}
