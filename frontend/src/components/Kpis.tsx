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

  // Each effect ignores replies that arrive after the area or period has changed.
  useEffect(() => {
    let live = true;
    setS(null);
    if (!aoiInfo?.harmonized || aoiInfo.aoi_id !== aoi) return;
    get("summary", { aoi }).then((r) => live && setS(r)).catch(() => live && setS(null));
    return () => { live = false; };
  }, [aoi, aoiInfo]);
  useEffect(() => {
    let live = true;
    setC(null);
    setCErr(null);
    if (!aoiInfo?.harmonized || aoiInfo.aoi_id !== aoi) return;
    get("compare", { aoi, days }).then((r) => live && setC(r)).catch((e) => live && setCErr(e.message));
    return () => { live = false; };
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
  return (
    <>
    <Hero c={c} cErr={cErr} days={days} setDays={setDays} name={aoiInfo?.name} />
    <div className="grid kpis">
      <div className="card kpi">
        <div className="label">Region</div>
        {aoiInfo ? <div className="value" style={{ fontSize: 18 }}>{aoiInfo.name}</div> : <Sk w="70%" />}
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
        {s ? <div className="value" style={{ fontSize: 18 }}>{niceDate(s.latest_date)}</div> : <Sk w="60%" />}
        {s && (
          <div className="foot">
            {METHOD_LABEL[s.latest.method]}
            {s.latest.provisional && <div><span className="pill warn" style={{ marginTop: 4 }}>Provisional (near-real-time)</span></div>}
          </div>
        )}
      </div>

      <div className="card kpi">
        <div className="label">Typical peak</div>
        {s?.most_active_month ? (
          <>
            <div className="value">{MONTHS[s.most_active_month.month - 1]}<small>most active month</small></div>
            <div className="foot">Most active year: {s.most_active_year?.year} · 2001–2025 harmonized</div>
          </>
        ) : <Sk w="50%" />}
      </div>

      <div className="card kpi">
        <div className="label">Unusual activity, last 365 days</div>
        {s ? (
          <>
            <div className="value">{(an.highly_unusual || 0) + (an.elevated || 0)}<small>days flagged</small></div>
            <div className="foot">{an.highly_unusual || 0} {ANOMALY_LABEL.highly_unusual.toLowerCase()} · {an.elevated || 0} elevated</div>
          </>
        ) : <Sk w="40%" />}
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
        ) : <Sk w="45%" />}
      </div>
    </div>
    </>
  );
}

/** Loading placeholder shaped like a KPI value and its footnote. */
function Sk({ w }: { w: string }) {
  return (
    <div aria-busy="true" aria-label="Loading">
      <div className="skeleton" style={{ height: 22, width: w, marginTop: 6 }} />
      <div className="skeleton" style={{ height: 10, width: "85%", marginTop: 8 }} />
    </div>
  );
}

function ordinal(n: number) {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] || "th";
  return `${n}${s}`;
}

function signed(v: number) {
  return `${v > 0 ? "+" : ""}${fmt(v, 0)}%`;
}

/** One-sentence headline: the selected period against the same dates in every previous year. */
function Hero({ c, cErr, days, setDays, name }: { c: any; cErr: string | null; days: number; setDays: (d: number) => void; name?: string }) {
  // Below one active cell per day a percentage change is dominated by noise, so it is not headlined.
  const low = !!c && Math.max(c.current, c.historical_median) < 1;
  const diff: number | null = c && !low ? c.pct_difference : null;
  const dir = diff === null ? null : diff >= 10 ? "up" : diff <= -10 ? "down" : "flat";
  // rank counts years below the current value (1 = lowest); convert to "Nth highest".
  const fromTop = c ? c.years_used + 2 - c.rank : null;
  return (
    <section className="card hero" aria-live="polite">
      <div className="hero-main">
        <div className="hero-kicker">
          {name || "Selected area"} · last {days} days{c ? ` · ${niceDate(c.start)} – ${niceDate(c.end)}` : ""}
        </div>
        {c && diff !== null && (
          <>
            <p className="hero-line">
              Satellite-detected burning activity is{" "}
              {dir === "flat"
                ? <><em className="flat">close to</em> the {c.years_used}-year median for the same dates ({signed(diff)}).</>
                : <><em className={dir!}>{fmt(Math.abs(diff), 0)}% {dir === "up" ? "above" : "below"}</em> the {c.years_used}-year median for the same dates.</>}
            </p>
            <div className="hero-sub num">
              {fmt(c.current, 1)} vs {fmt(c.historical_median, 1)} active cells/day on the S-NPP scale
              {fromTop !== null && <> · {ordinal(fromTop)} highest of {c.years_used + 1} years</>}
              {c.observed_era?.pct_difference != null && (
                <span title="Median of the years observed directly by VIIRS S-NPP only, excluding years reconstructed from MODIS">
                  {" "}· {signed(c.observed_era.pct_difference)} vs observed S-NPP years only ({c.observed_era.years})
                </span>
              )}
            </div>
          </>
        )}
        {c && diff === null && (
          <>
            <p className="hero-line">
              {low
                ? "Very little burning is detected here on these dates, now or in a typical year."
                : "No burning was recorded on these dates in the typical year, so a percentage comparison is not meaningful."}
            </p>
            <div className="hero-sub num">
              {fmt(c.current, 1)} vs median {fmt(c.historical_median, 1)} active cells/day on the S-NPP scale · percentage changes at this level are not meaningful
            </div>
          </>
        )}
        {cErr && <p className="hero-sub">A like-for-like comparison is not available for this period: {cErr}.</p>}
        {!c && !cErr && (
          <div aria-busy="true" aria-label="Loading">
            <div className="skeleton" style={{ height: 26, width: "70%", marginTop: 8 }} />
            <div className="skeleton" style={{ height: 12, width: "50%", marginTop: 10 }} />
          </div>
        )}
      </div>
      <div className="hero-side">
        <div className="seg" role="group" aria-label="Comparison period">
          {[7, 14, 30].map((d) => (
            <button key={d} className={d === days ? "on" : ""} aria-pressed={d === days} onClick={() => setDays(d)}>{d} days</button>
          ))}
        </div>
        {c?.provisional_days > 0 && (
          <span className="pill warn" title="These days rely on near-real-time FIRMS data, which can still change">
            Provisional · {c.provisional_days} of {days} days near-real-time
          </span>
        )}
      </div>
    </section>
  );
}
