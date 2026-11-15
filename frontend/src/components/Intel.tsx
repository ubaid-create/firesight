import { useEffect, useMemo, useState } from "react";
import EChart, { AXIS, TOOLTIP } from "./EChart";
import { MONTHS, PLATFORM_LABEL, fmt, get, niceDate } from "../api";

export function Anomalies({ aoi, onPickDate }: { aoi: string; onPickDate: (d: string) => void }) {
  const [a, setA] = useState<any>(null);
  useEffect(() => {
    setA(null);
    get("anomalies", { aoi, top: 30 }).then(setA).catch(() => setA({ episodes: [], episodes_total: 0 }));
  }, [aoi]);
  return (
    <div className="card">
      <h3>Most unusual episodes</h3>
      <div className="sub">
        Runs of days whose 8-day harmonized activity was far above the same dates in other years
        (robust z ≥ 2 elevated, ≥ 3.5 highly unusual). {a ? `${a.episodes_total} episodes in total; largest excess first.` : ""}
      </div>
      {!a && <div className="skeleton" style={{ height: 300 }} />}
      {a && (
        <div className="scroll">
          <table className="t">
            <thead><tr><th>Period</th><th>Level</th><th className="r">Peak</th><th className="r">Usual</th><th className="r">z</th><th>Source</th></tr></thead>
            <tbody>
              {a.episodes.map((e: any) => (
                <tr key={e.start} className="click" onClick={() => onPickDate(e.peak_date)} title="Show on calendar and map">
                  <td>{niceDate(e.start)}{e.days > 1 ? ` – ${niceDate(e.end)}` : ""}<div className="faint" style={{ fontSize: 11 }}>{e.days} days · peak {niceDate(e.peak_date)}</div></td>
                  <td><span className={`pill ${e.label === "highly_unusual" ? "bad" : "warn"}`}>{e.label === "highly_unusual" ? "Highly unusual" : "Elevated"}</span></td>
                  <td className="r">{fmt(e.peak, 1)}<div className="faint" style={{ fontSize: 10.5 }}>{fmt(e.peak_lo, 0)}–{fmt(e.peak_hi, 0)}</div></td>
                  <td className="r">{fmt(e.base_median, 1)}</td>
                  <td className="r">{e.z_max === null ? "rank" : fmt(e.z_max, 1)}</td>
                  <td><span className="pill">{e.reconstructed ? "reconstructed" : "observed"}</span>
                    {e.provisional && <span className="pill warn" style={{ marginLeft: 3 }}>NRT</span>}</td>
                </tr>
              ))}
              {a.episodes.length === 0 && <tr><td colSpan={6} className="muted">No flagged episodes.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <div className="faint" style={{ fontSize: 11.5, marginTop: 6 }}>An anomaly is unusual observed activity, not a confirmed wildfire. Values are cells/day on the S-NPP scale.</div>
    </div>
  );
}

export function Windows({ aoi, palette: _p }: { aoi: string; palette: string }) {
  const [w, setW] = useState<any>(null);
  useEffect(() => {
    setW(null);
    get("windows", { aoi }).then(setW).catch(() => setW({ windows: [], weekly: [] }));
  }, [aoi]);
  const option = useMemo(() => {
    if (!w || !w.weekly?.length) return null;
    const lab = w.weekly.map((r: any) => {
      const d = new Date(Date.UTC(2001, 0, 1 + (r.week - 1) * 7));
      return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
    });
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", formatter: (ps: any[]) => {
        const r = w.weekly[ps[0].dataIndex];
        return `<b>Week of ${lab[ps[0].dataIndex]}</b><br/>Elevated in ${r.years_elevated} of ${r.years} years (${fmt(100 * r.share_elevated, 0)}%)<br/>Median weekly total ${fmt(r.median, 0)} cell-days`;
      } },
      grid: { left: 46, right: 12, top: 16, bottom: 30 },
      xAxis: { type: "category", data: lab, ...AXIS, axisLabel: { ...AXIS.axisLabel, interval: 7 } },
      yAxis: { type: "value", max: 100, name: "% of years elevated", ...AXIS },
      series: [{
        type: "bar", data: w.weekly.map((r: any) => ({ value: Math.round(100 * r.share_elevated), itemStyle: { color: r.critical ? "#f0a03c" : "#3a4a5c" } })),
        barCategoryGap: "15%",
        markLine: { symbol: "none", silent: true, lineStyle: { color: "#ef6461", type: "dashed" }, data: [{ yAxis: 50, label: { formatter: "critical ≥ 50%", color: "#ef6461", fontSize: 10.5 } }] },
      }],
    };
  }, [w]);
  return (
    <div className="card">
      <h3>Critical burning windows</h3>
      <div className="sub">Weeks of the year that were elevated (above this area's 75th-percentile week) in at least half of the years with complete data.</div>
      {!w && <div className="skeleton" style={{ height: 240 }} />}
      {w && option && <EChart option={option} height={230} />}
      {w && !option && <div className="muted">Not enough history to identify recurring windows for this area.</div>}
      {w && w.windows?.length > 0 && (
        <table className="t" style={{ marginTop: 6 }}>
          <thead><tr><th>Historical window</th><th className="r">Years elevated</th><th className="r">Mean share</th></tr></thead>
          <tbody>
            {w.windows.map((x: any) => (
              <tr key={x.start_week}>
                <td>{x.start_label} – {x.end_label}</td>
                <td className="r">{x.min_years_elevated === x.max_years_elevated ? x.min_years_elevated : `${x.min_years_elevated}–${x.max_years_elevated}`} of {x.years_used}</td>
                <td className="r">{fmt(100 * x.mean_share_elevated, 0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="faint" style={{ fontSize: 11.5, marginTop: 6 }}>Historical recurrence, not a forecast of future fires.</div>
    </div>
  );
}

export function CompareHistory({ aoi }: { aoi: string }) {
  const [c, setC] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setC(null);
    setErr(null);
    get("compare", { aoi, days: 14 }).then(setC).catch((e) => setErr(e.message));
  }, [aoi]);
  const option = useMemo(() => {
    if (!c) return null;
    const years = [...c.history.map((h: any) => String(h.year)), String(c.end.slice(0, 4))];
    const vals = [...c.history.map((h: any) => ({ value: h.mean, itemStyle: { color: h.method === "reference_observed" ? "#7d6aa8" : "#8a6440" } })),
      { value: c.current, itemStyle: { color: "#f0a03c" } }];
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v: number) => fmt(v, 1) },
      grid: { left: 46, right: 12, top: 20, bottom: 26 },
      xAxis: { type: "category", data: years, ...AXIS, axisLabel: { ...AXIS.axisLabel, interval: 3 } },
      yAxis: { type: "value", name: "cells / day", ...AXIS },
      series: [{ type: "bar", data: vals, barCategoryGap: "20%",
        markLine: { symbol: "none", silent: true, lineStyle: { color: "#e4eaf1", type: "dashed" }, data: [{ yAxis: c.historical_median, label: { formatter: "median", color: "#e4eaf1", fontSize: 10.5 } }] } }],
    };
  }, [c]);
  return (
    <div className="card">
      <h3>Latest 14 days against the same dates in every year</h3>
      {c && <div className="sub">{niceDate(c.start)} – {niceDate(c.end)} in each year. Purple: observed S-NPP years; brown: reconstructed MODIS years; amber: now
        {c.provisional_days > 0 ? " (provisional, near-real-time)" : ""}.</div>}
      {err && <div className="notice">{err}</div>}
      {!c && !err && <div className="skeleton" style={{ height: 230 }} />}
      {option && <EChart option={option} height={230} />}
      {c && (
        <div className="faint" style={{ fontSize: 11.5, marginTop: 4 }}>
          Raw now: {Object.entries(c.raw_current_by_platform).filter(([, v]) => v !== null).map(([k, v]) => `${PLATFORM_LABEL[k]} ${fmt(v as number, 1)}`).join(" · ")} cells/day.
        </div>
      )}
    </div>
  );
}
