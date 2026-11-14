import { useEffect, useMemo, useState } from "react";
import EChart, { AXIS, TOOLTIP } from "./EChart";
import { ANOMALY_LABEL, METHOD_LABEL, MONTHS, PLATFORM_LABEL, addDays, fmt, get, niceDate } from "../api";
import { PALETTES, colorAt } from "../palettes";

type Props = {
  aoi: string;
  palette: string;
  selected: string | null;
  onSelect: (d: string) => void;
  focusYear?: number | null;
};

const ZERO = "#1a2531";
const NODATA = "#3a4049";
const MONTH_START = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];

export default function Calendar({ aoi, palette, selected, onSelect, focusYear }: Props) {
  const [measure, setMeasure] = useState<"h8" | "raw">("h8");
  const [platform, setPlatform] = useState("SNPP");
  const [year, setYear] = useState<number | "all">("all");
  const [markers, setMarkers] = useState(true);
  const [cal, setCal] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setErr(null);
    setCal(null);
    get("calendar", { aoi, measure, platform: measure === "raw" ? platform : undefined })
      .then(setCal)
      .catch((e) => setErr(String(e.message || e)));
  }, [aoi, measure, platform]);

  useEffect(() => {
    if (focusYear) setYear(focusYear);
  }, [focusYear]);

  const derived = useMemo(() => {
    if (!cal) return null;
    const n = cal.n;
    const dates: string[] = new Array(n);
    const years: number[] = [];
    const yr: number[] = new Array(n);
    const doy: number[] = new Array(n);
    let d = new Date(cal.start + "T00:00:00Z");
    let prevY = -1;
    let dayCounter = 0;
    for (let i = 0; i < n; i++) {
      const iso = d.toISOString().slice(0, 10);
      dates[i] = iso;
      const y = d.getUTCFullYear();
      if (y !== prevY) {
        years.push(y);
        prevY = y;
        dayCounter = Math.floor((d.getTime() - Date.UTC(y, 0, 1)) / 86400000);
      }
      yr[i] = y;
      doy[i] = ++dayCounter;
      d = new Date(d.getTime() + 86400000);
    }
    // colour scale value (0..100)
    let scale: number[] = cal.index.map((v: number | null) => v);
    let p99 = 0;
    if (cal.measure === "raw") {
      const pos = cal.value.filter((v: number | null) => v && v > 0).sort((a: number, b: number) => a - b);
      p99 = pos.length ? pos[Math.floor(pos.length * 0.99)] : 1;
      scale = cal.value.map((v: number | null) =>
        v === null ? null : v === 0 ? 0 : Math.max(1, Math.min(100, (100 * Math.log1p(v)) / Math.log1p(p99)))
      );
    }
    return { dates, years, yr, doy, scale, p99 };
  }, [cal]);

  const option = useMemo(() => {
    if (!cal || !derived) return null;
    const { dates, years, yr, doy, scale } = derived;
    const act: any[] = [], zero: any[] = [], none: any[] = [], gap: any[] = [], prov: any[] = [], anom: any[] = [], sel: any[] = [];
    const single = year !== "all";
    for (let i = 0; i < cal.n; i++) {
      if (single && yr[i] !== year) continue;
      const pos = single ? [dates[i]] : [doy[i] - 1, years.indexOf(yr[i])];
      const v = cal.value[i];
      const s = scale[i];
      if (v === null || cal.method[i] === 0) none.push([...pos, 0, i]);
      else if (cal.zero[i] || s === 0) zero.push([...pos, 0, i]);
      else if (s === null) zero.push([...pos, 0, i]);
      else act.push([...pos, s, i]);
      if (markers) {
        if (cal.gap[i]) gap.push([...pos, 0, i]);
        if (cal.provisional[i]) prov.push([...pos, 0, i]);
        if (cal.anomaly[i] === 4) anom.push([...pos, 0, i]);
      }
      if (selected && dates[i] === selected) sel.push([...pos, 0, i]);
    }
    const coord = single ? { coordinateSystem: "calendar" } : {};
    const tip = (p: any) => {
      const i = p.data[p.data.length - 1];
      const parts = [`<b>${niceDate(dates[i])}</b>`];
      if (cal.measure === "h8") {
        if (cal.method[i] === 0) parts.push("No platform delivering data");
        else {
          parts.push(
            `Harmonized activity <b>${fmt(cal.value[i], 1)}</b> cells/day` +
              (cal.lo[i] !== cal.hi[i] ? ` <span style="color:#8d9bad">(80% interval ${fmt(cal.lo[i], 1)}–${fmt(cal.hi[i], 1)})</span>` : "")
          );
          parts.push(`Activity index <b>${cal.index[i] === null ? "—" : cal.index[i]}</b> / 100`);
          parts.push(`<span style="color:#8d9bad">8-day window ${niceDate(addDays(dates[i], -7))} – ${niceDate(dates[i])}</span>`);
          parts.push(METHOD_LABEL[cal.codes.method[cal.method[i]]] || "");
          const an = cal.codes.anomaly[cal.anomaly[i]];
          parts.push(`Anomaly: ${ANOMALY_LABEL[an] || an}${cal.z[i] !== null ? ` (z = ${fmt(cal.z[i], 1)})` : ""}`);
          if (cal.zero[i]) parts.push(`<span style="color:#8d9bad">No detections recorded by the carrier platform in this window — not proof of no fire.</span>`);
        }
      } else {
        parts.push(cal.value[i] === null ? "Platform not delivering data" : `Observed active 1 km cells: <b>${cal.value[i]}</b>`);
        parts.push(`<span style="color:#8d9bad">Raw daily observation, ${PLATFORM_LABEL[cal.platform]} — not harmonized</span>`);
      }
      if (cal.provisional[i]) parts.push(`<span style="color:#e8b84a">Provisional: rests on near-real-time data</span>`);
      if (cal.gap[i]) parts.push(`<span style="color:#ef6461">FIRMS lists missing data for this platform in the window</span>`);
      return parts.join("<br/>");
    };
    const stops = PALETTES[palette].stops;
    const base: any = {
      tooltip: { ...TOOLTIP, formatter: tip },
      visualMap: [
        { show: false, seriesIndex: 0, min: 1, max: 100, dimension: single ? 1 : 2, inRange: { color: stops } },
        { show: false, seriesIndex: 1, min: 0, max: 1, dimension: single ? 1 : 2, inRange: { color: [ZERO, ZERO] } },
        { show: false, seriesIndex: 2, min: 0, max: 1, dimension: single ? 1 : 2, inRange: { color: [NODATA, NODATA] } },
      ],
      series: [
        { type: "heatmap", data: act, ...coord, progressive: 0 },
        { type: "heatmap", data: zero, ...coord, itemStyle: { color: ZERO }, progressive: 0 },
        { type: "heatmap", data: none, ...coord, itemStyle: { color: NODATA }, progressive: 0 },
        { type: "scatter", data: gap, ...coord, symbol: "rect", symbolSize: single ? 6 : 3, itemStyle: { color: "#ef6461" }, silent: true, z: 5 },
        { type: "scatter", data: prov, ...coord, symbol: "circle", symbolSize: single ? 5 : 2.5, itemStyle: { color: "#ffffff", opacity: 0.85 }, silent: true, z: 5 },
        { type: "scatter", data: anom, ...coord, symbol: "triangle", symbolSize: single ? 7 : 4, itemStyle: { color: "#ff4d6d", borderColor: "#0a0e13", borderWidth: 0.5 }, silent: true, z: 6 },
        { type: "scatter", data: sel, ...coord, symbol: "rect", symbolSize: single ? 18 : 9, itemStyle: { color: "transparent", borderColor: "#ffffff", borderWidth: 2 }, silent: true, z: 7 },
      ],
    };
    if (single) {
      return {
        ...base,
        calendar: {
          range: String(year), top: 30, left: 40, right: 10, bottom: 10, cellSize: ["auto", 17],
          itemStyle: { color: "#0e141b", borderColor: "#0a0e13", borderWidth: 2 },
          splitLine: { lineStyle: { color: "#2d3a4a", width: 1 } },
          dayLabel: { color: "#8d9bad", fontSize: 10, firstDay: 1 }, monthLabel: { color: "#aab6c5", fontSize: 11 },
          yearLabel: { show: false },
        },
      };
    }
    return {
      ...base,
      grid: { left: 46, right: 12, top: 8, bottom: 26 },
      xAxis: {
        type: "category", data: Array.from({ length: 366 }, (_, k) => k + 1), ...AXIS, splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { ...AXIS.axisLabel, interval: (i: number) => MONTH_START.includes(i + 1), formatter: (v: string) => MONTHS[MONTH_START.indexOf(Number(v))] || "" },
      },
      yAxis: { type: "category", data: years.map(String), inverse: true, ...AXIS, splitLine: { show: false }, axisTick: { show: false } },
    };
  }, [cal, derived, palette, year, markers, selected]);

  const years = derived?.years || [];
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>Burning activity calendar</h3>
          <div className="sub" style={{ marginBottom: 6 }}>
            {cal ? cal.label : "Loading…"} · click a day to inspect it on the map
          </div>
        </div>
        <div className="row">
          <div className="seg">
            <button className={measure === "h8" ? "on" : ""} onClick={() => setMeasure("h8")}>Harmonized 8-day</button>
            <button className={measure === "raw" ? "on" : ""} onClick={() => setMeasure("raw")}>Raw daily</button>
          </div>
          {measure === "raw" && (
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} aria-label="Platform">
              {["SNPP", "NOAA20", "NOAA21", "MODIS", "Terra", "Aqua"].map((p) => (
                <option key={p} value={p}>{PLATFORM_LABEL[p]}</option>
              ))}
            </select>
          )}
          <select value={String(year)} onChange={(e) => setYear(e.target.value === "all" ? "all" : Number(e.target.value))} aria-label="Year">
            <option value="all">All years (day × year)</option>
            {years.slice().reverse().map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <label className="chk"><input type="checkbox" checked={markers} onChange={(e) => setMarkers(e.target.checked)} /> markers</label>
        </div>
      </div>
      {err && <div className="notice bad">{err}</div>}
      {!cal && !err && <div className="skeleton" style={{ height: 380 }} />}
      {cal && option && <EChart option={option} height={year === "all" ? Math.max(260, years.length * 14 + 40) : 190} onClick={(p) => p.data && onSelect(derived!.dates[p.data[p.data.length - 1]])} />}
      <div className="cal-legend" style={{ marginTop: 8 }}>
        <span>
          {measure === "h8" ? "Activity index" : "Observed cells (log scale)"}{" "}
          <span style={{ display: "inline-block", width: 120, height: 9, borderRadius: 3, verticalAlign: -1, background: `linear-gradient(90deg, ${PALETTES[palette].stops.join(",")})` }} />{" "}
          {measure === "h8" ? "1 → 100 (percentile of this area's active periods)" : `1 → ${fmt(derived?.p99 ?? null, 0)}+`}
        </span>
        <span><i className="sw" style={{ background: ZERO }} />no detections recorded</span>
        <span><i className="sw" style={{ background: NODATA }} />no platform delivering</span>
        <span><i className="sw" style={{ background: "#ef6461", width: 6, height: 6 }} />FIRMS missing-data day</span>
        <span><i className="sw" style={{ background: "#fff", width: 6, height: 6, borderRadius: 3 }} />provisional (NRT)</span>
        {measure === "h8" && <span><span style={{ color: "#ff4d6d" }}>▲</span> highly unusual</span>}
      </div>
      {measure === "h8" ? (
        <div className="faint" style={{ fontSize: 11.5, marginTop: 6 }}>
          Each day shows the 8-day rolling harmonized value ending on that date (the resolution at which the sensors were calibrated).
          Before 27 Jan 2012 values are reconstructed from MODIS; from 3 Nov 2026 they are calibrated NOAA-21.
        </div>
      ) : (
        <div className="faint" style={{ fontSize: 11.5, marginTop: 6 }}>
          Raw daily counts are one platform's own observations. They are not comparable across platforms and are not harmonized.
        </div>
      )}
    </div>
  );
}
