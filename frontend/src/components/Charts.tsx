import { useEffect, useMemo, useState } from "react";
import EChart, { AXIS, LEGEND, TOOLTIP } from "./EChart";
import { MONTHS, PLATFORM_COLOR, PLATFORM_LABEL, fmt, get } from "../api";

const TRANSITIONS = [
  { date: "2002-07-06", label: "Aqua" },
  { date: "2012-01-20", label: "S-NPP" },
  { date: "2018-04-01", label: "NOAA-20" },
  { date: "2023-03-01", label: "NOAA-21" },
  { date: "2026-11-02", label: "S-NPP ends" },
];

function markLines(freq: string, periods: string[]) {
  const key = (d: string) => (freq === "year" ? d.slice(0, 4) : freq === "month" ? d.slice(0, 7) : d);
  const data = TRANSITIONS.map((t) => {
    const k = key(t.date);
    const hit = periods.find((p) => key(p) >= k);
    return hit ? { xAxis: hit, label: { formatter: t.label, color: "#aab6c5", fontSize: 10.5 } } : null;
  }).filter(Boolean);
  return { symbol: "none", silent: true, lineStyle: { color: "#4b5a6c", type: "dashed" }, data };
}

type Props = { aoi: string; onPickDate: (d: string) => void };

export function BeforeAfter({ aoi, onPickDate }: Props) {
  const [freq, setFreq] = useState<"year" | "month" | "8d">("year");
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    setS(null);
    get("series", { aoi, freq }).then(setS).catch(() => setS(null));
  }, [aoi, freq]);
  const option = useMemo(() => {
    if (!s) return null;
    const x = s.period;
    const band = s.harmonized_hi.map((h: number | null, i: number) => (h === null || s.harmonized_lo[i] === null ? null : h - s.harmonized_lo[i]));
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v: number) => (v === null || v === undefined ? "—" : fmt(v, 1)) },
      legend: { ...LEGEND, data: ["Naive union", "Raw MODIS", "Raw VIIRS S-NPP", "Harmonized (S-NPP scale)", "80% interval"] },
      grid: { left: 50, right: 16, top: 34, bottom: 30 },
      xAxis: { type: "category", data: x, ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: (v: string) => (freq === "year" ? v.slice(0, 4) : v.slice(0, 7)) } },
      yAxis: { type: "value", name: "active cells / day", ...AXIS },
      dataZoom: freq === "year" ? [] : [{ type: "inside" }, { type: "slider", height: 14, bottom: 4, borderColor: "#2d3a4a", textStyle: { color: "#8d9bad" } }],
      series: [
        { name: "80% interval", type: "line", data: s.harmonized_lo, stack: "band", symbol: "none", lineStyle: { opacity: 0 }, silent: true, tooltip: { show: false } },
        { name: "80% interval", type: "line", data: band, stack: "band", symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: "rgba(228,234,241,0.12)" }, silent: true, tooltip: { show: false } },
        { name: "Naive union", type: "line", data: s.observed.ALL, symbol: "none", lineStyle: { color: PLATFORM_COLOR.ALL, width: 1.5, type: "dashed" }, itemStyle: { color: PLATFORM_COLOR.ALL } },
        { name: "Raw MODIS", type: "line", data: s.observed.MODIS, symbol: "none", lineStyle: { color: PLATFORM_COLOR.MODIS, width: 1.5 }, itemStyle: { color: PLATFORM_COLOR.MODIS } },
        { name: "Raw VIIRS S-NPP", type: "line", data: s.observed.SNPP, symbol: "none", lineStyle: { color: PLATFORM_COLOR.SNPP, width: 1.5 }, itemStyle: { color: PLATFORM_COLOR.SNPP } },
        { name: "Harmonized (S-NPP scale)", type: "line", data: s.harmonized, symbol: freq === "year" ? "circle" : "none", symbolSize: 4,
          lineStyle: { color: "#e4eaf1", width: 2.2 }, itemStyle: { color: "#e4eaf1" }, markLine: markLines(freq, x) },
      ],
    };
  }, [s, freq]);
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>Before and after harmonization</h3>
          <div className="sub">The naive union jumps each time a satellite is added. The harmonized record stays on one scale (VIIRS S-NPP). Values before 2012 are reconstructed from MODIS.</div>
        </div>
        <div className="seg">
          {(["year", "month", "8d"] as const).map((f) => (
            <button key={f} className={freq === f ? "on" : ""} onClick={() => setFreq(f)}>{f === "8d" ? "8-day" : f}</button>
          ))}
        </div>
      </div>
      {option ? <EChart option={option} height={320} onClick={(p) => p.name && onPickDate(p.name.length === 4 ? `${p.name}-06-30` : p.name)} /> : <div className="skeleton" style={{ height: 320 }} />}
    </div>
  );
}

export function PlatformSeries({ aoi }: { aoi: string }) {
  const [freq, setFreq] = useState<"month" | "8d" | "year">("month");
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    setS(null);
    get("series", { aoi, freq }).then(setS).catch(() => setS(null));
  }, [aoi, freq]);
  const option = useMemo(() => {
    if (!s) return null;
    const plats = ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"];
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v: number) => (v === null || v === undefined ? "—" : fmt(v, 1)) },
      legend: { ...LEGEND, data: plats.map((p) => PLATFORM_LABEL[p]) },
      grid: { left: 50, right: 16, top: 62, bottom: 34 },
      xAxis: { type: "category", data: s.period, ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: (v: string) => (freq === "year" ? v.slice(0, 4) : v.slice(0, 7)) } },
      yAxis: { type: "value", name: "observed cells / day", ...AXIS },
      dataZoom: [{ type: "inside", start: freq === "year" ? 0 : 55 }, { type: "slider", height: 14, bottom: 4, start: freq === "year" ? 0 : 55, borderColor: "#2d3a4a", textStyle: { color: "#8d9bad" } }],
      series: plats.map((p) => ({ name: PLATFORM_LABEL[p], type: "line", data: s.observed[p], symbol: "none", connectNulls: false,
        lineStyle: { color: PLATFORM_COLOR[p], width: 1.4 }, itemStyle: { color: PLATFORM_COLOR[p] } })),
    };
  }, [s, freq]);
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>Each platform's own observations</h3>
          <div className="sub">Raw active 1 km cells per day. VIIRS (375 m) records about 4× more cells than MODIS (1 km); the three VIIRS satellites agree closely.</div>
        </div>
        <div className="seg">
          {(["year", "month", "8d"] as const).map((f) => (
            <button key={f} className={freq === f ? "on" : ""} onClick={() => setFreq(f)}>{f === "8d" ? "8-day" : f}</button>
          ))}
        </div>
      </div>
      {option ? <EChart option={option} height={300} /> : <div className="skeleton" style={{ height: 300 }} />}
    </div>
  );
}

export function CalibrationCheck({ aoi }: { aoi: string }) {
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    setS(null);
    get("series", { aoi, freq: "month", start: "2012-02-01" }).then(setS).catch(() => setS(null));
  }, [aoi]);
  const option = useMemo(() => {
    if (!s) return null;
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v: number) => (v === null || v === undefined ? "—" : fmt(v, 1)) },
      legend: { ...LEGEND, data: ["Observed VIIRS S-NPP (reference)", "Calibrated MODIS", "Calibrated NOAA-20", "Calibrated NOAA-21"] },
      grid: { left: 50, right: 16, top: 62, bottom: 34 },
      xAxis: { type: "category", data: s.period, ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: (v: string) => v.slice(0, 7) } },
      yAxis: { type: "value", name: "cells / day (S-NPP scale)", ...AXIS },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 14, bottom: 4, borderColor: "#2d3a4a", textStyle: { color: "#8d9bad" } }],
      series: [
        { name: "Observed VIIRS S-NPP (reference)", type: "line", data: s.observed.SNPP, symbol: "none", lineStyle: { color: PLATFORM_COLOR.SNPP, width: 2 }, itemStyle: { color: PLATFORM_COLOR.SNPP } },
        { name: "Calibrated MODIS", type: "line", data: s.calibrated_modis, symbol: "none", lineStyle: { color: PLATFORM_COLOR.MODIS, width: 1.4 }, itemStyle: { color: PLATFORM_COLOR.MODIS },
          markArea: { silent: true, itemStyle: { color: "rgba(240,160,60,0.06)" }, label: { color: "#8d9bad", fontSize: 10.5, position: "insideTop" },
            data: [[{ xAxis: s.period.find((p: string) => p >= "2022-01") || s.period[0], name: "held-out test years" }, { xAxis: s.period.find((p: string) => p >= "2025-12") || s.period[s.period.length - 1] }]] } },
        { name: "Calibrated NOAA-20", type: "line", data: s.calibrated_noaa20, symbol: "none", lineStyle: { color: PLATFORM_COLOR.NOAA20, width: 1.2 }, itemStyle: { color: PLATFORM_COLOR.NOAA20 } },
        { name: "Calibrated NOAA-21", type: "line", data: s.calibrated_noaa21, symbol: "none", lineStyle: { color: PLATFORM_COLOR.NOAA21, width: 1.2 }, itemStyle: { color: PLATFORM_COLOR.NOAA21 } },
      ],
    };
  }, [s]);
  return (
    <div className="card">
      <h3>Calibration check on the overlap period</h3>
      <div className="sub">Each platform converted to the S-NPP scale, monthly. Where the lines overlap, the calibration reproduces the reference; the shaded years were never used for fitting the MODIS link.</div>
      {option ? <EChart option={option} height={300} /> : <div className="skeleton" style={{ height: 300 }} />}
    </div>
  );
}

export function Seasonal({ aoi, year }: { aoi: string; year: number }) {
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    setS(null);
    get("seasonal", { aoi, end_year: 2026 }).then(setS).catch(() => setS(null));
  }, [aoi]);
  const option = useMemo(() => {
    if (!s) return null;
    const band = s.p75.map((v: number | null, i: number) => (v === null || s.p25[i] === null ? null : v - s.p25[i]));
    const yr = s.by_year[year] || [];
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v: number) => (v === null || v === undefined ? "—" : fmt(v, 1)) },
      legend: { ...LEGEND, data: ["Median 2001–2025", "Interquartile range", String(year)] },
      grid: { left: 50, right: 16, top: 34, bottom: 26 },
      xAxis: { type: "category", data: MONTHS, ...AXIS },
      yAxis: { type: "value", name: "cells / day", ...AXIS },
      series: [
        { name: "Interquartile range", type: "line", data: s.p25, stack: "iqr", symbol: "none", lineStyle: { opacity: 0 }, tooltip: { show: false } },
        { name: "Interquartile range", type: "line", data: band, stack: "iqr", symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: "rgba(240,160,60,0.18)" }, tooltip: { show: false } },
        { name: "Median 2001–2025", type: "line", data: s.median, symbol: "circle", symbolSize: 4, lineStyle: { color: "#f0a03c", width: 2 }, itemStyle: { color: "#f0a03c" } },
        { name: String(year), type: "line", data: yr, symbol: "circle", symbolSize: 4, lineStyle: { color: "#e4eaf1", width: 1.6 }, itemStyle: { color: "#e4eaf1" } },
      ],
    };
  }, [s, year]);
  return (
    <div className="card">
      <h3>Seasonal pattern</h3>
      <div className="sub">Monthly mean harmonized activity: the 2001–2025 median and middle half of years, against {year}.</div>
      {option ? <EChart option={option} height={280} /> : <div className="skeleton" style={{ height: 280 }} />}
    </div>
  );
}
