// Thin client for the FireSight API. Every value shown in the UI comes from these endpoints.

export type Json = any;

const cache = new Map<string, Promise<Json>>();

export async function get(path: string, params: Record<string, any> = {}, useCache = true): Promise<Json> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  const url = `/api/${path}${qs.toString() ? "?" + qs : ""}`;
  if (useCache && cache.has(url)) return cache.get(url)!;
  const p = fetch(url).then(async (r) => {
    if (!r.ok) {
      let msg = `${r.status}`;
      try {
        msg = (await r.json()).detail || msg;
      } catch {
        /* ignore */
      }
      cache.delete(url);
      throw new Error(msg);
    }
    return r.json();
  });
  if (useCache) cache.set(url, p);
  return p;
}

export async function post(path: string, body: Json): Promise<Json> {
  const r = await fetch(`/api/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.detail || r.status);
  return j;
}

export function exportUrl(params: Record<string, any>) {
  const qs = new URLSearchParams(params as any).toString();
  return `/api/export.csv?${qs}`;
}

export const PLATFORMS = ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"] as const;
export type Platform = (typeof PLATFORMS)[number];

export const PLATFORM_LABEL: Record<string, string> = {
  Terra: "MODIS Terra",
  Aqua: "MODIS Aqua",
  SNPP: "VIIRS S-NPP",
  NOAA20: "VIIRS NOAA-20",
  NOAA21: "VIIRS NOAA-21",
  MODIS: "MODIS (Terra+Aqua)",
  ALL: "Naive union (all platforms)",
};

export const PLATFORM_COLOR: Record<string, string> = {
  Terra: "#e8894a",
  Aqua: "#5bb8e6",
  SNPP: "#b896f2",
  NOAA20: "#4fcfa8",
  NOAA21: "#f2cf5b",
  MODIS: "#e8894a",
  ALL: "#ef6461",
};

export const METHOD_LABEL: Record<string, string> = {
  no_source: "No platform delivering data",
  reference_observed: "Observed (VIIRS S-NPP reference)",
  calibrated_terra: "Reconstructed from MODIS Terra",
  calibrated_modis: "Reconstructed from MODIS Terra+Aqua",
  calibrated_noaa21: "Calibrated VIIRS NOAA-21",
  calibrated_noaa20: "Calibrated VIIRS NOAA-20",
};

export const ANOMALY_LABEL: Record<string, string> = {
  insufficient_baseline: "Insufficient baseline",
  normal: "Normal",
  unusually_low: "Unusually low",
  elevated: "Elevated",
  highly_unusual: "Highly unusual",
};

export const RATING_LABEL: Record<string, string> = {
  high: "High",
  moderate: "Moderate",
  low: "Low",
  very_low: "Very low",
  insufficient: "Insufficient data",
};

export function fmt(v: number | null | undefined, nd = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: nd, minimumFractionDigits: nd });
}

export function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function dayOfYear(iso: string): number {
  const d = new Date(iso + "T00:00:00Z");
  const start = Date.UTC(d.getUTCFullYear(), 0, 1);
  return Math.floor((d.getTime() - start) / 86400000) + 1;
}

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function niceDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}
