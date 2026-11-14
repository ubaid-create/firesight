// Sequential palettes for the activity index (low -> high).
export const PALETTES: Record<string, { label: string; stops: string[] }> = {
  viridis: {
    label: "Viridis",
    stops: ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
  },
  cividis: {
    label: "Cividis (colour-vision safe)",
    stops: ["#00224e", "#123570", "#3b496c", "#575d6d", "#707173", "#8a8779", "#a69d75", "#c4b56c", "#e4cf5b", "#fee838"],
  },
  ylorrd: {
    label: "YlOrRd (traditional fire)",
    stops: ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#bd0026", "#800026", "#4d0019"],
  },
};

export function colorAt(palette: string, t: number): string {
  const s = PALETTES[palette].stops;
  const x = Math.max(0, Math.min(1, t)) * (s.length - 1);
  const i = Math.floor(x);
  const f = x - i;
  if (i >= s.length - 1) return s[s.length - 1];
  const a = hex(s[i]);
  const b = hex(s[i + 1]);
  const c = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function hex(h: string): number[] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// MapLibre interpolate expression over 0..100
export function mapRamp(palette: string, prop: any[]): any[] {
  const s = PALETTES[palette].stops;
  const expr: any[] = ["interpolate", ["linear"], prop];
  s.forEach((c, i) => expr.push((100 * i) / (s.length - 1), c));
  return expr;
}
