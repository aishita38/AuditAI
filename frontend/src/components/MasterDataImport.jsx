import React,{useEffect,useState} from 'react';
import {masterDataApi,claimsApi,transfersApi} from '../api/client';
import {useAuth} from '../auth/AuthContext';
import AutomaticCheckResult from './AutomaticCheckResult';
const DATASETS={'vendor-master':'Vendor master','employee-roster':'Employee roster','payroll-payments':'Payroll payments'};
const ALL_TYPES={...DATASETS,'expense-claims':'Expense claims','receipts':'Receipt','bank-transfers':'Bank transfers'};
export default function MasterDataImport(){
  const {user}=useAuth();const [dataset,setDataset]=useState('vendor-master'),[file,setFile]=useState(null),[status,setStatus]=useState([]),[report,setReport]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[claimId,setClaimId]=useState('');
  const load=()=>masterDataApi.status().then(r=>setStatus(r.data));
  useEffect(()=>{load().catch(()=>setError('Could not load master-data import status.'));},[]);
  const upload=async e=>{e.preventDefault();setBusy(true);setError('');setReport(null);try{let r;if(DATASETS[dataset])r=await masterDataApi.upload(dataset,file);else {const body=new FormData();body.append('file',file);r=dataset==='bank-transfers'?await transfersApi.upload(body):dataset==='expense-claims'?await claimsApi.upload(body):await claimsApi.uploadReceipt(claimId.trim(),body);}setReport({...r.data,dataset:r.data.dataset||ALL_TYPES[dataset]});}catch(e){const detail=e.response?.data;if(detail?.errors)setReport(detail);else setError(typeof detail?.detail==='string'?detail.detail:'Import failed.');}finally{try{await load();}catch{setError('Could not refresh import status.');}setBusy(false);}};
  return <section className="glass-card mb-6"><h2>Data Import</h2><p>Upload once. Relevant checks run automatically and results are included in the dashboard. Re-imports update or skip matching business IDs. Only these new imports accept valid rows and report rejected rows separately.</p>
    <ul>{Object.entries(DATASETS).map(([key,label])=>{const s=status.find(r=>r.dataset===key);return <li key={key}>{label}: {s?.rows_loaded??0} rows; last attempt {s?.last_imported_at||'Never'}; status {s?.last_import_status||'Not imported'}</li>;})}</ul>
    {user?.roles?.includes('admin')?<form className="transfer-controls" onSubmit={upload}>
      <label>Dataset type<select value={dataset} onChange={e=>{setDataset(e.target.value);setFile(null);setReport(null);}}>{Object.entries(ALL_TYPES).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
      {dataset==='receipts'&&<label>Target Claim ID<input required value={claimId} onChange={e=>setClaimId(e.target.value)} placeholder="AST-DEMO-CLM-001"/></label>}
      <label>{dataset==='receipts'?'Receipt image or PDF':'CSV file'}<input key={dataset} type="file" accept={dataset==='receipts'?'.png,.jpg,.jpeg,.pdf,.tiff,.bmp':'.csv,text/csv'} required onChange={e=>setFile(e.target.files[0]||null)}/></label>
      <button className="btn btn-primary" disabled={busy||!file||(dataset==='receipts'&&!claimId.trim())}>{busy?'Importing and checking...':'Import and check'}</button>
      {DATASETS[dataset]?<a href={`/samples/master-data/${dataset}.csv`} download>Download synthetic example CSV</a>:<a href="/downloads/aster/aster_upload_pack.zip" download>Download Aster demo files</a>}
    </form>:<p>An administrator can use this combined import. Your existing claim and receipt upload controls are available below.</p>}

    {error&&<p role="alert">{error}</p>}{report&&<div role="status"><AutomaticCheckResult checks={report.checks}/><p>{report.dataset}: {report.status||report.upload_status||'Imported'}. {report.inserted!=null?`Inserted ${report.inserted}; updated ${report.updated}; skipped ${report.skipped}; rejected ${report.rejected}.`:report.message|| (report.imported!=null?`${report.imported} transfers imported; ${report.skipped} skipped.`:report.upload_status==='processed'?'Receipt processed.':'See upload status.')}</p>{report.errors?.length>0&&<details open><summary>Row rejection report ({report.errors.length})</summary><ul>{report.errors.map((e,i)=><li key={i}>Row {e.row??'file'}: {e.reason||e.error}</li>)}</ul></details>}</div>}
  </section>;
}
