import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { policiesApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import PolicyEvidence from '../components/PolicyEvidence';

export default function PolicyChecks() {
  const { user } = useAuth(); const admin=user?.roles?.includes('admin');
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const [offset,setOffset]=useState(0); const [reviewers,setReviewers]=useState([]); const [reviewer,setReviewer]=useState(''); const [limit,setLimit]=useState('');
  const [claim,setClaim]=useState(''); const [evidence,setEvidence]=useState('{}');
  async function load() { try { setData((await policiesApi.list({offset,limit:50})).data); setError(''); if(admin) setReviewers((await policiesApi.reviewers()).data); } catch(e) { setError(e.response?.data?.detail || 'Could not load policy checks.'); } }
  useEffect(()=>{load();},[offset]);
  async function act(fn) { setBusy(true);setError('');try { await fn(); await load(); }catch(e){setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Action failed. Check the input values.');}finally{setBusy(false);} }
  return <section><h2 className="text-xl font-semibold mb-4">Company policy checks</h2>
    <p className="text-secondary mb-4">Explicit Aster demo rules alongside the ML model. Policy triggers open review cases; they do not change the anomaly score. Currency, approver and evidence gaps remain visible.</p>
    {error && <p role="alert">{error}</p>}
    {admin && <>
      <button disabled={busy} className="btn btn-primary mb-4" onClick={()=>act(()=>policiesApi.run())}>{busy ? 'Working…' : 'Run company policy checks'}</button>
      <details className="glass-card mb-4"><summary>Provision checker authority (INR)</summary><p>Only raise a limit when authorized by your company. These are demo policies; all changes are recorded.</p><form className="transfer-controls" onSubmit={e=>{e.preventDefault();act(()=>policiesApi.authority(reviewer,limit));}}><label>Checker<select required value={reviewer} onChange={e=>setReviewer(e.target.value)}><option value="">Select checker</option>{reviewers.map(r=><option value={r.id} key={r.id}>{r.email} · current {r.limit}</option>)}</select></label><label>Approval limit<input required type="number" min="0" step="0.01" value={limit} onChange={e=>setLimit(e.target.value)} /></label><button className="btn btn-secondary" disabled={busy}>Save authority</button></form></details>
      <details className="glass-card mb-4"><summary>Add missing claim evidence</summary><form className="transfer-review-form" onSubmit={e=>{e.preventDefault();act(()=>policiesApi.inputs(claim,JSON.parse(evidence)));}}><label>Claim ID<input required value={claim} onChange={e=>setClaim(e.target.value)} /></label><label>Evidence JSON<textarea required value={evidence} onChange={e=>setEvidence(e.target.value)} /></label><p>Supported fields: invoice_id, invoice_series, invoice_sequence, event_timestamp (include timezone), source_approver_id, source_approver_limit, business_exception. Save evidence, then run checks.</p><button className="btn btn-secondary" disabled={busy}>Save evidence</button></form></details>
    </>}
    {data && <><details className="glass-card mb-4"><summary>Policy configuration and limitations</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(data.config,null,2)}</pre><p>All thresholds are fictional Aster demo assumptions. Matching amounts may be recurring payments; sequence gaps may reflect incomplete imports. Round values, weekend activity and phrases are review prompts, not proof. Legacy low-value claims without currency retain the existing review flow; high-value authority cannot be verified without currency. Closed decisions are preserved. No ML retraining is performed.</p></details>
      <p>{data.total} claims evaluated · showing {data.total ? offset+1 : 0}–{Math.min(offset+50,data.total)}</p>
      {data.items.map(p=><details className="glass-card mb-4" key={p.claim_id}><summary>{p.claim_id} · {p.requires_review ? 'Review required' : 'No review trigger'}</summary><Link to={`/claims/${encodeURIComponent(p.claim_id)}`}>Open claim</Link><PolicyEvidence result={p}/></details>)}
      <div className="transfer-controls"><button className="btn btn-secondary" disabled={offset===0||busy} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous</button><button className="btn btn-secondary" disabled={offset+50>=data.total||busy} onClick={()=>setOffset(offset+50)}>Next</button></div>
    </>}
  </section>;
}
