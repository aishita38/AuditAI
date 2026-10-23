import React, { useEffect, useState, useCallback } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { reviewQueueApi } from '../api/client';
import CaseEvidence from '../components/CaseEvidence';
import {evidenceReferences} from '../components/evidenceRecords';
import RecordLink, { RecordLinksProvider } from '../components/RecordLink';
import { TYPES, STATES } from './reviewLabels';
import './CircularPayments.css';
import './ReviewCases.css';

export default function CaseDetail() {
  const {caseId}=useParams();
  const [params]=useSearchParams();
  const requested=params.get('returnTo');
  const returnTo=requested==='/review-queue'||requested?.startsWith('/review-queue?')?requested:'/review-queue';
  const [item,setItem]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const [notes,setNotes]=useState(''),[comment,setComment]=useState(''),[action,setAction]=useState('approve');
  const load=useCallback(async()=>{const response=await reviewQueueApi.detail(caseId);setItem(response.data);},[caseId]);
  useEffect(()=>{let active=true;setItem(null);setLoading(true);setError('');setNotes('');setComment('');
    reviewQueueApi.detail(caseId).then(r=>{if(active)setItem(r.data);}).catch(e=>{if(active)setError(e.response?.status===404?'Case not found.': 'Could not load this case. Please retry.');}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[caseId]);
  async function mutate(fn){setBusy(true);setError('');try{await fn();setNotes('');setComment('');await load();}catch(e){setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'Could not save. Refresh before trying again.');try{await load();}catch{ /* Keep saved evidence visible on a transient failure. */ }}finally{setBusy(false);}}
  const related=(item?.related_records||[]).filter(r=>['claim','transfer','vendor','employee','payroll_payment'].includes(r.kind)&&r.id);
  const references=item?[...evidenceReferences(item),...related.map(r=>({kind:r.kind,id:String(r.id)}))]:[];
  const permissions=item?.permissions||{};
  return <main className="main-content"><Link to={returnTo} className="record-link">← Back to review queue</Link>
    {loading&&<p role="status">Loading case...</p>}{error&&<p role="alert">{error}</p>}
    {!loading&&!item&&<button className="btn btn-secondary" onClick={()=>window.location.reload()}>Retry</button>}
    {item&&<RecordLinksProvider records={references}><article className="glass-card mt-6"><h1>Case #{item.id}</h1>
      <dl className="case-metadata">{[['Case type',TYPES[item.case_type]||item.case_type],['Severity',item.severity],['Reason',item.reason],['Status',STATES[item.status]||item.status],['Maker',item.maker_id??'Unassigned'],['Checker',item.checker_id??'Unassigned'],['Created time',item.created_at]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <CaseEvidence item={item}/>
      {related.length>0&&<details className="related-records"><summary>Related records ({related.length})</summary><p>Current records connected by explicit record keys. These do not replace the saved evidence above.</p><ul>{related.map((r,i)=><li key={i}>{r.kind}: <RecordLink kind={r.kind} id={r.id}/> {r.claim_id&&` · claim_id: ${r.claim_id}`}</li>)}</ul></details>}
      <h2>Review actions</h2>
      {(permissions.can_make||permissions.can_check)?<form className="transfer-review-form" onSubmit={e=>{e.preventDefault();mutate(()=>reviewQueueApi.decide(item.id,permissions.can_make?'maker-recommend':'checker-signoff',{action,notes}));}}>
        <h3>{permissions.can_make?'Maker recommendation':'Checker decision'}</h3><label>Decision<select value={action} onChange={e=>setAction(e.target.value)}><option value="approve">Approve / explained</option><option value="reject">Reject / unresolved concern</option></select></label>
        <p>{item.case_type==='expense_claim'?'Final sign-off changes the expense claim status.':'This decision resolves the finding only; it does not approve claims or move money.'}</p>
        <label>Review notes<textarea required minLength={5} maxLength={5000} value={notes} onChange={e=>setNotes(e.target.value)}/></label><button className="btn btn-primary" disabled={busy||notes.trim().length<5}>{permissions.can_make?'Submit maker recommendation':'Submit checker sign-off'}</button>
      </form>:<p>{permissions.maker_reason} {permissions.checker_reason}</p>}
      <p>Maker and checker must be different people. The server checks permissions on every action.</p>
      <form className="transfer-review-form" onSubmit={e=>{e.preventDefault();mutate(()=>reviewQueueApi.comment(item.id,comment));}}><label>Comment<textarea required minLength={5} maxLength={5000} value={comment} onChange={e=>setComment(e.target.value)}/></label><button className="btn btn-secondary" disabled={busy||comment.trim().length<5}>Add comment</button></form>
      <h2>Audit trail</h2>{item.audit_trail?.length?<ol>{item.audit_trail.map(e=><li key={e.id}><strong>{e.action}</strong> · {e.actor} · {e.timestamp}<p>{e.notes}</p></li>)}</ol>:<p>No audit events saved.</p>}
    </article></RecordLinksProvider>}
  </main>;
}
