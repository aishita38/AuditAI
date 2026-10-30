import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Play, KeyRound, FilePlus, ChevronRight } from 'lucide-react';
import { policiesApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import PolicyEvidence from '../components/PolicyEvidence';

export default function PolicyChecks() {
  const { user } = useAuth();
  const admin = user?.roles?.includes('admin');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [reviewers, setReviewers] = useState([]);
  const [reviewer, setReviewer] = useState('');
  const [limit, setLimit] = useState('');
  const [claim, setClaim] = useState('');
  const [evidence, setEvidence] = useState('{}');

  async function load() {
    try {
      setData((await policiesApi.list({ offset, limit: 50 })).data);
      setError('');
      if (admin) setReviewers((await policiesApi.reviewers()).data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not load policy checks.');
    }
  }

  useEffect(() => {
    load();
  }, [offset]);

  async function act(fn) {
    setBusy(true);
    setError('');
    try {
      await fn();
      await load();
    } catch (e) {
      setError(
        typeof e.response?.data?.detail === 'string'
          ? e.response.data.detail
          : 'Action failed. Check the input values.'
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold">Company Policy Checks</h2>
        {admin && (
          <button
            disabled={busy}
            className="btn btn-primary text-xs flex items-center gap-1.5"
            onClick={() => act(() => policiesApi.run())}
          >
            <Play size={14} />
            <span>{busy ? 'Evaluating…' : 'Run Company Policy Checks'}</span>
          </button>
        )}
      </div>

      <p className="text-secondary text-xs mb-4">
        Rule-based policy verification running alongside ML anomaly models. Violations open review cases directly without skewing statistical scores.
      </p>

      {error && <p role="alert" className="glass-card mb-4 text-xs text-status-danger">{error}</p>}

      {admin && (
        <div className="grid-cols-2 gap-4 mb-5">
          <details className="glass-card p-4">
            <summary className="text-xs font-semibold cursor-pointer flex items-center gap-1.5 text-primary">
              <KeyRound size={14} className="text-accent-primary" />
              <span>Configure Checker Authority Limits (INR)</span>
            </summary>
            <p className="text-[11px] text-muted mt-2 mb-3">
              Define the maximum single-claim approval authority threshold for each designated checker.
            </p>
            <form
              className="transfer-controls"
              onSubmit={(e) => {
                e.preventDefault();
                act(() => policiesApi.authority(reviewer, limit));
              }}
            >
              <label>
                Checker
                <select required value={reviewer} onChange={(e) => setReviewer(e.target.value)}>
                  <option value="">Select checker</option>
                  {reviewers.map((r) => (
                    <option value={r.id} key={r.id}>
                      {r.email} · limit: ₹{Number(r.limit).toLocaleString()}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Approval limit (₹)
                <input
                  required
                  type="number"
                  min="0"
                  step="0.01"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                />
              </label>
              <button className="btn btn-secondary text-xs" disabled={busy}>
                Save Authority
              </button>
            </form>
          </details>

          <details className="glass-card p-4">
            <summary className="text-xs font-semibold cursor-pointer flex items-center gap-1.5 text-primary">
              <FilePlus size={14} className="text-accent-primary" />
              <span>Attach Claim Policy Evidence</span>
            </summary>
            <p className="text-[11px] text-muted mt-2 mb-3">
              Add invoice series, event timestamps, or exception notes to a specific claim.
            </p>
            <form
              className="transfer-review-form"
              onSubmit={(e) => {
                e.preventDefault();
                act(() => policiesApi.inputs(claim, JSON.parse(evidence)));
              }}
            >
              <label>
                Claim ID
                <input required value={claim} onChange={(e) => setClaim(e.target.value)} placeholder="CLM-00001" />
              </label>
              <label>
                Evidence JSON
                <textarea required value={evidence} onChange={(e) => setEvidence(e.target.value)} />
              </label>
              <button className="btn btn-secondary text-xs" disabled={busy}>
                Save Evidence
              </button>
            </form>
          </details>
        </div>
      )}

      {data && (
        <>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs text-muted">
              {data.total} claims evaluated · showing {data.total ? offset + 1 : 0}–
              {Math.min(offset + 50, data.total)}
            </span>
            <details className="text-xs">
              <summary className="text-xs text-muted cursor-pointer hover:text-secondary">
                View policy parameters
              </summary>
              <pre className="mono-pre p-2 mt-1 rounded text-[11px]" style={{ whiteSpace: 'pre-wrap', maxHeight: '140px' }}>
                {JSON.stringify(data.config, null, 2)}
              </pre>
            </details>
          </div>

          <div className="space-y-3 mb-5">
            {data.items.map((p) => (
              <details className="glass-card p-4" key={p.claim_id}>
                <summary className="cursor-pointer flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-primary">{p.claim_id}</span>
                    <span
                      className={`badge text-[10px] uppercase ${
                        p.requires_review ? 'badge-amber' : 'badge-green'
                      }`}
                    >
                      {p.requires_review ? 'Review Required' : 'Passed'}
                    </span>
                  </div>
                  <Link
                    to={`/claims/${encodeURIComponent(p.claim_id)}`}
                    className="text-xs text-accent-primary hover:underline font-medium"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Open claim →
                  </Link>
                </summary>
                <div className="mt-3 pt-3 border-t border-glass">
                  <PolicyEvidence result={p} />
                </div>
              </details>
            ))}
          </div>

          <div className="transfer-controls">
            <button
              className="btn btn-secondary text-xs"
              disabled={offset === 0 || busy}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous
            </button>
            <button
              className="btn btn-secondary text-xs"
              disabled={offset + 50 >= data.total || busy}
              onClick={() => setOffset(offset + 50)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
