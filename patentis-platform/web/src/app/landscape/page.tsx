'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type Region = {
  id: string;
  cpc_subclass: string;
  composite_whitespace_score: number | null;
  scarcity_score: number;
  momentum_score: number;
};

export default function LandscapePage() {
  const [rows, setRows] = useState<Region[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api<Region[]>('/api/landscape/regions?vertical=medtech')
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <>
      <h1>Landscape</h1>
      <p className="muted">Ranked technology regions (CPC × vertical). Train models after seeding.</p>
      {error && <p style={{ color: '#f66' }}>{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>CPC</th>
              <th>Composite</th>
              <th>Scarcity</th>
              <th>Momentum</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.cpc_subclass}</td>
                <td>{r.composite_whitespace_score?.toFixed?.(3) ?? '—'}</td>
                <td>{r.scarcity_score.toFixed(2)}</td>
                <td>{r.momentum_score.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
