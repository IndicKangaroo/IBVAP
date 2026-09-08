import { palette } from "../lib/palette.js";

// Real swatch colors for the dot next to each name — distinct from
// the dashboard's own severity/status palette, since these represent
// actual vehicle paint colors, not UI state.
const COLOR_SWATCHES = {
  white: "#F2F2F2", black: "#1A1A1A", gray: "#8A8A8A",
  red: "#D64545", orange: "#E08A3C", yellow: "#E0C93C",
  green: "#4CAF7D", blue: "#4A7FC9", purple: "#8A5CC9",
};

export default function ANPRTable({ results }) {
  return (
    <table className="w-full ibvap-mono text-[12px]">
      <thead>
        <tr className="text-left" style={{ color: palette.textMuted }}>
          <th className="px-3 py-1.5 font-normal">Camera</th>
          <th className="px-3 py-1.5 font-normal">Track</th>
          <th className="px-3 py-1.5 font-normal">Type</th>
          <th className="px-3 py-1.5 font-normal">Color</th>
          <th className="px-3 py-1.5 font-normal">Plate</th>
          <th className="px-3 py-1.5 font-normal">Confidence</th>
          <th className="px-3 py-1.5 font-normal">Plausible</th>
          <th className="px-3 py-1.5 font-normal">Read at</th>
        </tr>
      </thead>
      <tbody>
        {results.length === 0 && (
          <tr>
            <td colSpan={8} className="px-3 py-3" style={{ color: palette.textMuted }}>No ANPR results yet.</td>
          </tr>
        )}
        {results.map((r) => (
          <tr key={r.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: palette.border }}>
            <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{r.camera_id}</td>
            <td className="px-3 py-1.5" style={{ color: palette.textSecondary }}>{r.track_id ?? "—"}</td>
            <td className="px-3 py-1.5" style={{ color: palette.textPrimary }}>{r.vehicle_type ?? "—"}</td>
            <td className="px-3 py-1.5">
              {r.vehicle_color ? (
                <span className="flex items-center gap-1.5" style={{ color: palette.textPrimary }}>
                  <span
                    className="w-2.5 h-2.5 rounded-full border shrink-0"
                    style={{ backgroundColor: COLOR_SWATCHES[r.vehicle_color] || "#666", borderColor: palette.borderLight }}
                    title={`${Math.round((r.vehicle_color_confidence ?? 0) * 100)}% confidence`}
                  />
                  {r.vehicle_color}
                </span>
              ) : (
                <span style={{ color: palette.textMuted }}>—</span>
              )}
            </td>
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
