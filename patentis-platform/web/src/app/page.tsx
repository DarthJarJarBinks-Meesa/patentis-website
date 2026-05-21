export default function Home() {
  return (
    <>
      <h1>Innovation GPS for R&D</h1>
      <p className="muted">
        Patentis maps patent whitespace, validates scientific feasibility, and generates
        opportunity briefs — decision support for where to innovate next.
      </p>
      <div className="card">
        <h3>Modules</h3>
        <ul>
          <li>
            <strong>Landscape</strong> — ranked CPC regions (scarcity, concentration, momentum)
          </li>
          <li>
            <strong>Corpus</strong> — project vault + hybrid search
          </li>
          <li>
            <strong>Calibration</strong> — expert labels for model training
          </li>
          <li>
            <strong>Agents</strong> — WhitespaceScan → Feasibility → InventionBrief → RiskSketch
          </li>
        </ul>
      </div>
    </>
  );
}
