import { PLATFORM_COLOR, PLATFORM_LABEL, fmt, niceDate } from "../api";

export function StoryList({ stories, onOpen }: { stories: any[] | null; onOpen: (s: any) => void }) {
  return (
    <div className="page">
      <h2 style={{ margin: "6px 0 4px" }}>Explore fire stories</h2>
      <div className="muted" style={{ marginBottom: 16 }}>
        Guided case studies on the live application. Every number is computed from NASA FIRMS observations; narrative context is marked as such.
      </div>
      {!stories && <div className="skeleton" style={{ height: 200 }} />}
      <div className="grid two">
        {stories?.map((s) => (
          <div key={s.id} className="card story-card" onClick={() => onOpen(s)}>
            <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".07em" }}>{s.subtitle}</div>
            <h3 style={{ fontSize: 17, margin: "4px 0 8px" }}>{s.title}</h3>
            <p className="muted" style={{ margin: "0 0 10px" }}>{s.context[0]}</p>
            {s.stats && (
              <div className="row" style={{ gap: 14 }}>
                <span className="num"><b>{Object.values(s.stats.detections_by_platform).reduce((a: number, b: any) => a + b, 0).toLocaleString()}</b> <span className="muted">detections in the story period</span></span>
                {s.stats.peak_index !== null && <span><b>{s.stats.peak_index}</b> <span className="muted">peak index</span></span>}
              </div>
            )}
            <div style={{ marginTop: 12 }}><span className="btn primary">Open story</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StoryBanner({ story, step, setStep, onClose }: { story: any; step: number; setStep: (i: number) => void; onClose: () => void }) {
  const st = story.stats;
  const total = st ? Object.values(st.detections_by_platform).reduce((a: number, b: any) => a + b, 0) : 0;
  const s = story.steps[step];
  return (
    <div className="story-banner">
      <div className="row between">
        <div>
          <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".07em" }}>Story · {story.subtitle}</div>
          <h2 style={{ margin: "2px 0 0", fontSize: 18 }}>{story.title}</h2>
        </div>
        <button className="btn small" onClick={onClose}>Close story</button>
      </div>
      <div className="grid two" style={{ marginTop: 10, gap: 18 }}>
        <div>
          {story.context.map((c: string, i: number) => <p key={i} style={{ margin: "0 0 6px", color: "#d6dee8" }}>{c}</p>)}
          <div className="faint" style={{ fontSize: 11.5 }}>{story.context_note}</div>
          {story.sources?.length > 0 && (
            <ol className="faint" style={{ fontSize: 11.5, margin: "4px 0 0", paddingLeft: 18 }} aria-label="Sources">
              {story.sources.map((src: { label: string; url: string }) => (
                <li key={src.url}><a href={src.url} target="_blank" rel="noopener noreferrer">{src.label}</a></li>
              ))}
            </ol>
          )}
          {story.boundary_note && <div className="faint" style={{ fontSize: 11.5, marginTop: 4 }}>{story.boundary_note}</div>}
        </div>
        <div>
          <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 4 }}>
            From FIRMS, {niceDate(story.start)} – {niceDate(story.end)}
          </div>
          {st ? (
            <div className="kv" style={{ fontSize: 12.5 }}>
              <div>Detections</div>
              <div>{total.toLocaleString()} ({Object.entries(st.detections_by_platform).map(([p, n]: any) =>
                <span key={p} style={{ marginRight: 8 }}><span className="dot" style={{ background: PLATFORM_COLOR[p] }} /> {PLATFORM_LABEL[p]} {n}</span>)})</div>
              <div>First / last</div><div>{st.first_detection ? `${niceDate(st.first_detection)} – ${niceDate(st.last_detection)}` : "—"}</div>
              <div>Peak 8-day activity</div><div>{fmt(st.peak_h_roll, 1)} cells/day on {st.peak_date ? niceDate(st.peak_date) : "—"} (index {st.peak_index ?? "—"})</div>
              <div>Max FRP</div><div>{fmt(st.max_frp, 1)} MW</div>
              <div>Anomaly days</div><div>{st.anomaly_days.highly_unusual || 0} highly unusual · {st.anomaly_days.elevated || 0} elevated{st.max_z !== null ? ` · max z ${fmt(st.max_z, 1)}` : ""}</div>
            </div>
          ) : <div className="muted">No statistics available.</div>}
        </div>
      </div>
      <div className="steps">
        {story.steps.map((x: any, i: number) => (
          <div key={i} className={`step ${i === step ? "on" : ""}`} onClick={() => setStep(i)}>{i + 1}. {x.title}</div>
        ))}
      </div>
      <div style={{ marginTop: 8, color: "#d6dee8" }}>{s.text}</div>
    </div>
  );
}
