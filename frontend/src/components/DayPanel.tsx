import { useEffect, useState } from "react";
import { ANOMALY_LABEL, METHOD_LABEL, PLATFORM_COLOR, PLATFORM_LABEL, addDays, exportUrl, fmt, get, niceDate } from "../api";
import { colorAt } from "../palettes";

type Props = { aoi: string; date: string | null; palette: string; range: [string, string]; harmonized: boolean };

function anomalyClass(a: string) {
  return a === "highly_unusual" ? "bad" : a === "elevated" ? "warn" : a === "unusually_low" ? "info" : "";
}

export default function DayPanel({ aoi, date, palette, range, harmonized }: Props) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!date || !harmonized) return;
    setD(null);
    setErr(null);
    get("day", { aoi, date }).then(setD).catch((e) => setErr(e.message));
  }, [aoi, date, harmonized]);

  if (!harmonized) return <div className="card day"><h3>Day detail</h3><div className="notice info" style={{ marginTop: 8 }}>No processed historical record for this area.</div></div>;
  if (!date) return <div className="card day"><h3>Day detail</h3><div className="muted">Select a day on the calendar.</div></div>;
  if (err) return <div className="card day"><div className="notice bad">{err}</div></div>;
  if (!d) return <div className="card day"><div className="skeleton" style={{ height: 420 }} /></div>;

  const h = d.harmonized;
  const maxCells = Math.max(1, ...d.platforms.map((p: any) => p.cells));
  const reconstructed = h.method.startsWith("calibrated");
  return (
    <div className="card day">
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".07em" }}>Selected day</div>
      <h2>{niceDate(d.date)}</h2>
      <div className="sub">8-day window {niceDate(addDays(d.date, -7))} – {niceDate(d.date)}</div>

      <div className="row" style={{ alignItems: "flex-end", gap: 14 }}>
        <div>
          <div className="big" style={{ color: h.index ? colorAt(palette, h.index / 100) : undefined }}>{h.index ?? "—"}</div>
          <div className="muted" style={{ fontSize: 11.5 }}>activity index / 100</div>
        </div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }} className="num">{fmt(h.h_roll, 1)}</div>
          <div className="muted" style={{ fontSize: 11.5 }}>cells/day, S-NPP scale{h.lo !== h.hi ? ` · 80% ${fmt(h.lo, 1)}–${fmt(h.hi, 1)}` : ""}</div>
        </div>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <span className={`pill ${reconstructed ? "accent" : "good"}`}>{METHOD_LABEL[h.method] || h.method}</span>
        <span className={`pill ${anomalyClass(d.anomaly.label)}`}>{ANOMALY_LABEL[d.anomaly.label]}{d.anomaly.z !== null ? ` · z ${fmt(d.anomaly.z, 1)}` : ""}</span>
        {h.provisional && <span className="pill warn">Provisional (NRT)</span>}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Seasonal baseline (same dates ±7 days, {d.anomaly.base_years} other years): median {fmt(d.anomaly.base_median, 1)} cells/day
        {d.anomaly.method === "rank_fallback" ? " · scored by rank (baseline MAD is zero)" : ""}
        {d.anomaly.method === "below_min_activity" ? " · too little activity to flag" : ""}
      </div>

      <div className="title muted" style={{ marginTop: 14, fontSize: 11, textTransform: "uppercase", letterSpacing: ".07em" }}>Observed on this day, by platform</div>
      <table className="t" style={{ marginTop: 4 }}>
        <thead><tr><th>Platform</th><th className="r">Cells</th><th className="r">Det.</th><th className="r">FRP max</th><th className="r">D/N</th></tr></thead>
        <tbody>
          {d.platforms.map((p: any) => {
            const on = d.delivering.includes(p.platform);
            const miss = d.missing_today.some((m: any) => m.platform === p.platform);
            return (
              <tr key={p.platform} style={{ opacity: on ? 1 : 0.45 }}>
                <td><span className="dot" style={{ background: PLATFORM_COLOR[p.platform] }} /> {PLATFORM_LABEL[p.platform]}
                  {!on && <span className="faint"> · not operating</span>}{miss && <span className="error"> · FIRMS missing data</span>}
                  <div className="bar" style={{ marginTop: 3 }}><span style={{ width: `${(100 * p.cells) / maxCells}%`, background: PLATFORM_COLOR[p.platform] }} /></div>
                </td>
                <td className="r">{on ? p.cells : "—"}</td>
                <td className="r">{on ? p.n_det : "—"}</td>
                <td className="r">{p.frp_max === null ? "—" : fmt(p.frp_max, 0)}</td>
                <td className="r">{on ? `${p.n_day}/${p.n_night}` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="faint" style={{ fontSize: 11.5, marginTop: 6 }}>
        Cells = unique active 1 km grid cells (vegetation-fire or unclassified, nominal/high confidence). Platforms see different
        times of day and pixel sizes, so these raw counts are not comparable with each other.
      </div>
      {h.naive_roll !== null && (
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Naive union of all platforms: {fmt(h.naive_roll, 1)} cells/day — shown for contrast; it inflates with every added satellite.
        </div>
      )}
      <div className="row" style={{ marginTop: 12 }}>
        <a className="btn small" href={exportUrl({ aoi, kind: "harmonized" })}>Export harmonized CSV</a>
        <a className="btn small" href={exportUrl({ aoi, kind: "detections", start: range[0], end: range[1] })}>Export map detections</a>
      </div>
    </div>
  );
}
