import React, { useEffect, useState } from 'react';
import { Link,useNavigate } from 'react-router-dom';
import { transfersApi,reviewQueueApi } from '../api/client';

const LABELS = {
  payment_total_mismatch: 'Payment total differs from claim amount',
  payment_for_rejected_claim: 'Payment linked to a rejected claim',
  multiple_payments_for_claim: 'Multiple payments — check for duplicate settlement',
  payment_before_checker_approval: 'Payment predates checker approval',
  payment_without_checker_approval: 'Payment has no recorded checker approval',
  checker_approval_time_unavailable: 'Approved claim has no recorded checker approval time',
  currency_mismatch: 'Payment and claim currencies differ',
  claim_currency_unavailable: 'Claim currency unavailable',
  linked_claim_missing: 'Linked claim missing',
};

export default function PaymentReconciliation() {
  const navigate=useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); setError('');
    try { setData((await transfersApi.reconciliation()).data); }
    catch (e) { setError(e.response?.data?.detail || 'Could not reconcile payments.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);
  async function send(claimId) {
    setBusy(true);setError('');
    try {const item=(await reviewQueueApi.reconcile(claimId)).data;navigate(`/review-queue?case=${item.id}`);}
    catch(e){setError(e.response?.data?.detail||'Could not send finding to review.');}
    finally{setBusy(false);}
  }
  return <section>
    <h2 className="text-xl font-semibold mb-4">Payment Reconciliation</h2>
    <p className="text-secondary mb-4">Compare imported payments with linked claims and recorded checker approval events. Add an existing claim_id to each settlement transfer when importing through Circular Payments.</p>
    <button className="btn btn-secondary mb-4" onClick={load} disabled={busy}>Refresh reconciliation</button>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Checking linked payments…</p>}
    {data && <>
      <p>{data.items.length} linked claims · {data.unlinked_transfers} transfers without a claim link (not reconciled)</p>
      {data.items.length === 0 && <p className="glass-card">No claim-linked transfers yet. Existing circular-payment examples are intentionally unlinked.</p>}
      {data.items.map(item => <article className="glass-card mb-4" key={item.claim_id}>
        <h3 className="text-lg font-semibold"><Link to={`/claims/${encodeURIComponent(item.claim_id)}`}>{item.claim_id}</Link> · {item.claim_status}</h3>
        <p>Claim: {item.claim_currency || 'Currency unknown'} {item.claim_amount} · Paid: {item.paid_total ?? 'Mixed currencies; no combined total'} {item.payment_currencies?.join(', ')}</p>
        <p>Checker approval: {item.approved_at || 'No timestamp recorded'}</p>
        {item.flags.length>0 && <button className="btn btn-primary mb-4" disabled={busy} onClick={()=>send(item.claim_id)}>Send to review</button>}
        {item.flags.length ? <ul>{item.flags.map(flag => <li key={flag}>{LABELS[flag] || flag}</li>)}</ul> : <p>No reconciliation exceptions found in the available records.</p>}
        <div className="table-container"><table><thead><tr><th>Transfer ID</th><th>Amount</th><th>Paid at (UTC)</th><th>Sender → Receiver</th></tr></thead><tbody>{item.payments.map(p => <tr key={p.transaction_id}><td>{p.transaction_id}</td><td>{p.currency} {p.amount}</td><td>{p.timestamp}</td><td>{p.sender_account} → {p.receiver_account}</td></tr>)}</tbody></table></div>
      </article>)}
    </>}
    <details className="glass-card mt-6"><summary>Limitations</summary><p>These are review signals, not proof. Multiple payments may be legitimate installments. Amount comparison assumes full settlement and does not adjust for fees, withholding, refunds or exchange rates. Unlinked transfers cannot be reconciled. Missing currency or approval history is reported as unavailable, never treated as a successful check. Synthetic tests do not establish real-world detection accuracy.</p></details>
  </section>;
}
