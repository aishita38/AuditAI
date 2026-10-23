import React, { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { reviewQueueApi } from '../api/client';
import { TYPES, STATES } from './reviewLabels';
import './CircularPayments.css';
import './ReviewCases.css';

export default function ReviewQueue() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const type=params.get('case_type')||'', status=params.get('status')||'', severity=params.get('severity')||'';
  const offset=Math.max(0, Number(params.get('offset'))||0);
  const [data,setData]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false), [refresh,setRefresh]=useState(0);
  const setFilter=(key,value)=>setParams(previous=>{const next=new URLSearchParams(previous);next.delete('case');next.delete('offset');if(value)next.set(key,value);else next.delete(key);return next;});
  const caseUrl=useCallback(id=>{const filters=new URLSearchParams(params);filters.delete('case');return `/review/cases/${id}?${new URLSearchParams({returnTo:'/review-queue'+(filters.toString()?'?'+filters.toString():'')})}`;},[params]);
  useEffect(()=>{if(params.get('case'))navigate(caseUrl(params.get('case')),{replace:true});},[params,navigate,caseUrl]);
  useEffect(()=>{
    let active=true;
    setBusy(true);setError('');
    (async()=>{try {
      await reviewQueueApi.sync();
      const response=await reviewQueueApi.list({case_type:type||undefined,status:status||undefined,severity:severity||undefined,offset,limit:50});
      if(active)setData(response.data);
    } catch(e){if(active)setError(e.response?.data?.detail||'Could not load the shared queue.');}
    finally{if(active)setBusy(false);}})();
    return ()=>{active=false;};
  },[type,status,severity,offset,refresh]);
  return <main className="main-content"><h1>Shared review queue</h1><p>All review cases in one place. Findings are review signals, never proof of fraud.</p>
    <form className="glass-card transfer-controls mb-4" onSubmit={e=>{e.preventDefault();setRefresh(v=>v+1);}}>
      <label>Case type<select value={type} onChange={e=>setFilter('case_type',e.target.value)}><option value="">All types</option>{Object.entries(TYPES).map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>
      <label>Status<select value={status} onChange={e=>setFilter('status',e.target.value)}><option value="">All statuses</option>{Object.entries(STATES).map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>
      <label>Severity<select value={severity} onChange={e=>setFilter('severity',e.target.value)}><option value="">All severities</option>{['low','medium','high','critical'].map(v=><option key={v}>{v}</option>)}</select></label>
      <button className="btn btn-secondary" disabled={busy}>Refresh queue</button>
    </form>
    {error&&<p role="alert">{error}</p>}{busy&&<p role="status">Loading queue...</p>}
    {data&&<><p>{data.total} cases matching filters</p><div className="glass-card table-container"><table><thead><tr><th>Case</th><th>Type</th><th>Severity</th><th>Reason</th><th>Status</th></tr></thead><tbody>{data.items.map(c=>{
      const url=caseUrl(c.id);
      return <tr key={c.id} className="review-case-row" role="link" tabIndex={0} aria-label={`Open case #${c.id}`} onClick={e=>{if(!e.target.closest('a'))navigate(url);}} onKeyDown={e=>{if(e.target===e.currentTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();navigate(url);}}}>
        <td><Link className="case-number-link" to={url}>#{c.id}</Link></td><td>{TYPES[c.case_type]||c.case_type}</td><td>{c.severity}</td><td>{c.reason}</td><td>{STATES[c.status]||c.status}</td>
      </tr>;
    })}</tbody></table>{!data.items.length&&<p>No cases match these filters.</p>}</div><div className="transfer-controls"><button className="btn btn-secondary" disabled={!offset||busy} onClick={()=>setParams(p=>{p.set('offset',String(Math.max(0,offset-50)));return p;})}>Previous</button><button className="btn btn-secondary" disabled={offset+50>=data.total||busy} onClick={()=>setParams(p=>{p.set('offset',String(offset+50));return p;})}>Next</button></div></>}
  </main>;
}
