import React,{useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {masterDataApi} from '../api/client';
import CaseEvidence from '../components/CaseEvidence';
import {evidenceReferences} from '../components/evidenceRecords';
import {RecordLinksProvider} from '../components/RecordLink';
import './ReviewCases.css';
export default function MasterChecks({dataset}){
  const [data,setData]=useState(null),[selected,setSelected]=useState(null),[rule,setRule]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState([]);
  useEffect(()=>{let active=true;setData(null);setSelected(null);setRule('');setError('');masterDataApi.status().then(r=>{if(active)setStatus(r.data);}).catch(()=>{if(active)setError('Could not load dataset status.');});masterDataApi.findings(dataset).then(r=>{if(active)setData(r.data);}).catch(()=>{if(active)setError('Could not load findings.');});return()=>{active=false;};},[dataset]);
  const run=async()=>{setBusy(true);setError('');setSelected(null);try{setData((await masterDataApi.run(dataset)).data);}catch(e){setError(e.response?.data?.detail||'Could not run checks.');}finally{setBusy(false);}};
  const send=async finding=>{setBusy(true);setError('');try{const caseId=(await masterDataApi.send(finding.id)).data.case_id;setData(d=>({...d,items:d.items.map(f=>f.id===finding.id?{...f,case_id:caseId}:f)}));setSelected(f=>f?.id===finding.id?{...f,case_id:caseId}:f);}catch(e){setError(e.response?.data?.detail||'Could not send finding to review.');}finally{setBusy(false);}};
  const missing=(dataset==='vendor'?['vendor-master']:['employee-roster','payroll-payments']).filter(key=>!status.find(s=>s.dataset===key)?.rows_loaded);
  const caseItem=selected?{case_type:dataset==='vendor'?'vendor_check':'payroll_check',evidence:selected.evidence}:null;
  return <section className="master-checks"><h2>{dataset==='vendor'?'Vendor Master Checks':'Payroll Checks'}</h2><p>Findings are review signals, never proof of fraud, based on the imported data only. Checks run automatically when these datasets are uploaded. Synthetic examples demonstrate rules and do not establish real-world performance.</p>
    {missing.length>0&&<p role="status">Import {missing.join(', ')} to enable this check. <Link to="/upload">Open Data Import</Link></p>}
    {dataset==='vendor'?<p>Tax IDs: format check, not verification. New-vendor large payment: Cannot evaluate, vendor-linked transactions unavailable. Vendor names are never used to link payments.</p>:<p>Duplicate payees: bank-account matching across roster and payments; PAN matching on roster only. Salary comparisons do not adjust for bonuses, partial months, taxes, or arrears.</p>}
    <div className="check-actions"><button className="btn btn-primary" disabled={busy} onClick={run}>{busy?'Working...':'Recheck (optional)'}</button> <Link className="record-link" to="/upload">Import / update datasets</Link></div>
    {data?.config&&<p>Configured thresholds: new vendor INR {data.config.new_vendor_amount_inr}, {data.config.new_vendor_days} days; salary tolerance {Number(data.config.salary_tolerance)*100}%.</p>}
    {error&&<p role="alert">{error}</p>}
    {data&&<><label>Filter by rule <select className="input" style={{width:'auto'}} value={rule} onChange={e=>setRule(e.target.value)}><option value="">All rules</option>{[...new Set(data.items.map(f=>f.rule_id))].sort().map(id=><option key={id}>{id}</option>)}</select></label><p>{data.items.filter(f=>!rule||f.rule_id===rule).length} findings. Re-running unchanged data preserves finding and case identities.</p>
    <div className="table-container glass-card"><table><thead><tr><th>Rule</th><th>Severity</th><th>Reason</th><th>Evidence</th><th>Review</th></tr></thead><tbody>{data.items.filter(f=>!rule||f.rule_id===rule).map(f=><tr key={f.id}><td>{f.rule_id}</td><td>{f.severity}</td><td>{f.explanation}</td><td><button className="btn btn-secondary" onClick={()=>setSelected(f)}>View evidence</button></td><td>{f.case_id?<Link to={`/review/cases/${f.case_id}?returnTo=${encodeURIComponent('/review-queue?case_type='+(dataset==='vendor'?'vendor_check':'payroll_check'))}`}>Open case #{f.case_id}</Link>:<button className="btn btn-primary" disabled={busy} onClick={()=>send(f)}>Send to review</button>}</td></tr>)}</tbody></table></div></>}
    {caseItem&&<aside className="glass-card" aria-label="Finding evidence"><button className="btn btn-secondary" onClick={()=>setSelected(null)}>Close evidence</button><h3>{selected.rule_id}</h3><RecordLinksProvider records={evidenceReferences(caseItem)}><CaseEvidence item={caseItem}/></RecordLinksProvider>{selected.case_id?<Link to={`/review/cases/${selected.case_id}`}>Open case #{selected.case_id}</Link>:<button className="btn btn-primary" disabled={busy} onClick={()=>send(selected)}>Send to review</button>}</aside>}
  </section>;
}
