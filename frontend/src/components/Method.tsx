import { useEffect, useState } from "react";
import { RATING_LABEL, fmt, get } from "../api";

const LINK_LABEL: Record<string, string> = {
  MODIS_to_SNPP: "MODIS (Terra+Aqua) → S-NPP",
  Terra_to_SNPP: "MODIS Terra → S-NPP",
  Terra_to_MODIS: "Terra → Terra+Aqua (diagnostic)",
  NOAA20_to_SNPP: "NOAA-20 → S-NPP",
  NOAA21_to_SNPP: "NOAA-21 → S-NPP",
};

export default function Method() {
  const [v, setV] = useState<any>(null);
  const [m, setM] = useState<any>(null);
  useEffect(() => {
    get("validation").then(setV);
    get("meta").then(setM);
  }, []);
  return (
    <div className="page prose">
      <h2 style={{ marginTop: 6 }}>Method and validation</h2>
      <p>
        FireSight turns NASA FIRMS active-fire detections from five satellites into one consistent burning-activity record for Pakistan,
        from November 2000 to the latest available day. This page explains how, and reports the validation results exactly as computed.
      </p>

      <div className="notice" style={{ margin: "14px 0" }}>
        <b>Limitations you should know before using the results</b>
        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
          <li>VIIRS S-NPP is the chosen <i>reference scale</i>, not ground truth. Validation measures agreement between sensors, not wildfire-detection accuracy.</li>
          <li>The model-selection rule (calibrated totals within 5% in training cross-validation) was added after the team had seen held-out test results, so the test years are not fully independent of that choice. All candidate models are reported below.</li>
          <li>District-level estimates are much less reliable than country or province estimates (see reliability ratings). Districts with too little history show “insufficient data”.</li>
          <li>The Terra-only period (Nov 2000 – Jul 2002) has the weakest support: its link is 17% low on the 2022–2025 test years, partly because Terra's overpass time has drifted since 2022; the early years themselves cannot be tested against VIIRS.</li>
          <li>The calibration was fitted in Pakistan and does not transfer automatically: leaving out a province changes its error substantially (Punjab +52%). It is never applied outside Pakistan.</li>
          <li>Near-real-time (NRT) observations after the last standard-quality date are provisional and carry no detection type.</li>
          <li>No detections does not mean no fire: clouds, overpass timing and detection limits all matter. FIRMS-listed missing-data days are marked; pixel-level cloud cover is not available.</li>
          <li>A hotspot is a thermal anomaly, not a confirmed wildfire. Agricultural burning is vegetation burning and is included.</li>
        </ul>
      </div>

      <h3>Satellite timeline</h3>
      <div className="timeline">
        {m?.platforms?.filter((p: any) => p.processing === "SP").map((p: any) => (
          <div key={p.platform} style={{ display: "contents" }}>
            <div className="muted">{p.label}</div>
            <div className="num">{p.first} → {p.last} (standard), {p.detections.toLocaleString()} detections in Pakistan</div>
          </div>
        ))}
      </div>
      <h3>Which platform carries the record</h3>
      <table className="t" style={{ maxWidth: 760 }}>
        <thead><tr><th>Period</th><th>Carrier</th><th>Status</th></tr></thead>
        <tbody>
          {m?.carrier_periods?.map((c: any) => (
            <tr key={c.from}><td className="num">{c.from} – {c.to}</td><td>{c.carrier}</td>
              <td>{c.method === "reference_observed" ? <span className="pill good">observed reference</span> : <span className="pill accent">calibrated / reconstructed</span>}</td></tr>
          ))}
        </tbody>
      </table>

      <h3>Pipeline</h3>
      <ol>
        <li><b>Raw data, unchanged.</b> FIRMS country archive files (MODIS C6.1 2000–2025, VIIRS S-NPP 2012–2025, NOAA-20 2018–2025) and Area API files (NOAA-21 standard, 2026 standard, near-real-time gap). Each file is checksummed in a manifest.</li>
        <li><b>Normalization.</b> One schema for all sensors, keeping the original confidence, both brightness channels, scan/track, version, source file and row. UTC timestamps and local solar time (UTC + longitude/15). Clipped to Pakistan's provinces.</li>
        <li><b>Default filter.</b> FIRMS type 0 (presumed vegetation fire) or unclassified NRT; nominal or high confidence using each sensor's own scale (MODIS: &lt;30 low, 30–79 nominal, ≥80 high; VIIRS: delivered classes). Filtered detections stay in the data.</li>
        <li><b>Common grid.</b> Every detection is assigned to a 1 km cell of an equal-area grid (EPSG:6933). For each platform and day, an active cell counts once, however many pixels fall in it. This removes much of the “one MODIS pixel = several VIIRS pixels” effect, but not differences in sensitivity or overpass time.</li>
        <li><b>Calibration on 8-day windows.</b> For each province and 8-day window, a platform's active cell-days are mapped to S-NPP's. Candidate models from simple ratios to a month-specific log-linear model are compared by cross-validation over blocks of training years; test years are scored once.</li>
        <li><b>Harmonized record.</b> Provinces get the fitted model; the country is the sum of provinces; districts receive their province's estimate in proportion to their own observations. Raw platform counts are never added together.</li>
        <li><b>Activity index (0–100).</b> Percentile of this area's 8-day harmonized activity among its periods with detections; 0 means the carrier platform recorded nothing in the window.</li>
        <li><b>Anomalies.</b> Robust z = (x − median) / (1.4826 × MAD) against the same day of year ±7 days in all other years (minimum 5 years; rank-based when MAD is zero; at least 5 cell-days needed to be flagged).</li>
        <li><b>Critical windows.</b> Weeks elevated (above the 75th-percentile week) in at least half of the complete years.</li>
      </ol>

      <h2>Validation results</h2>
      {!v && <div className="skeleton" style={{ height: 200 }} />}
      {v && (
        <>
          <h3>Calibration links, held-out years</h3>
          <table className="t">
            <thead><tr><th>Link</th><th>Train</th><th>Test</th><th>Model</th><th className="r">Bias before</th><th className="r">Bias after</th><th className="r">Spearman</th><th className="r">80% interval coverage</th></tr></thead>
            <tbody>
              {Object.entries(v.links).map(([k, l]: any) => (
                <tr key={k}><td>{LINK_LABEL[k] || k}</td><td className="num">{l.train_period?.join(" – ")}</td><td className="num">{l.test_period?.join(" – ")}</td>
                  <td className="mono">{l.chosen_model}</td><td className="r">{fmt(l.uncalibrated_total_bias_pct, 1)}%</td><td className="r">{fmt(l.test_total_bias_pct, 1)}%</td>
                  <td className="r">{fmt(l.test_spearman, 3)}</td><td className="r">{fmt(l.interval_coverage_pct, 1)}%</td></tr>
              ))}
            </tbody>
          </table>

          <h3>Do added satellites inflate the record?</h3>
          <p className="muted">Mean annual activity after a platform was added divided by the mean before. The control is a platform present on both sides, so it shows real change in burning.</p>
          <table className="t">
            <thead><tr><th>Transition</th><th>Years</th><th className="r">Control</th><th className="r">Naive union</th><th className="r">Harmonized</th><th className="r">Harmonized excess</th></tr></thead>
            <tbody>
              {Object.entries(v.transitions).filter(([k]) => k !== "annual_cell_days").map(([k, t]: any) => (
                <tr key={k}><td>{k}</td><td className="num">{t.before_years.join("–")} → {t.after_years.join("–")}</td>
                  <td className="r">{fmt(t.control_ratio, 2)}×</td><td className="r">{fmt(t.naive_union_ratio, 2)}× <span className="faint">(+{fmt(t.naive_union_excess_over_control_pct, 0)}%)</span></td>
                  <td className="r">{fmt(t.harmonized_ratio, 2)}×</td><td className="r">{fmt(t.harmonized_excess_over_control_pct, 0)}%</td></tr>
              ))}
            </tbody>
          </table>
          <p className="faint">The 2012 harmonized ratio is not an independent test, because the MODIS link was fitted on 2012–2021 and no VIIRS data exist before 2012. The 2002 row rests on a single Terra-only year.</p>

          <h3>Reliability by spatial scale (calibrated MODIS vs observed S-NPP, 2022–2025)</h3>
          <table className="t">
            <thead><tr><th>Scale</th><th className="r">Areas</th><th className="r">8-day Spearman</th><th className="r">8-day bias</th><th className="r">8-day interval coverage</th><th className="r">Daily Spearman</th></tr></thead>
            <tbody>
              {Object.entries(v.scales).map(([k, s]: any) => (
                <tr key={k}><td>{k === "ADM0" ? "Country" : k === "ADM1" ? "Province" : "District"}</td><td className="r">{s.aois}</td>
                  <td className="r">{fmt(s.eight_day.spearman, 3)}</td><td className="r">{fmt(s.eight_day.total_bias_pct, 1)}%</td>
                  <td className="r">{fmt(s.eight_day.interval_coverage_pct, 1)}%</td><td className="r">{fmt(s.daily.spearman, 3)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="faint">Daily agreement is weak below country level, which is why the calendar shows 8-day values. Reliability ratings per area:{" "}
            {Object.entries(v.reliability_counts).map(([k, n]: any) => `${k.split("/")[0]} ${RATING_LABEL[k.split("/")[1]]}: ${n}`).join(" · ")}.
            Rating rule: Spearman ≥ 0.8 moderate (high for provinces with ≥ 60 active windows), 0.6–0.8 low, below 0.6 very low.</p>

          <h3>Geographic holdout (MODIS → S-NPP)</h3>
          <table className="t">
            <thead><tr><th>Province left out of fitting</th><th className="r">Mean reference</th><th className="r">Total bias</th><th className="r">Spearman</th></tr></thead>
            <tbody>
              {Object.entries(v.geographic).map(([k, g]: any) => (
                <tr key={k}><td>{k}</td><td className="r">{fmt(g.mean_ref, 1)}</td><td className="r">{fmt(g.total_bias_pct, 1)}%</td><td className="r">{fmt(g.spearman, 3)}</td></tr>
              ))}
            </tbody>
          </table>

          <h3>Sensitivity of the MODIS → S-NPP link</h3>
          <table className="t">
            <thead><tr><th>Variant</th><th className="r">S-NPP per MODIS cell</th><th className="r">Test bias</th><th className="r">Spearman</th></tr></thead>
            <tbody>
              {Object.entries(v.sensitivity).map(([k, s]: any) => (
                <tr key={k}><td>{k}</td><td className="r">{fmt(s.train_ratio_snpp_per_modis, 2)}</td><td className="r">{fmt(s.test_total_bias_pct, 1)}%</td><td className="r">{fmt(s.test_spearman, 3)}</td></tr>
              ))}
            </tbody>
          </table>

          <h3>Cross-sensor correspondence (Aqua vs S-NPP, daytime, same day)</h3>
          <table className="t">
            <thead><tr><th>Period</th><th className="r">Aqua cells with S-NPP within 1 cell</th><th className="r">S-NPP cells with Aqua within 1 cell</th></tr></thead>
            <tbody>
              {Object.entries(v.correspondence).map(([k, c]: any) => (
                <tr key={k}><td>{k}</td><td className="r">{fmt(c.aqua_cells_with_snpp_within_1_cell_pct, 1)}%</td><td className="r">{fmt(c.snpp_cells_with_aqua_within_1_cell_pct, 1)}%</td></tr>
              ))}
            </tbody>
          </table>
          <p className="faint">Nearly every Aqua active cell has an S-NPP detection nearby on the same day, but S-NPP sees many small fires Aqua misses. A same-day match is evidence of correspondence, not proof of the same fire.</p>

          <h3>All candidate models</h3>
          {Object.entries(v.candidates).map(([k, c]: any) => (
            <details key={k} style={{ marginBottom: 6 }}>
              <summary>{LINK_LABEL[k] || k} — chosen: <span className="mono">{c.chosen}</span></summary>
              <table className="t">
                <thead><tr><th>Model</th><th className="r">CV log-MAE</th><th className="r">CV bias</th><th className="r">Test log-MAE</th><th className="r">Test bias</th><th className="r">Test Spearman</th></tr></thead>
                <tbody>
                  {Object.keys(c.cv).map((mm) => (
                    <tr key={mm}><td className="mono">{mm}{mm === c.chosen ? " ✓" : ""}</td><td className="r">{fmt(c.cv[mm].log_mae, 3)}</td><td className="r">{fmt(c.cv[mm].total_bias_pct, 1)}%</td>
                      <td className="r">{fmt(c.test[mm].log_mae, 3)}</td><td className="r">{fmt(c.test[mm].total_bias_pct, 1)}%</td><td className="r">{fmt(c.test[mm].spearman, 3)}</td></tr>
                  ))}
                </tbody>
              </table>
            </details>
          ))}
        </>
      )}

      <h2>Data sources</h2>
      <ul>
        {m?.sources?.map((s: any) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a></li>)}
        <li>Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors. True-colour imagery: NASA GIBS / Worldview.</li>
      </ul>
      <p className="faint">Calibration version <span className="mono">{m?.calibration_version}</span> · validation generated {v?.generated?.slice(0, 16)}.</p>
    </div>
  );
}
