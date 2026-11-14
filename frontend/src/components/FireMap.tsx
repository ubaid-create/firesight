import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { PLATFORMS, PLATFORM_COLOR, PLATFORM_LABEL, fmt, get, niceDate } from "../api";
import { PALETTES, colorAt, mapRamp } from "../palettes";

export type Filters = {
  platforms: string[];
  daynight: string[];
  modisConf: string[];
  viirsConf: string[];
  types: string[];
  persist: string[];
};

export type Layers = { hotspots: boolean; grid: boolean; choropleth: boolean; imagery: boolean; level: "ADM1" | "ADM2" };

type Props = {
  aoi: string;
  aoiInfo: any;
  range: [string, string];
  filters: Filters;
  setFilters: (f: Filters) => void;
  layers: Layers;
  setLayers: (l: Layers) => void;
  palette: string;
  onSelectAoi: (id: string) => void;
  onCustom: (spec: any) => void;
  ondemand: any | null;
  fitTo?: number[] | null;
};

const BASEMAP = ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"];

function gibsUrl(date: string) {
  const layer = date >= "2018-04-01" ? "VIIRS_NOAA20_CorrectedReflectance_TrueColor" : "MODIS_Terra_CorrectedReflectance_TrueColor";
  return [`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`];
}

const TYPE_OPTS: [string, string][] = [
  ["0", "Presumed vegetation fire"],
  ["-1", "Unclassified (near-real-time)"],
  ["2", "Other static land source"],
  ["3", "Offshore"],
  ["1", "Volcano"],
];
const PERSIST_OPTS: [string, string][] = [
  ["normal", "Normal / seasonal cells"],
  ["suspected_persistent", "Suspected persistent source"],
  ["known_static", "Known static source"],
];

function toggle(list: string[], v: string) {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

export default function FireMap(props: Props) {
  const { aoi, aoiInfo, range, filters, setFilters, layers, setLayers, palette, ondemand, fitTo } = props;
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);
  const [draw, setDraw] = useState<number[][] | null>(null);
  const drawRef = useRef<number[][] | null>(null);
  drawRef.current = draw;
  const onSelectRef = useRef(props.onSelectAoi);
  onSelectRef.current = props.onSelectAoi;
  const choroRef = useRef<any[]>([]);
  const geoRef = useRef<Record<string, any>>({});

  // ---------- init
  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: {
        version: 8,
        sources: {
          carto: { type: "raster", tiles: BASEMAP, tileSize: 256, maxzoom: 16, attribution: "Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors" },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#0a0e13" } },
          { id: "carto", type: "raster", source: "carto", paint: { "raster-opacity": 0.9 } },
        ],
      },
      center: [69.5, 30.2],
      zoom: 4.6,
      attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.current = m;
    m.on("load", async () => {
      m.addSource("gibs", { type: "raster", tiles: gibsUrl("2022-05-20"), tileSize: 256, maxzoom: 9,
        attribution: "Imagery: NASA GIBS / Worldview" });
      m.addLayer({ id: "gibs", type: "raster", source: "gibs", layout: { visibility: "none" }, paint: { "raster-opacity": 0.85 } });
      const [a0, a1, a2] = await Promise.all([get("geo/adm0"), get("geo/adm1"), get("geo/adm2")]);
      geoRef.current = { adm0: a0, adm1: a1, adm2: a2 };
      m.addSource("adm0", { type: "geojson", data: a0 });
      m.addSource("adm1", { type: "geojson", data: a1, promoteId: "aoi_id" });
      m.addSource("adm2", { type: "geojson", data: a2, promoteId: "aoi_id" });
      for (const lv of ["adm1", "adm2"]) {
        m.addLayer({
          id: `${lv}-fill`, type: "fill", source: lv,
          layout: { visibility: lv === "adm2" ? "visible" : "none" },
          paint: { "fill-color": "#000", "fill-opacity": 0 },
        });
      }
      m.addSource("grid", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "grid", type: "fill", source: "grid", paint: { "fill-color": ["get", "c"], "fill-opacity": 0.72 } });
      m.addLayer({ id: "adm2-line", type: "line", source: "adm2", paint: { "line-color": "#3b4a5c", "line-width": 0.5, "line-opacity": 0.6 } });
      m.addLayer({ id: "adm1-line", type: "line", source: "adm1", paint: { "line-color": "#6b7d92", "line-width": 1.1 } });
      m.addLayer({ id: "adm0-line", type: "line", source: "adm0", paint: { "line-color": "#a3b1c2", "line-width": 1.4 } });
      m.addLayer({ id: "hover-line", type: "line", source: "adm2", filter: ["==", ["get", "aoi_id"], ""], paint: { "line-color": "#c9d4e0", "line-width": 1.2 } });
      m.addSource("sel", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "sel-line", type: "line", source: "sel", paint: { "line-color": "#f0a03c", "line-width": 2.4 } });
      m.addSource("hot", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({
        id: "hot", type: "circle", source: "hot",
        paint: {
          "circle-color": ["case", ["==", ["get", "pc"], "known_static"], "#8a8f98",
            ["match", ["get", "p"], "Terra", PLATFORM_COLOR.Terra, "Aqua", PLATFORM_COLOR.Aqua, "SNPP", PLATFORM_COLOR.SNPP,
              "NOAA20", PLATFORM_COLOR.NOAA20, "NOAA21", PLATFORM_COLOR.NOAA21, "#ffffff"]],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, ["case", ["in", ["get", "p"], ["literal", ["Terra", "Aqua"]]], 2.4, 1.5],
            8, ["case", ["in", ["get", "p"], ["literal", ["Terra", "Aqua"]]], 5, 3], 12, ["case", ["in", ["get", "p"], ["literal", ["Terra", "Aqua"]]], 10, 6]],
          "circle-opacity": 0.85,
          "circle-stroke-color": ["case", ["==", ["get", "nrt"], 1], "#ffffff", "#0a0e13"],
          "circle-stroke-width": ["case", ["==", ["get", "nrt"], 1], 0.8, 0.3],
        },
      });
      m.addSource("draw", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "draw-line", type: "line", source: "draw", paint: { "line-color": "#ffb85c", "line-width": 2, "line-dasharray": [2, 1] } });
      m.addLayer({ id: "draw-pt", type: "circle", source: "draw", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-color": "#ffb85c", "circle-radius": 4 } });

      m.on("click", "hot", async (e) => {
        const f = e.features?.[0];
        if (!f || drawRef.current) return;
        const id = f.properties?.id;
        const pop = new maplibregl.Popup({ maxWidth: "300px" }).setLngLat(e.lngLat).setHTML('<div class="muted">Loading…</div>').addTo(m);
        if (id === undefined || id < 0) {
          pop.setHTML(`<b>${PLATFORM_LABEL[f.properties?.p] || f.properties?.p}</b><br/>${f.properties?.date}<br/>FRP ${f.properties?.frp} MW<br/><span class="muted">On-demand near-real-time observation (provisional)</span>`);
          return;
        }
        try {
          const d = await get(`hotspot/${id}`);
          pop.setHTML(`
            <div style="font-weight:600;margin-bottom:4px"><span class="dot" style="background:${PLATFORM_COLOR[d.platform]}"></span> ${d.platform_label}</div>
            <div class="kv">
              <div>Time (UTC)</div><div>${d.ts_utc.slice(0, 16).replace("T", " ")}</div>
              <div>Local solar time</div><div>${fmt(d.local_solar_hour, 2)} h</div>
              <div>Location</div><div>${fmt(d.lat, 4)}, ${fmt(d.lon, 4)}</div>
              <div>FRP</div><div>${fmt(d.frp, 1)} MW</div>
              <div>Confidence</div><div>${d.conf_raw} (${d.conf_class}, ${d.instrument}-specific)</div>
              <div>Brightness</div><div>${fmt(d.brightness, 1)} K / ${fmt(d.brightness_2, 1)} K</div>
              <div>Pixel</div><div>${fmt(d.scan_km, 2)} × ${fmt(d.track_km, 2)} km</div>
              <div>Day/night</div><div>${d.daynight === "D" ? "Day" : "Night"}</div>
              <div>Type</div><div>${d.type_label}</div>
              <div>Cell class</div><div>${String(d.persist_class).replace("_", " ")}</div>
              <div>Product</div><div>${d.processing} v${d.version}</div>
              <div>Source</div><div class="mono" style="font-size:10.5px;word-break:break-all">${d.source_file}:${d.source_row}</div>
            </div>`);
        } catch (err) {
          pop.setHTML(`<span class="error">${err}</span>`);
        }
      });
      m.on("mouseenter", "hot", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "hot", () => (m.getCanvas().style.cursor = ""));
      for (const lv of ["adm1", "adm2"]) {
        m.on("mousemove", `${lv}-fill`, (e) => {
          const f = e.features?.[0];
          if (!f || drawRef.current) return;
          m.setFilter("hover-line", ["==", ["get", "aoi_id"], f.properties?.aoi_id]);
          const c = choroRef.current.find((x) => x.aoi_id === f.properties?.aoi_id);
          m.getCanvas().title = `${f.properties?.name}${c ? ` — index ${c.index ?? "—"}, ${fmt(c.h_roll, 1)} cells/day` : ""} (click to select)`;
        });
        m.on("click", `${lv}-fill`, (e) => {
          if (drawRef.current) return;
          const hits = m.queryRenderedFeatures(e.point, { layers: ["hot"] });
          if (hits.length) return;
          const id = e.features?.[0]?.properties?.aoi_id;
          if (id) onSelectRef.current(id);
        });
      }
      m.on("click", (e) => {
        if (!drawRef.current) return;
        const pts = [...drawRef.current, [e.lngLat.lng, e.lngLat.lat]];
        setDraw(pts);
      });
      setReady(true);
    });
    return () => m.remove();
  }, []);

  // ---------- selected AOI outline + zoom
  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !aoiInfo) return;
    let feat: any = null;
    if (aoiInfo.geometry) feat = { type: "Feature", geometry: aoiInfo.geometry, properties: {} };
    else {
      const data = geoRef.current[aoiInfo.level === "ADM1" ? "adm1" : aoiInfo.level === "ADM2" ? "adm2" : "adm0"];
      const f = data?.features?.find((x: any) => x.properties.aoi_id === aoi);
      if (f) feat = f;
    }
    (m.getSource("sel") as any).setData({ type: "FeatureCollection", features: feat ? [feat] : [] });
    const b = fitTo || aoiInfo.bounds;
    if (b) m.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, duration: 700, maxZoom: 10 });
  }, [ready, aoi, aoiInfo, fitTo]);

  // ---------- hotspots
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const src = m.getSource("hot") as maplibregl.GeoJSONSource;
    if (ondemand) {
      const c = ondemand.cols;
      const feats = c.lat.map((lat: number, i: number) => ({
        type: "Feature", geometry: { type: "Point", coordinates: [c.lon[i], lat] },
        properties: { id: -1, p: c.p[i], frp: c.frp[i], date: c.date[i], pc: "normal", nrt: 1 },
      }));
      src.setData({ type: "FeatureCollection", features: layers.hotspots ? feats : [] } as any);
      setStatus(`${ondemand.total.toLocaleString()} on-demand near-real-time detections (provisional, uncalibrated)`);
      return;
    }
    if (!layers.hotspots || !aoiInfo?.harmonized) {
      src.setData({ type: "FeatureCollection", features: [] } as any);
      if (!layers.hotspots) setStatus("");
      return;
    }
    let cancelled = false;
    setStatus("Loading detections…");
    get("hotspots", {
      aoi, start: range[0], end: range[1], platforms: filters.platforms.join(","), daynight: filters.daynight.join(","),
      modis_conf: filters.modisConf.join(","), viirs_conf: filters.viirsConf.join(","), types: filters.types.join(","),
      persist: filters.persist.join(","),
    }).then((r) => {
      if (cancelled) return;
      const c = r.cols;
      const feats = (c.lat || []).map((lat: number, i: number) => ({
        type: "Feature", geometry: { type: "Point", coordinates: [c.lon[i], lat] },
        properties: { id: c.id[i], p: c.p[i], frp: c.frp[i], date: c.date[i], pc: c.pc[i], nrt: c.nrt[i] },
      }));
      src.setData({ type: "FeatureCollection", features: feats } as any);
      setStatus(r.total === 0 ? "No detections match the filters in this period"
        : `${r.returned.toLocaleString()}${r.truncated ? ` of ${r.total.toLocaleString()} (highest FRP shown)` : ""} detections · ${niceDate(range[0])} – ${niceDate(range[1])}`);
    }).catch((e) => !cancelled && setStatus(`Error: ${e.message}`));
    return () => { cancelled = true; };
  }, [ready, aoi, aoiInfo, range[0], range[1], filters, layers.hotspots, ondemand]);

  // ---------- density grid
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const src = m.getSource("grid") as maplibregl.GeoJSONSource;
    if (!layers.grid || !aoiInfo?.harmonized) {
      src.setData({ type: "FeatureCollection", features: [] } as any);
      return;
    }
    const size = aoiInfo.level === "ADM0" ? 0.1 : aoiInfo.level === "ADM1" ? 0.05 : 0.025;
    get("grid", { aoi, start: range[0], end: range[1], platforms: filters.platforms.join(","), size }).then((g) => {
      const max = Math.max(1, ...g.value);
      const feats = g.lon.map((x: number, i: number) => {
        const y = g.lat[i];
        const t = Math.log1p(g.value[i]) / Math.log1p(max);
        return { type: "Feature", properties: { v: g.value[i], c: colorAt(palette, 0.15 + 0.85 * t) },
          geometry: { type: "Polygon", coordinates: [[[x, y], [x + g.size, y], [x + g.size, y + g.size], [x, y + g.size], [x, y]]] } };
      });
      src.setData({ type: "FeatureCollection", features: feats } as any);
    });
  }, [ready, aoi, aoiInfo, range[0], range[1], filters.platforms, layers.grid, palette]);

  // ---------- harmonized choropleth (index on the range end date)
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const lv = layers.level.toLowerCase();
    const other = lv === "adm2" ? "adm1" : "adm2";
    m.setLayoutProperty(`${lv}-fill`, "visibility", "visible");
    m.setLayoutProperty(`${other}-fill`, "visibility", "none");
    if (!layers.choropleth) {
      m.setPaintProperty(`${lv}-fill`, "fill-opacity", 0);
      return;
    }
    get("choropleth", { level: layers.level, date: range[1] }).then((r) => {
      choroRef.current = r.items;
      r.items.forEach((it: any) => m.setFeatureState({ source: lv, id: it.aoi_id }, { index: it.index ?? -1 }));
      m.setPaintProperty(`${lv}-fill`, "fill-color", ["case", ["<", ["coalesce", ["feature-state", "index"], -1], 0], "#2b313a",
        ["==", ["feature-state", "index"], 0], "#16202b", mapRamp(palette, ["feature-state", "index"])]);
      m.setPaintProperty(`${lv}-fill`, "fill-opacity", 0.62);
    });
  }, [ready, layers.choropleth, layers.level, range[1], palette]);

  // ---------- imagery
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    m.setLayoutProperty("gibs", "visibility", layers.imagery ? "visible" : "none");
    if (!layers.imagery) return;
    try {
      (m.getSource("gibs") as any).setTiles(gibsUrl(range[1]));
    } catch {
      /* tile requests for the previous date were cancelled */
    }
  }, [ready, layers.imagery, range[1]]);

  // ---------- drawing
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const pts = draw || [];
    const feats: any[] = pts.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: p }, properties: {} }));
    if (pts.length > 1) feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: [...pts, pts[0]] }, properties: {} });
    (m.getSource("draw") as any).setData({ type: "FeatureCollection", features: feats });
    m.getCanvas().style.cursor = draw ? "crosshair" : "";
  }, [ready, draw]);

  const legendStops = PALETTES[palette].stops;
  return (
    <div className="map-wrap">
      <div ref={el} className="map" />
      {status && <div className="map-status">{status}</div>}
      <div className="map-toolbar">
        <div className="map-panel">
          <div className="title">Layers</div>
          <label className="chk"><input type="checkbox" checked={layers.hotspots} onChange={(e) => setLayers({ ...layers, hotspots: e.target.checked })} /> Satellite detections</label>
          <label className="chk"><input type="checkbox" checked={layers.grid} onChange={(e) => setLayers({ ...layers, grid: e.target.checked })} /> Activity-density grid</label>
          <label className="chk"><input type="checkbox" checked={layers.choropleth} onChange={(e) => setLayers({ ...layers, choropleth: e.target.checked })} /> Harmonized index by
            <select value={layers.level} onChange={(e) => setLayers({ ...layers, level: e.target.value as any })} style={{ padding: "1px 4px", fontSize: 11.5 }}>
              <option value="ADM2">district</option><option value="ADM1">province</option>
            </select>
          </label>
          <label className="chk"><input type="checkbox" checked={layers.imagery} onChange={(e) => setLayers({ ...layers, imagery: e.target.checked })} /> NASA GIBS true colour</label>
          <div className="row" style={{ marginTop: 6 }}>
            <button className="btn small" onClick={() => setShowFilters(!showFilters)}>{showFilters ? "Hide filters" : "Filters"}</button>
            {!draw && <button className="btn small" onClick={() => setDraw([])} title="Click points on the map, then Finish">Draw area</button>}
            {draw && (
              <>
                <button className="btn small primary" disabled={draw.length < 3} onClick={() => { props.onCustom({ type: "polygon", coordinates: draw }); setDraw(null); }}>Finish ({draw.length})</button>
                <button className="btn small" onClick={() => setDraw(null)}>Cancel</button>
              </>
            )}
          </div>
        </div>
        {showFilters && (
          <div className="map-panel" style={{ maxHeight: 360, overflow: "auto" }}>
            <div className="title">Platform</div>
            {PLATFORMS.map((p) => (
              <label key={p} className="chk"><input type="checkbox" checked={filters.platforms.includes(p)} onChange={() => setFilters({ ...filters, platforms: toggle(filters.platforms, p) })} />
                <span className="dot" style={{ background: PLATFORM_COLOR[p] }} /> {PLATFORM_LABEL[p]}</label>
            ))}
            <div className="title" style={{ marginTop: 8 }}>Day / night</div>
            <div className="row">
              {[["D", "Day"], ["N", "Night"]].map(([k, l]) => (
                <label key={k} className="chk"><input type="checkbox" checked={filters.daynight.includes(k)} onChange={() => setFilters({ ...filters, daynight: toggle(filters.daynight, k) })} /> {l}</label>
              ))}
            </div>
            <div className="title" style={{ marginTop: 8 }}>MODIS confidence (0–100)</div>
            <div className="row">
              {[["low", "<30"], ["nominal", "30–79"], ["high", "≥80"]].map(([k, l]) => (
                <label key={k} className="chk"><input type="checkbox" checked={filters.modisConf.includes(k)} onChange={() => setFilters({ ...filters, modisConf: toggle(filters.modisConf, k) })} /> {l}</label>
              ))}
            </div>
            <div className="title" style={{ marginTop: 8 }}>VIIRS confidence (class)</div>
            <div className="row">
              {["low", "nominal", "high"].map((k) => (
                <label key={k} className="chk"><input type="checkbox" checked={filters.viirsConf.includes(k)} onChange={() => setFilters({ ...filters, viirsConf: toggle(filters.viirsConf, k) })} /> {k}</label>
              ))}
            </div>
            <div className="title" style={{ marginTop: 8 }}>Detection type</div>
            {TYPE_OPTS.map(([k, l]) => (
              <label key={k} className="chk"><input type="checkbox" checked={filters.types.includes(k)} onChange={() => setFilters({ ...filters, types: toggle(filters.types, k) })} /> {l}</label>
            ))}
            <div className="title" style={{ marginTop: 8 }}>Persistent thermal sources</div>
            {PERSIST_OPTS.map(([k, l]) => (
              <label key={k} className="chk"><input type="checkbox" checked={filters.persist.includes(k)} onChange={() => setFilters({ ...filters, persist: toggle(filters.persist, k) })} /> {l}</label>
            ))}
            <div className="faint" style={{ marginTop: 6 }}>Filters change what is shown; original detections are never deleted.</div>
          </div>
        )}
      </div>
      <div className="legend">
        <div className="title muted" style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".07em" }}>Detections</div>
        {PLATFORMS.map((p) => (
          <div key={p}><span className="dot" style={{ background: PLATFORM_COLOR[p] }} /> {PLATFORM_LABEL[p]}</div>
        ))}
        <div><span className="dot" style={{ background: "#8a8f98" }} /> Known static source cell</div>
        <div><span className="dot" style={{ background: "transparent", border: "1px solid #fff" }} /> Near-real-time (provisional)</div>
        {(layers.choropleth || layers.grid) && (
          <>
            <div className="ramp" style={{ background: `linear-gradient(90deg, ${legendStops.join(",")})` }} />
            <div className="row between faint"><span>low</span><span>{layers.choropleth ? "harmonized index" : "cell-days (log)"}</span><span>high</span></div>
          </>
        )}
      </div>
    </div>
  );
}
