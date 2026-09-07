// Same palette as CommandCenterReference.jsx, factored out so the
// real app and the reference build can't visually drift apart. See
// that file's header comment for the design reasoning.
export const palette = {
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

export function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}
