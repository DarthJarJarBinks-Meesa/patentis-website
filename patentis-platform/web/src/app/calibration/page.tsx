'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type Region = { id: string; cpc_subclass: string };

export default function CalibrationPage() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [regionId, setRegionId] = useState('');
  const [scores, setScores] = useState({ cr: 4, b: 4, ci: 4, wq: 4 });
  const [summary, setSummary] = useState<{ ratings_count: number } | null>(null);

  useEffect(() => {
    api<Region[]>('/api/landscape/regions?vertical=medtech').then((r) => {
      setRegions(r);
      if (r[0]) setRegionId(r[0].id);
    });
    api<{ ratings_count: number; target: number }>('/api/calibration/summary').then(setSummary);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await api('/api/calibration/rate', {
      method: 'POST',
      body: JSON.stringify({
        region_id: regionId,
        clinical_relevance: scores.cr,
        buildability: scores.b,
        commercial_interest: scores.ci,
        whitespace_quality: scores.wq,
      }),
    });
    const s = await api<{ ratings_count: number }>('/api/calibration/summary');
    setSummary(s);
    alert('Calibration saved');
  }

  return (
    <>
      <h1>Expert calibration</h1>
      <p className="muted">Ratings feed RF labels and future DPO loops.</p>
      {summary && (
        <div className="card">
          Ratings logged: {summary.ratings_count} / target 100
        </div>
      )}
      <form className="card" onSubmit={submit}>
        <label className="muted">Region</label>
        <select value={regionId} onChange={(e) => setRegionId(e.target.value)} style={{ width: '100%', marginBottom: 12 }}>
          {regions.map((r) => (
            <option key={r.id} value={r.id}>
              {r.cpc_subclass}
            </option>
          ))}
        </select>
        {(['cr', 'b', 'ci', 'wq'] as const).map((k) => (
          <div key={k} style={{ marginBottom: 8 }}>
            <label className="muted">{k}</label>
            <input
              type="range"
              min={1}
              max={5}
              value={scores[k]}
              onChange={(e) => setScores({ ...scores, [k]: Number(e.target.value) })}
            />
            <span>{scores[k]}</span>
          </div>
        ))}
        <button type="submit">Submit rating</button>
      </form>
    </>
  );
}
