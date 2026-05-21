'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('demo@patentis.dev');
  const [password, setPassword] = useState('patentis-demo');
  const [orgName, setOrgName] = useState('Demo Lab');
  const [mode, setMode] = useState<'login' | 'register'>('register');
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body =
        mode === 'login'
          ? { email, password }
          : { email, password, org_name: orgName };
      const data = await api<{ access_token: string }>(path, {
        method: 'POST',
        body: JSON.stringify(body),
        auth: false,
      });
      setToken(data.access_token);
      router.push('/landscape');
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <>
      <h1>{mode === 'login' ? 'Sign in' : 'Create account'}</h1>
      <form onSubmit={submit} className="card" style={{ maxWidth: 420 }}>
        <label className="muted">Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: '100%', marginBottom: 12 }} />
        <label className="muted">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ width: '100%', marginBottom: 12 }}
        />
        {mode === 'register' && (
          <>
            <label className="muted">Organization</label>
            <input
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              style={{ width: '100%', marginBottom: 12 }}
            />
          </>
        )}
        {error && <p style={{ color: '#f66' }}>{error}</p>}
        <button type="submit">{mode === 'login' ? 'Login' : 'Register'}</button>
        <p className="muted" style={{ marginTop: 12 }}>
          <button
            type="button"
            style={{ background: 'transparent', color: 'var(--accent)', padding: 0 }}
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          >
            Switch to {mode === 'login' ? 'register' : 'login'}
          </button>
        </p>
      </form>
    </>
  );
}
