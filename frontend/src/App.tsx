import { useEffect, useMemo, useState } from "react";
import { addDays, fmt, get, niceDate, post } from "./api";
import { PALETTES } from "./palettes";
import Calendar from "./components/Calendar";
import FireMap, { Filters, Layers } from "./components/FireMap";
import DayPanel from "./components/DayPanel";
import Kpis from "./components/Kpis";
import { BeforeAfter, CalibrationCheck, PlatformSeries, Seasonal } from "./components/Charts";
import { Anomalies, CompareHistory, Windows } from "./components/Intel";
import { StoryBanner, StoryList } from "./components/Stories";
import Method from "./components/Method";

const DEFAULT_FILTERS: Filters = {
  platforms: ["Terra", "Aqua", "SNPP", "NOAA20", "NOAA21"],
  daynight: ["D", "N"],
  modisConf: ["nominal", "high"],
  viirsConf: ["nominal", "high"],
  types: ["0", "-1"],
  persist: ["normal", "suspected_persistent", "known_static"],
};

type Tab = "dashboard" | "stories" | "method";

function Logo() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="#151c26" />
      <path d="M16 5c1.5 4.5 6 6.5 6 12a6 6 0 0 1-12 0c0-3 1.5-4.5 2.5-6 .3 2 1.3 3 2.3 3.4C14 11 15 8 16 5z" fill="#f0a03c" />
      <circle cx="16" cy="18" r="2.6" fill="#151c26" />
    </svg>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [meta, setMeta] = useState<any>(null);
  const [aois, setAois] = useState<any[]>([]);
  const [aoi, setAoi] = useState("PAK");
  const [aoiInfo, setAoiInfo] = useState<any>(null);
  const [date, setDate] = useState<string | null>(null);
  const [range, setRange] = useState<[string, string]>(["2026-11-06", "2026-11-13"]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [layers, setLayers] = useState<Layers>({ hotspots: true, grid: false, choropleth: false, imagery: false, level: "ADM2" });
  const [palette, setPalette] = useState<string>(() => {
    try { return localStorage.getItem("fs-palette") || "viridis"; } catch { return "viridis"; }
  });
  const [stories, setStories] = useState<any[] | null>(null);
  const [story, setStory] = useState<any>(null);
  const [step, setStep] = useState(0);
  const [fitTo, setFitTo] = useState<number[] | null>(null);
  const [focusYear, setFocusYear] = useState<number | null>(null);
  const [ondemand, setOndemand] = useState<any>(null);
  const [odBusy, setOdBusy] = useState(false);
  const [bboxText, setBboxText] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Shareable links: ?tab=stories|method, ?aoi=PAK-ADM1-5, ?date=2022-05-20, ?story=sherani-2022
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  useEffect(() => {
    const t = params.get("tab");
    if (t === "stories" || t === "method") setTab(t);
    const a = params.get("aoi");
    if (a) setAoi(a);
  }, []);

  useEffect(() => {
    get("meta").then((m) => {
      setMeta(m);
      const d = params.get("date") || m.latest_date;
      setDate(d);
      setRange([addDays(d, -7), d]);
    }).catch((e) => setErr(`Cannot reach the FireSight API (${e.message}). Start it with: uvicorn backend.api.main:app --port 8000`));
    get("aois").then(setAois).catch(() => {});
    get("stories").then((ss) => {
      setStories(ss);
      const sid = params.get("story");
      const st = ss.find((x: any) => x.id === sid);
      if (st) openStory(st);
    }).catch(() => setStories([]));
  }, []);

  useEffect(() => {
    try { localStorage.setItem("fs-palette", palette); } catch { /* ignore */ }
  }, [palette]);

  useEffect(() => {
    setAoiInfo(null);
    setOndemand(null);
    get(`aoi/${aoi}`).then(setAoiInfo).catch((e) => setErr(e.message));
  }, [aoi]);

  const provinces = useMemo(() => aois.filter((a) => a.level === "ADM1").sort((a, b) => a.name.localeCompare(b.name)), [aois]);
  const selProvince = aoiInfo?.level === "ADM1" ? aoi : aoiInfo?.level === "ADM2" ? aoiInfo.parent : "";
  const districts = useMemo(() => aois.filter((a) => a.level === "ADM2" && a.parent === selProvince).sort((a, b) => a.name.localeCompare(b.name)), [aois, selProvince]);

  function pickDate(d: string) {
    setDate(d);
    setRange([addDays(d, -7), d]);
  }

  function selectAoi(id: string) {
    setFitTo(null);
    setAoi(id);
  }

  function applyStep(s: any, i: number) {
    const st = s.steps[i];
    setStep(i);
    setDate(st.date);
    setRange(st.range);
    setFocusYear(Number(st.date.slice(0, 4)));
  }

  function openStory(s: any) {
    setTab("dashboard");
    setStory(s);
    setFitTo(s.bounds);
    setAoi(s.aoi_id);
    setLayers((l) => ({ ...l, hotspots: true }));
    applyStep(s, 0);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function createCustom(spec: any) {
    setMsg("Computing the record for the custom area…");
    try {
      const r = await post("custom", spec);
      setAois((xs) => (xs.some((x) => x.aoi_id === r.aoi_id) ? xs : [...xs, { aoi_id: r.aoi_id, name: r.name, level: "CUSTOM", bounds: r.bounds }]));
      setFitTo(r.bounds);
      setAoi(r.aoi_id);
      setMsg(r.coverage === "pakistan_processed" ? `Custom area ready (${fmt(r.area_km2, 0)} km², ${r.seconds}s).` : "This area is outside the processed Pakistan record.");
    } catch (e: any) {
      setMsg(`Could not create the area: ${e.message}`);
    }
  }

  function submitBbox() {
    const v = bboxText.split(/[ ,;]+/).map(Number).filter((x) => !Number.isNaN(x));
    if (v.length !== 4) { setMsg("Enter four numbers: west, south, east, north (degrees)."); return; }
    createCustom({ type: "bbox", bbox: v });
  }

  async function fetchOndemand() {
    if (!aoiInfo?.bounds) return;
    setOdBusy(true);
    try {
      const r = await get("ondemand", { bbox: aoiInfo.bounds.map((x: number) => x.toFixed(3)).join(","), days: 5 }, false);
      setOndemand(r);
    } catch (e: any) {
      setMsg(`On-demand retrieval failed: ${e.message}`);
    } finally {
      setOdBusy(false);
    }
  }

  const harmonized = !!aoiInfo?.harmonized;
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <Logo />
          <div>
            <div className="brand-name">FireSight</div>
            <div className="brand-tag">One Earth. Multiple satellites. One harmonized fire history.</div>
          </div>
        </div>
        <nav className="tabs">
          {([["dashboard", "Dashboard"], ["stories", "Fire stories"], ["method", "Method & validation"]] as [Tab, string][]).map(([k, l]) => (
            <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{l}</button>
          ))}
        </nav>
        <div className="spacer" />
        {tab === "dashboard" && (
          <div className="row">
            <div className="ctl">
              <label>Area</label>
              <select value={selProvince || (aoi === "PAK" ? "PAK" : "")} onChange={(e) => { setStory(null); selectAoi(e.target.value); }} aria-label="Province">
                <option value="PAK">Pakistan (country)</option>
                {provinces.map((p) => <option key={p.aoi_id} value={p.aoi_id}>{p.name}</option>)}
                {!selProvince && aoi !== "PAK" && <option value="">{aoiInfo?.name || "Custom area"}</option>}
              </select>
              {selProvince && (
                <select value={aoiInfo?.level === "ADM2" ? aoi : ""} onChange={(e) => { setStory(null); selectAoi(e.target.value || selProvince); }} aria-label="District">
                  <option value="">All districts</option>
                  {districts.map((d) => <option key={d.aoi_id} value={d.aoi_id}>{d.name}</option>)}
                </select>
              )}
            </div>
            <div className="ctl">
              <label>Palette</label>
              <select value={palette} onChange={(e) => setPalette(e.target.value)} aria-label="Colour palette">
                {Object.entries(PALETTES).map(([k, p]) => <option key={k} value={k}>{p.label}</option>)}
              </select>
            </div>
          </div>
        )}
      </header>

      {err && <div className="page"><div className="notice bad">{err}</div></div>}

      {tab === "stories" && <StoryList stories={stories} onOpen={openStory} />}
      {tab === "method" && <Method />}

      {tab === "dashboard" && (
        <div className="page">
          {story && (
            <StoryBanner story={stories?.find((s) => s.id === story.id) || story} step={step}
              setStep={(i) => applyStep(story, i)} onClose={() => { setStory(null); setFocusYear(null); }} />
          )}
          <Kpis aoi={aoi} aoiInfo={aoiInfo} onPickDate={pickDate} />

          <div className="grid main-row">
            <div className="card" style={{ padding: 12 }}>
              <div className="row between" style={{ marginBottom: 10 }}>
                <div className="row">
                  <h3 style={{ margin: 0 }}>Fire map</h3>
                  {aoiInfo && <span className="pill">{aoiInfo.name}</span>}
                  {aoiInfo?.level === "CUSTOM" && aoiInfo.coverage === "pakistan_processed" && <span className="pill info">custom area · Pakistan record</span>}
                  {aoiInfo?.coverage === "not_acquired" && <span className="pill warn">historical data not acquired</span>}
                  {ondemand && <span className="pill warn">on-demand NRT · uncalibrated</span>}
                </div>
                <div className="row">
                  <div className="ctl">
                    <label>From</label>
                    <input type="date" value={range[0]} max={range[1]} onChange={(e) => e.target.value && setRange([e.target.value, range[1]])} />
                    <label>to</label>
                    <input type="date" value={range[1]} min={range[0]} max={meta?.latest_date} onChange={(e) => e.target.value && setRange([range[0], e.target.value])} />
                  </div>
                  <div className="seg">
                    <button onClick={() => date && setRange([date, date])}>Day</button>
                    <button onClick={() => date && setRange([addDays(date, -7), date])}>8 days</button>
                    <button onClick={() => date && setRange([addDays(date, -29), date])}>30 days</button>
                  </div>
                </div>
              </div>
              <FireMap aoi={aoi} aoiInfo={aoiInfo} range={range} filters={filters} setFilters={setFilters} layers={layers} setLayers={setLayers}
                palette={palette} onSelectAoi={(id) => { setStory(null); selectAoi(id); }} onCustom={createCustom} ondemand={ondemand} fitTo={fitTo} />
              <div className="row between" style={{ marginTop: 10 }}>
                <div className="row">
                  <span className="muted" style={{ fontSize: 12 }}>Custom area (W, S, E, N):</span>
                  <input type="text" placeholder="69.8, 31.25, 70.15, 31.62" value={bboxText} onChange={(e) => setBboxText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitBbox()} style={{ width: 210 }} />
                  <button className="btn small" onClick={submitBbox}>Go</button>
                  <span className="faint" style={{ fontSize: 11.5 }}>or use “Draw area” on the map</span>
                </div>
                {aoiInfo?.coverage === "not_acquired" && (
                  <button className="btn small primary" disabled={odBusy} onClick={fetchOndemand}>{odBusy ? "Retrieving…" : "Fetch last 5 days from FIRMS (raw)"}</button>
                )}
              </div>
              {msg && <div className="notice info" style={{ marginTop: 8 }} onClick={() => setMsg(null)}>{msg}</div>}
              {aoiInfo?.note && aoiInfo.level === "CUSTOM" && <div className="faint" style={{ fontSize: 11.5, marginTop: 6 }}>{aoiInfo.note}</div>}
            </div>
            <DayPanel aoi={aoi} date={date} palette={palette} range={range} harmonized={harmonized} />
          </div>

          {harmonized && (
            <>
              <div style={{ marginTop: 14 }}>
                <Calendar aoi={aoi} palette={palette} selected={date} onSelect={pickDate} focusYear={focusYear} />
              </div>

              <div className="section-title">Sensor harmonization <small>raw, calibrated and harmonized series · {aoiInfo?.name}</small></div>
              <BeforeAfter aoi={aoi} onPickDate={pickDate} />
              <div className="grid two" style={{ marginTop: 14 }}>
                <PlatformSeries aoi={aoi} />
                <CalibrationCheck aoi={aoi} />
              </div>

              <div className="section-title">Historical intelligence <small>seasonality, recurring windows and unusual activity</small></div>
              <div className="grid three">
                <Seasonal aoi={aoi} year={date ? Number(date.slice(0, 4)) : 2026} />
                <Windows aoi={aoi} palette={palette} />
                <CompareHistory aoi={aoi} />
              </div>
              <div style={{ marginTop: 14 }}>
                <Anomalies aoi={aoi} onPickDate={pickDate} />
              </div>
            </>
          )}
        </div>
      )}
      <footer className="foot">
        FireSight · NASA Space Apps Challenge 2026 · Data: NASA FIRMS (MODIS C6.1, VIIRS S-NPP / NOAA-20 / NOAA-21), geoBoundaries.
        {meta && <> Latest data {niceDate(meta.latest_date)} · calibration {meta.calibration_version}.</>} Hotspots are thermal anomalies, not confirmed wildfires.
      </footer>
    </>
  );
}
