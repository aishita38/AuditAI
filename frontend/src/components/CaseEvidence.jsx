import React from 'react';
import RecordLink from './RecordLink';
import PolicyEvidence from './PolicyEvidence';
import {snapshotGroups} from './evidenceRecords';

const label=value=>value.replaceAll('_',' ');
export function ReadableValue({value}) {
  if(value==null)return <span>Not saved</span>;
  if(Array.isArray(value))return value.length?<><ol>{value.slice(0,10).map((v,i)=><li key={i}><ReadableValue value={v}/></li>)}</ol>{value.length>10&&<details><summary>Show all {value.length} entries</summary><ol start={11}>{value.slice(10).map((v,i)=><li key={i}><ReadableValue value={v}/></li>)}</ol></details>}</>:<span>None</span>;
  if(typeof value==='object')return <dl>{Object.entries(value).map(([k,v])=><React.Fragment key={k}><dt>{label(k)}</dt><dd><ReadableValue value={v}/></dd></React.Fragment>)}</dl>;
  return <span>{String(value)}</span>;
}
function triggeredFields(item) {
  const e=item.evidence||{};
  const fields=new Set([...(Array.isArray(e.trigger_fields)?e.trigger_fields:[]),...(Array.isArray(e.matched_fields)?e.matched_fields:[]),e.trigger_field,e.matched_field,e.shared_attribute,e.field].filter(v=>typeof v==='string'));
  if(item.case_type==='circular_payment')['sender_account','receiver_account','amount','timestamp'].forEach(f=>fields.add(f));
  for(const flag of e.flags||[]) {
    if(flag.includes('amount')||flag.includes('total'))['claimed_amount','amount'].forEach(f=>fields.add(f));
    if(flag.includes('currency'))fields.add('currency');
    if(flag.includes('approval'))['timestamp','approved_at','status'].forEach(f=>fields.add(f));
    if(flag.includes('rejected'))fields.add('status');
    if(flag.includes('multiple'))fields.add('claim_id');
  }
  for(const check of e.policy?.checks||[])if(check.status==='review'){
    for(const field of check.fields||[])fields.add(field);
    if(check.code?.includes('receipt'))fields.add('claimed_amount');
  }
  const groups=snapshotGroups(item);
  if(item.case_type==='vendor_check'||item.case_type==='payroll_check') {
    for(const field of ['bank_account','pan','gstin','phone','address']) {
      const values=groups.flatMap(g=>g.rows).map(r=>r[field]).filter(Boolean);
      if(values.length>new Set(values).size)fields.add(field);
    }
  }
  return fields;
}
function SnapshotRows({group,fields}) {
  const rows=group.rows;
  const render=list=><div className="table-container"><table><thead><tr><th>Live record</th><th>Saved evidence fields</th></tr></thead><tbody>{list.map((r,i)=><tr key={`${r[group.idKey]}-${i}`}><td><RecordLink kind={group.kind} id={r[group.idKey]}/></td><td><dl>{Object.entries(r).map(([k,v])=><React.Fragment key={k}><dt className={fields.has(k)?'evidence-trigger':''}>{label(k)}{fields.has(k)&&' · Rule trigger'}</dt><dd className={fields.has(k)?'evidence-trigger':''}><ReadableValue value={v}/></dd></React.Fragment>)}</dl></td></tr>)}</tbody></table></div>;
  return <section className="evidence-records"><h4>{group.title} ({rows.length})</h4>{render(rows.slice(0,10))}{rows.length>10&&<details><summary>Show all {rows.length} records ({rows.length-10} more)</summary>{render(rows.slice(10))}</details>}</section>;
}
function Records({item}){return snapshotGroups(item).map(g=><SnapshotRows key={g.title} group={g} fields={triggeredFields(item)}/>);}
function ExpenseEvidence({item}) {
  const e=item.evidence||{};
  return <><h3>Expense claim evidence</h3><Records item={item}/>{!Object.hasOwn(e,'payments')&&<p>Linked payments were not captured in this older snapshot. Any current links appear separately under Related records.</p>}
    <h4>Receipt at capture</h4><div className="evidence-records"><ReadableValue value={e.receipt||'No receipt saved.'}/></div>
    <h4>Model score and explanation at capture</h4><div className="evidence-records"><ReadableValue value={e.prediction||'No model score saved.'}/></div>
    {e.policy&&<PolicyEvidence result={e.policy}/>}<p>{e.snapshot_note}</p></>;
}
function CircularEvidence({item}) {const e=item.evidence||{};return <><h3>Circular payment evidence</h3><p className="transfer-path">{(e.accounts||[]).join(' → ')||'Account path not saved'}</p><p>{e.currency} {e.initial_amount} sent; {e.returned_amount} returned ({e.return_ratio==null?'Unknown':(e.return_ratio*100).toFixed(1)}%).</p><p>{e.reason}</p><Records item={item}/></>;}
function ReconciliationEvidence({item}) {const e=item.evidence||{};return <><h3>Payment reconciliation evidence</h3><p>Claim {e.claim_currency} {e.claim_amount}; paid {e.paid_total??'Total not saved'}.</p><ul>{(e.flags||[]).map(f=><li key={f}>{label(f)}</li>)}</ul><Records item={item}/></>;}
function GenericEvidence({item}) {const extra=Object.fromEntries(Object.entries(item.evidence||{}).filter(([k])=>!['vendors','transactions','payments','payment','employees','employee','roster_records','roster_record'].includes(k)));return <><h3>Saved evidence</h3><Records item={item}/><div className="evidence-records"><ReadableValue value={Object.keys(extra).length?extra:{note:'No additional evidence fields were saved.'}}/></div></>;}
export default function CaseEvidence({item}) {
  const Viewer={expense_claim:ExpenseEvidence,circular_payment:CircularEvidence,reconciliation:ReconciliationEvidence}[item.case_type]||GenericEvidence;
  return <section aria-label="Evidence snapshot"><p>Evidence snapshot saved at case creation. Highlighted fields triggered the rule; live links may show later changes.</p><Viewer item={item}/></section>;
}
