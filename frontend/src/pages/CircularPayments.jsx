import React, { useEffect, useState } from 'react';
import { transfersApi, reviewQueueApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useAuditProfile } from '../context/AuditProfileContext';
import { Info, Zap } from 'lucide-react';
import './CircularPayments.css';
import CycleReviews from '../components/CycleReviews';

export default function CircularPayments() {
  const { user } = useAuth();
  const { profileId, profile } = useAuditProfile();
  const admin = user?.roles?.includes('admin');
  const [data, setData] = useState(null);
  const [days, setDays] = useState(7);
  const [hops, setHops] = useState(4);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
  const [showExplanation, setShowExplanation] = useState(true);

  async function send(cycle) {
    setBusy(true); setError('');
    try {
      const result = (await transfersApi.sendToReview({ transaction_ids: cycle.transaction_ids, window_days: data.window_days, max_hops: data.max_hops })).data;
      await reviewQueueApi.sync();
      setNotice(`Cycle case #${result.id} was sent to the shared review queue.`);
      setRevision(value => value + 1); await scan();
    } catch (e) { setError(e.response?.data?.detail || 'Could not send this cycle to review.'); }
    finally { setBusy(false); }
  }

  async function scan(windowDays = days, maxHops = hops) {
    setBusy(true); setError(''); setData(null);
    try { setData((await transfersApi.cycles({ window_days: windowDays, max_hops: maxHops })).data); }
    catch (e) { setError(e.response?.data?.detail || 'Could not screen transfers. Please try again.'); }
    finally { setBusy(false); }
  }

  useEffect(() => { scan(7, 4); }, []);

  async function upload(event) {
    event.preventDefault(); if (!file) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const form = new FormData(); form.append('file', file);
      const res = (await transfersApi.upload(form)).data;
      setNotice(`${res.imported} transfers imported; ${res.skipped} existing transfers skipped.`);
      await scan();
    } catch (e) { setError(e.response?.data?.detail || 'Import failed. Please try again.'); }
    finally { setBusy(false); }
  }

  if (profile.hasCircularPayments === false) {
    return (
      <section className="circular-payments">
        <div className="glass-card p-6 text-center">
          <h2 className="text-lg font-bold mb-2">Feature Not Applicable to Corporate Enterprise</h2>
          <p className="text-secondary text-sm mb-4">
            Circular payment and shell loop screening is designed for Forensic &amp; Regulatory investigations and Bank AML monitoring. Corporate enterprise accounts focus on internal AP, vendor checks, and payroll anomalies.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="circular-payments">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">Circular Payment & Shell Loop Screening</h1>
        <div className="flex items-center gap-2">
          <span
            className="badge text-xs"
            style={{ background: `${profile.color}20`, color: profile.color, border: `1px solid ${profile.color}40` }}
          >
            {profile.name}
          </span>
        </div>
      </div>

      <p className="text-secondary mb-4">
        Follow transfer loops that return funds to the starting account. These flags identify potential shell company rings, carousel fraud, and money laundering layering.
      </p>

      {/* Audit Context & Data Scope Guide */}
      <div className="glass-card mb-6" style={{ borderLeft: `4px solid ${profile.color}`, padding: '18px 20px' }}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 font-semibold text-sm">
            <Info size={18} style={{ color: profile.color }} />
            <span>Audit Context & Data Source Guide ({profile.name} View)</span>
          </div>
          <button
            type="button"
            className="text-xs text-muted hover:text-primary"
            onClick={() => setShowExplanation(!showExplanation)}
          >
            {showExplanation ? 'Hide Guide' : 'Show Guide'}
          </button>
        </div>

        {showExplanation && (
          <div className="text-xs text-secondary leading-relaxed space-y-2 mt-2">
            <div className="grid-cols-2 gap-4">
              <div>
                <strong className="text-primary block mb-1">Why is this flagged as a risk?</strong>
                <p>
                  In real-world finance, circular transfers (Account A → B → C → A) are the primary signature of <strong>Round-Tripping</strong> (faking revenue/invoicing), <strong>Carousel GST/Tax credit theft</strong>, or <strong>AML Layering</strong> (washing illicit funds through intermediary shell accounts).
                </p>
              </div>
              <div>
                <strong className="text-primary block mb-1">Investigation Data Source</strong>
                {profileId === 'banking' ? (
                  <p>
                    <strong>Bank & AML Compliance Context:</strong> Directly fed by <strong>core banking inter-account transaction ledgers</strong> and wire monitoring networks to detect money laundering and smurfing.
                  </p>
                ) : (
                  <p>
                    <strong>Forensic Investigation Context:</strong> Data is acquired via <strong>court subpoenas, tax authority discovery (GST/ED/IRS)</strong>, or insolvency proceedings to expose hidden shell company rings.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <section className="glass-card mb-6">
        <h2 className="text-lg font-semibold mb-2">Transfer Ledger Feeds</h2>
        <p className="text-secondary">CSV columns: transaction_id, sender_account, receiver_account, amount, currency, timestamp; optional claim_id links a payment to an existing expense claim. Use positive amounts and timezone-aware timestamps. Same-currency paths only; maximum 5,000 transfers.</p>
        <p className="mb-4"><a href="/sample-transfers.csv" download className="text-accent-primary">Download synthetic examples</a> — two expected cycles, plus transfers that should not form a cycle. Sample accounts are fictional.</p>
        {admin ? <form onSubmit={upload} className="transfer-controls">
          <label>Transfer CSV<input type="file" accept=".csv,text/csv" disabled={busy} onChange={e => setFile(e.target.files?.[0] || null)} /></label>
          <button className="btn btn-primary" disabled={busy || !file}>Import and screen</button>
        </form> : <p className="text-secondary">An administrator can import transfer records. Makers and checkers can inspect results.</p>}
      </section>

      <form className="glass-card transfer-controls mb-6" onSubmit={e => { e.preventDefault(); setNotice(''); scan(); }}>
        <label>Maximum cycle window (days)<input type="number" min="1" max="30" required value={days} disabled={busy} onChange={e => setDays(e.target.value)} /></label>
        <label>Maximum transfers in a cycle<input type="number" min="2" max="6" required value={hops} disabled={busy} onChange={e => setHops(e.target.value)} /></label>
        <button className="btn btn-secondary" disabled={busy}>Run screening</button>
      </form>

      {error && <p role="alert" className="glass-card mb-4">{error}</p>}
      {notice && <p role="status" className="mb-4">{notice}</p>}
      {busy && <p role="status">Screening transfers…</p>}

      {data && <>
        <p className="mb-4">{data.transfer_count} transfers · {data.cycles.length} potential cycles · window {data.window_days} days · up to {data.max_hops} transfers per cycle</p>
        {data.search_limited && <p role="alert" className="glass-card mb-4">Screening reached its search or result limit. Results are incomplete; use a smaller dataset or shorter window.</p>}
        {data.excluded_self_transfers > 0 && <p>{data.excluded_self_transfers} self-transfers excluded from cycle starts.</p>}
        {data.cycles.length === 0 && <p className="glass-card">{data.transfer_count === 0 ? 'No transfer records imported yet. Download the sample CSV and ask an administrator to import it here.' : 'No cycles found within these settings. This does not establish that all transfers are safe.'}</p>}
        {data.cycles.map(cycle => {
          const isRapid = cycle.elapsed_hours <= 24;
          const feeRetained = Math.max(0, cycle.initial_amount - cycle.returned_amount);
          const feePercent = (100 - (cycle.return_ratio * 100)).toFixed(1);
          return (
            <article className="glass-card mb-6" key={cycle.transaction_ids.join('|')}>
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-lg font-semibold">Potential circular payment · review required</h2>
                <div className="flex items-center gap-2">
                  {isRapid && (
                    <span className="badge badge-amber text-xs flex items-center gap-1" title="Completed within 24 hours">
                      <Zap size={12} /> Rapid Layering ({cycle.elapsed_hours}h)
                    </span>
                  )}
                  <span className="badge badge-red text-xs">Round-Trip Cycle</span>
                </div>
              </div>

              <ol className="transfer-path" aria-label="Account flow">{cycle.accounts.map((account, index) => <li key={`${index}-${account}`}>{account}{index < cycle.accounts.length - 1 && <span aria-hidden="true"> → </span>}</li>)}</ol>
              <div className="flex flex-wrap items-center gap-4 text-sm text-secondary mb-3">
                <span><strong>{cycle.currency} {cycle.initial_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong> sent</span>
                <span>•</span>
                <span><strong>{cycle.returned_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong> returned ({(cycle.return_ratio * 100).toFixed(1)}%)</span>
                <span>•</span>
                <span><strong>{cycle.elapsed_hours}h</strong> elapsed</span>
                {feeRetained > 0 && (
                  <>
                    <span>•</span>
                    <span className="text-xs text-amber-400">Intermediary retained: {cycle.currency} {feeRetained.toLocaleString(undefined, { minimumFractionDigits: 2 })} ({feePercent}%)</span>
                  </>
                )}
              </div>
              <p className="text-secondary text-sm mb-4">{cycle.reason}</p>
              {cycle.case_id ? <p className="text-sm font-medium">Review case exists · {cycle.case_status.replaceAll('_', ' ')} · open the shared review queue</p> : <button className="btn btn-primary mb-4" disabled={busy} onClick={() => send(cycle)}>Send to review</button>}
              <div className="table-container"><table><thead><tr><th>Transfer ID</th><th>Sender</th><th>Receiver</th><th>Amount</th><th>Timestamp (UTC)</th></tr></thead>
                <tbody>{cycle.transfers.map(t => <tr key={t.transaction_id}><td>{t.transaction_id}</td><td>{t.sender_account}</td><td>{t.receiver_account}</td><td>{t.currency} {t.amount}</td><td>{t.timestamp}</td></tr>)}</tbody>
              </table></div>
            </article>
          );
        })}
      </>}
      <CycleReviews revision={revision} onCaseChanged={() => scan()} />
      <details className="glass-card mt-6"><summary>Technical Limitations & Regulatory Scope</summary><p>Results are review signals, not proof of fraud. The examples are synthetic. Legitimate refunds, escrow returns, or corporate treasury sweeping can form cycles. This screen cannot prove that the same funds circulated, reconstruct split/merged funds, or follow cross-currency flows. Strict timestamp ordering excludes tied times. Search and time limits can miss patterns. No ML score or claim approval is changed.</p></details>
    </section>
  );
}
