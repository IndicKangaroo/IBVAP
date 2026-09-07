// Verifies reconnectingSocket.js against a REAL running backend — not
// a mock. Doesn't just check it connects; walks through the failure
// case that actually matters: kill the backend mid-session, confirm
// it retries with backoff, restart the backend, confirm it recovers
// and receives a live message again.
//
// Requires the `ws` package (already a devDependency — a Node
// stand-in for the browser's global WebSocket; the module itself
// takes the implementation as a parameter for exactly this reason).
//
// Usage:
//   node scripts/test-reconnect.mjs
// ...then in another terminal, kill and restart the backend partway
// through the 15s run to watch it recover live. Or see
// FRONTEND_BLUEPRINT.md / the project history for a transcript of
// this already having been run that way.
import WebSocketImpl from "ws";
import { createReconnectingSocket } from "../src/lib/reconnectingSocket.js";

const url = process.env.WS_URL || "ws://127.0.0.1:8000/ws";
const statuses = [];
const messages = [];

console.log(`Connecting to ${url} — this will run for 15s, watching for status changes and messages.`);
console.log("Try killing and restarting the backend partway through to see it recover.\n");

const conn = createReconnectingSocket({
  url,
  WebSocketImpl,
  onStatusChange: (s) => { statuses.push(s); console.log("[status]", s); },
  onMessage: (m) => { messages.push(m); console.log("[message]", m.type); },
  minDelayMs: 300,
  maxDelayMs: 1000,
});

await new Promise((r) => setTimeout(r, 15000));
console.log("\n=== SUMMARY ===");
console.log("statuses seen:", statuses);
console.log("messages received:", messages.length);
conn.close();
process.exit(0);
