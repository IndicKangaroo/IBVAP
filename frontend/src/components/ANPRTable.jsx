import { palette } from "../lib/palette.js";

export default function ANPRTable({ results }) {
  return (
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
        {results.length === 0 && (
          <tr>
            <td colSpan={6} className="px-3 py-3" style={{ color: palette.textMuted }}>No ANPR results yet.</td>
          </tr>
        )}
        {results.map((r) => (
          <tr key={r.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: palette.border }}>
            <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{r.camera_id}</td>
            <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{r.track_id ?? "—"}</td>
            <td className="px-3 py-1.5">
              {r.plate_text ? (
                <span style={{ color: palette.textPrimary }}>{r.plate_text}</span>
              ) : (
                <span
                  className="px-1.5 py-0.5 rounded-sm border border-dashed"
                  style={{ color: palette.textMuted, borderColor: palette.border }}
                >
                  No plate read
                </span>
              )}
            </td>
            <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{Math.round(r.confidence * 100)}%</td>
            <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{r.plausible ? "yes" : "no"}</td>
            <td className="px-3 py-1.5" style={{ color: palette.textMuted }}>{new Date(r.created_at).toLocaleTimeString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
