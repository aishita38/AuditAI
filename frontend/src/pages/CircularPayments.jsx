import React, { useEffect, useState } from 'react';
import { transfersApi, reviewQueueApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import './CircularPayments.css';
import CycleReviews from '../components/CycleReviews';

export default function CircularPayments() {
  const { user } = useAuth();
  const admin = user?.roles?.includes('admin');
  const [data, setData] = useState(null);
  const [days, setDays] = useState(7);
  const [hops, setHops] = useState(4);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
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
  return <section className="circular-payments">
    <h1 className="text-2xl font-bold mb-4">Circular payment screening</h1>
    <p className="text-secondary mb-6">Follow transfers that return to the starting account. These are review signals, not fraud findings or ML scores. Transfer records are separate from expense claims.</p>
    <section className="glass-card mb-6">
      <h2 className="text-lg font-semibold mb-2">Transfer ledger</h2>
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
      {data.cycles.map(cycle => <article className="glass-card mb-6" key={cycle.transaction_ids.join('|')}>
        <h2 className="text-lg font-semibold mb-2">Potential circular payment · review required</h2>
        <ol className="transfer-path" aria-label="Account flow">{cycle.accounts.map((account, index) => <li key={`${index}-${account}`}>{account}{index < cycle.accounts.length - 1 && <span aria-hidden="true"> → </span>}</li>)}</ol>
        <p className="text-secondary mb-4">{cycle.currency} {cycle.initial_amount} initially sent · {cycle.returned_amount} returned ({(cycle.return_ratio * 100).toFixed(1)}%) · {cycle.elapsed_hours} hours elapsed</p>
        <p className="text-secondary mb-4">{cycle.reason}</p>
        {cycle.case_id ? <p>Review case exists · {cycle.case_status.replaceAll('_', ' ')} · open the shared review queue</p> : <button className="btn btn-primary mb-4" disabled={busy} onClick={() => send(cycle)}>Send to review</button>}
        <div className="table-container"><table><thead><tr><th>Transfer ID</th><th>Sender</th><th>Receiver</th><th>Amount</th><th>Timestamp (UTC)</th></tr></thead>
          <tbody>{cycle.transfers.map(t => <tr key={t.transaction_id}><td>{t.transaction_id}</td><td>{t.sender_account}</td><td>{t.receiver_account}</td><td>{t.currency} {t.amount}</td><td>{t.timestamp}</td></tr>)}</tbody>
        </table></div>
      </article>)}
    </>}
    <CycleReviews revision={revision} onCaseChanged={() => scan()} />
    <details className="glass-card mt-6"><summary>Limitations</summary><p>Results are review signals, not proof of fraud. The examples are synthetic. Legitimate refunds or treasury movements can form cycles. This screen cannot prove that the same funds circulated, reconstruct split/merged funds, or follow cross-currency flows. Strict timestamp ordering excludes tied times. Search and time limits can miss patterns. No ML score or claim approval is changed.</p></details>
  </section>;
}
