// Minimal reconnecting WebSocket wrapper with exponential backoff.
//
// Takes the WebSocket implementation as a parameter (defaults to the
// browser global) specifically so this can be unit-tested in Node
// against a real running backend without a browser — see
// scripts/test-reconnect.mjs, which does exactly that.
//
// Why this exists at all: the backend's WS broadcast has zero message
// history (see FRONTEND_BLUEPRINT.md §3) — a dropped connection means
// silently missed events, not just a UI hiccup. useLiveBackend.js
// treats every reconnect as a cue to re-fetch the REST snapshot for
// exactly that reason; this module's only job is to make "reconnect"
// a reliable, observable event to hook that behavior onto.
export function createReconnectingSocket({
  url,
  onMessage,
  onStatusChange,
  WebSocketImpl = typeof WebSocket !== "undefined" ? WebSocket : undefined,
  minDelayMs = 500,
  maxDelayMs = 8000,
}) {
  if (!WebSocketImpl) {
    throw new Error("No WebSocket implementation available — pass WebSocketImpl explicitly outside a browser.");
  }

  let socket = null;
  let closedByUser = false;
  let attempt = 0;
  let reconnectTimer = null;

  function setStatus(status) {
    onStatusChange?.(status);
  }

  function connect() {
    setStatus(attempt === 0 ? "connecting" : "reconnecting");
    socket = new WebSocketImpl(url);

    socket.onopen = () => {
      const wasReconnect = attempt > 0;
      attempt = 0;
      setStatus(wasReconnect ? "reconnected" : "connected");
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        onMessage?.(msg);
      } catch (e) {
        console.error("Failed to parse WS message:", event.data, e);
      }
    };

    socket.onclose = () => {
      if (closedByUser) {
        setStatus("closed");
        return;
      }
      setStatus("disconnected");
      const delay = Math.min(maxDelayMs, minDelayMs * 2 ** attempt);
      attempt += 1;
      reconnectTimer = setTimeout(connect, delay);
    };

    socket.onerror = () => {
      // onclose fires immediately after onerror on a failed connection —
      // let onclose own reconnect scheduling so it isn't scheduled twice.
    };
  }

  connect();

  return {
    close() {
      closedByUser = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}
