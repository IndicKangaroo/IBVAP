import { useEffect, useRef, useState } from "react";
import { palette } from "../lib/palette.js";
import { previewFrameUrl } from "../lib/api.js";

const FETCH_TIMEOUT_MS = 8000;

// Click-to-add-points polygon editor over a real preview frame fetched
// from the backend (GET /api/preview-frame). This is the direct
// replacement for scripts/draw_zone.py's OpenCV desktop window — same
// underlying idea (click points, save a polygon), but reachable from
// a browser instead of a local GUI window.
//
// Loads the preview via fetch() + AbortController rather than a plain
// <img src>, specifically so there's a hard client-side timeout
// independent of the server. A bare <img> tag has no timeout of its
// own — if a request hangs anywhere between the browser and the
// backend (network, the backend process, OpenCV, wherever), a plain
// <img> just sits in "loading" forever with zero feedback, even if
// the server itself has its own timeout, because a hang before the
// server responds means the server's timeout never even matters.
export default function ZoneCanvasEditor({ source, onPolygonChange }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const [points, setPoints] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | loading | loaded | error | timeout
  const [errorDetail, setErrorDetail] = useState(null);
  const blobUrlRef = useRef(null);

  useEffect(() => {
    onPolygonChange?.(points);
  }, [points, onPolygonChange]);

  useEffect(() => {
    setPoints([]);
    if (!source) {
      setStatus("idle");
      return;
    }

    setStatus("loading");
    setErrorDetail(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    fetch(previewFrameUrl(source), { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new Error(`Server returned ${res.status}${body ? `: ${body}` : ""}`);
        }
        return res.blob();
      })
      .then((blob) => {
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        const url = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        const img = new Image();
        img.onload = () => {
          imgRef.current = img;
          // canvas is now ALWAYS mounted (see render below) — just
          // hidden via CSS until status flips to "loaded" — so this
          // ref is guaranteed non-null here. The previous version
          // conditionally mounted the canvas based on the very status
          // this handler was about to set, meaning the ref was still
          // null at exactly this moment: canvas.width would throw,
          // and setStatus("loaded") — right after it — would never
          // run. That was the actual bug behind "stuck on loading
          // preview": the image genuinely loaded, the component just
          // never found out.
          const canvas = canvasRef.current;
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          setStatus("loaded");
        };
        img.onerror = () => {
          setStatus("error");
          setErrorDetail("Downloaded a response but it wasn't a valid image.");
        };
        img.src = url;
      })
      .catch((e) => {
        if (e.name === "AbortError") {
          setStatus("timeout");
          setErrorDetail(
            `No response after ${FETCH_TIMEOUT_MS / 1000}s. If this also hangs when you open ` +
            `the preview-frame URL directly in a browser tab, it's a backend/OpenCV issue, not this UI. ` +
            `If pasting that URL directly loads fine, this is worth reporting as a frontend bug.`
          );
        } else {
          setStatus("error");
          setErrorDetail(e.message);
        }
      })
      .finally(() => clearTimeout(timeoutId));

    return () => {
      controller.abort();
      clearTimeout(timeoutId);
    };
  }, [source]);

  const draw = () => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || status !== "loaded") return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    if (points.length === 0) return;
    ctx.strokeStyle = palette.medium;
    ctx.fillStyle = palette.medium;
    ctx.lineWidth = 2;

    ctx.beginPath();
    points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    if (points.length >= 3) ctx.closePath();
    ctx.stroke();

    points.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  };

  useEffect(draw, [points, status]);

  const handleClick = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);
    setPoints((prev) => [...prev, [x, y]]);
  };

  if (!source) {
    return (
      <div className="ibvap-mono text-[12px] p-4" style={{ color: palette.textMuted }}>
        Pick a source first.
      </div>
    );
  }

  return (
    <div>
      <div className="relative border rounded-sm overflow-hidden" style={{ borderColor: palette.border }}>
        {status === "loading" && (
          <div className="ibvap-mono text-[12px] p-6 text-center" style={{ color: palette.textMuted }}>
            Loading preview… (times out at {FETCH_TIMEOUT_MS / 1000}s if the source can't be opened)
          </div>
        )}
        {(status === "error" || status === "timeout") && (
          <div className="ibvap-mono text-[12px] p-6" style={{ color: palette.high }}>
            <div className="font-medium mb-1">{status === "timeout" ? "Timed out" : "Failed to load preview"}</div>
            <div style={{ color: palette.textSecondary }}>{errorDetail}</div>
          </div>
        )}
        {/* Always mounted (never conditionally rendered on `status`) —
            just hidden via CSS until loaded. This is the actual fix:
            the ref must exist BEFORE the image's onload handler runs,
            not after, or setting canvas.width there hits a null ref.
            See the onload handler above for the full story. */}
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          className="w-full h-auto block cursor-crosshair"
          style={{ display: status === "loaded" ? "block" : "none" }}
        />
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="ibvap-mono text-[11px]" style={{ color: palette.textMuted }}>
          {points.length} point{points.length === 1 ? "" : "s"} · click to add, need at least 3
        </span>
        <div className="flex gap-1.5">
          <button
            onClick={() => setPoints((p) => p.slice(0, -1))}
            disabled={points.length === 0}
            className="text-[11px] px-2 py-1 rounded-sm border disabled:opacity-40"
            style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
          >
            Undo
          </button>
          <button
            onClick={() => setPoints([])}
            disabled={points.length === 0}
            className="text-[11px] px-2 py-1 rounded-sm border disabled:opacity-40"
            style={{ borderColor: palette.borderLight, color: palette.textSecondary }}
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
