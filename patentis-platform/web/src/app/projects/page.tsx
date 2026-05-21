'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type Project = { id: string; name: string };

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('My whitespace study');
  const [note, setNote] = useState('Paste notes or claims excerpts here for hybrid search.');
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState('');

  async function refresh() {
    const list = await api<Project[]>('/api/projects');
    setProjects(list);
    if (!selected && list[0]) setSelected(list[0].id);
  }

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, []);

  async function create() {
    await api('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ name, vertical: 'medtech' }),
    });
    await refresh();
  }

  async function addCorpus() {
    if (!selected) return;
    await api(`/api/projects/${selected}/corpus`, {
      method: 'POST',
      body: JSON.stringify({ title: 'Lab note', body: note }),
    });
    alert('Corpus chunk added');
  }

  return (
    <>
      <h1>Corpus (Vault)</h1>
      <p className="muted">Org-scoped projects with hybrid BM25 + embedding retrieval.</p>
      {error && <p style={{ color: '#f66' }}>{error}</p>}
      <div className="card">
        <label className="muted">New project name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
        <button type="button" onClick={create}>
          Create project
        </button>
      </div>
      <div className="card">
        <label className="muted">Active project</label>
        <select value={selected ?? ''} onChange={(e) => setSelected(e.target.value)} style={{ width: '100%', marginBottom: 8 }}>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={6} style={{ width: '100%' }} />
        <button type="button" onClick={addCorpus} style={{ marginTop: 8 }}>
          Add to corpus
        </button>
      </div>
    </>
  );
}
