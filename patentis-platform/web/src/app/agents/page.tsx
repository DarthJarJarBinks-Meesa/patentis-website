'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type Project = { id: string; name: string };

export default function AgentsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [log, setLog] = useState('');

  useEffect(() => {
    api<Project[]>('/api/projects').then((p) => {
      setProjects(p);
      if (p[0]) setProjectId(p[0].id);
    });
  }, []);

  async function seed() {
    await api('/api/agents/ingest/seed', { method: 'POST' });
    setLog('Seed complete');
  }

  async function pipeline() {
    const out = await api<unknown>(`/api/agents/pipeline/${projectId}?idea_summary=implant+sensor`, {
      method: 'POST',
    });
    setLog(JSON.stringify(out, null, 2));
  }

  return (
    <>
      <h1>Workflow agents</h1>
      <p className="muted">
        WhitespaceScan → FeasibilityPass → InventionBrief → RiskSketch. Requires backend DB +
        trained models.
      </p>
      <div className="card">
        <button type="button" onClick={seed} style={{ marginRight: 8 }}>
          Seed demo data
        </button>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button type="button" onClick={pipeline} style={{ marginLeft: 8 }}>
          Run pipeline
        </button>
      </div>
      <pre className="card" style={{ whiteSpace: 'pre-wrap' }}>
        {log || 'Agent output appears here.'}
      </pre>
    </>
  );
}
