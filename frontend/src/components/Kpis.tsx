import { useEffect, useState } from "react";
import { ANOMALY_LABEL, METHOD_LABEL, MONTHS, RATING_LABEL, fmt, get, niceDate } from "../api";

type Props = { aoi: string; aoiInfo: any; onPickDate: (d: string) => void };

export function ratingClass(r: string) {
  return r === "high" ? "good" : r === "moderate" ? "info" : r === "low" ? "warn" : "bad";
}

export default function Kpis({ aoi, aoiInfo, onPickDate }: Props) {
  const [s, setS] = useState<any>(null);
  const [c, setC] = useState<any>(null);
  const [cErr, setCErr] = useState<string | null>(null);
  const [days, setDays] = useState(14);

  useEffect(() => {
    setS(null);
    if (!aoiInfo?.harmonized) return;
    get("summary", { aoi }).then(setS).catch(() => setS(null));
  }, [aoi, aoiInfo]);
  useEffect(() => {
    setC(null);
    setCErr(null);
    if (!aoiInfo?.harmonized) return;
    get("compare", { aoi, days }).then(setC).catch((e) => setCErr(e.message));
  }, [aoi, aoiInfo, days]);

  const rel = aoiInfo?.reliability;
  if (aoiInfo && !aoiInfo.harmonized) {
    return (
      <div className="notice info">
        <b>{aoiInfo.name}</b> lies outside the preprocessed Pakistan record ({fmt(100 * (aoiInfo.share_inside_pakistan || 0), 0)}% inside).
        Historical FIRMS data have not been acquired here, so no harmonized score, calendar or anomaly analysis is shown, and the
        Pakistan calibration is not applied. Recent raw observations can be fetched on demand from the map panel.
      </div>
    );
  }
  const an = s?.last_365_anomaly_days || {};
  const diff = c?.pct_difference;
  return (
    <div className="grid kpis">
      <div className="card kpi">
        <div className="label">Region</div>
        <div className="value" style={{ fontSize: 18 }}>{aoiInfo?.name || "…"}</div>
        <div className="foot row">
          <span className="muted">{aoiInfo?.level === "ADM0" ? "Country" : aoiInfo?.level === "ADM1" ? "Province / territory" : aoiInfo?.level === "ADM2" ? "District" : "Custom area"}
            {aoiInfo ? ` · ${fmt(aoiInfo.area_km2, 0)} km²` : ""}</span>
        </div>
        {rel && (
          <div className="foot" title={`Held-out 2022–2025 agreement of calibrated MODIS with observed S-NPP: Spearman ${fmt(rel.test_spearman, 2)} over ${rel.test_windows_active ?? "—"} active 8-day windows`}>
            <span className={`pill ${ratingClass(rel.rating)}`}>Reliability: {RATING_LABEL[rel.rating] || rel.rating}</span>
          </div>
        )}
      </div>

      <div className="card kpi">
        <div className="label">Latest data</div>
        <div className="value" style={{ fontSize: 18 }}>{s ? niceDate(s.latest_date) : "…"}</div>
        {s && (
          <div className="foot">
            {METHOD_LABEL[s.latest.method]}
            {s.latest.provisional && <div><span className="pill warn" style={{ marginTop: 4 }}>Provisional (near-real-time)</span></div>}
          </div>
        )}
      </div>

      <div className="card kpi accent">
        <div className="label row between">
          <span>Now vs historical median</span>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ padding: "0 4px", fontSize: 11 }} aria-label="Comparison period">
            {[7, 14, 30].map((d) => <option key={d} value={d}>{d} days</option>)}
          </select>
        </div>
        {cErr && <div className="foot error">{cErr}</div>}
        {c && (
          <>
            <div className="value" style={{ color: diff === null ? undefined : diff > 25 ? "#ef6461" : diff < -25 ? "#6aa9e9" : undefined }}>
              {diff === null ? "—" : `${diff > 0 ? "+" : ""}${fmt(diff, 0)}%`}
            </div>
            <div className="foot num">
              {fmt(c.current, 1)} vs median {fmt(c.historical_median, 1)} cells/day · {c.years_used} years
            </div>
            {c.observed_era && (
              <div className="foot num" title="Median of the years observed directly by VIIRS S-NPP only, excluding years reconstructed from MODIS">
                vs observed S-NPP years only ({c.observed_era.years}): {c.observed_era.pct_difference > 0 ? "+" : ""}{fmt(c.observed_era.pct_difference, 0)}%
              </div>
            )}
            <div className="foot">{niceDate(c.start)} – {niceDate(c.end)} · rank {c.rank} of {c.years_used + 1}
              {c.provisional_days > 0 && <span className="pill warn" style={{ marginLeft: 4 }}>{c.provisional_days} provisional days</span>}
            </div>
          </>
        )}
        {!c && !cErr && <div className="skeleton" style={{ height: 40, marginTop: 6 }} />}
      </div>

      <div className="card kpi">
        <div className="label">Typical peak</div>
        {s?.most_active_month ? (
          <>
            <div className="value">{MONTHS[s.most_active_month.month - 1]}<small>most active month</small></div>
            <div className="foot">Most active year: {s.most_active_year?.year} · 2001–2025 harmonized</div>
          </>
        ) : <div className="foot">…</div>}
      </div>

      <div className="card kpi">
        <div className="label">Unusual activity, last 365 days</div>
        {s ? (
          <>
            <div className="value">{(an.highly_unusual || 0) + (an.elevated || 0)}<small>days flagged</small></div>
            <div className="foot">{an.highly_unusual || 0} {ANOMALY_LABEL.highly_unusual.toLowerCase()} · {an.elevated || 0} elevated</div>
          </>
        ) : <div className="foot">…</div>}
      </div>

      <div className="card kpi">
        <div className="label">Record peak (8-day)</div>
        {s?.peak ? (
          <>
            <div className="value" style={{ cursor: "pointer" }} onClick={() => onPickDate(s.peak.date)} title="Show on calendar and map">
              {fmt(s.peak.value, 0)}<small>cells/day</small>
            </div>
            <div className="foot">{niceDate(s.peak.date)} · {s.peak.method === "reference_observed" ? "observed" : "reconstructed"}</div>
          </>
        ) : <div className="foot">…</div>}
      </div>
    </div>
  );
}
