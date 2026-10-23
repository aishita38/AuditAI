export function snapshotGroups(item) {
  const e=item.evidence||{}, groups=[];
  const add=(title,kind,rows,idKey)=>{if(rows?.length)groups.push({title,kind,rows,idKey});};
  if(item.case_type==='expense_claim'){
    add('Claim at capture','claim',e.claim?[e.claim]:[],'claim_id');
    add('Linked payments at capture','transfer',e.payments||[],'transaction_id');
    const saved=e.supporting_claims||[];
    const referenced=[...new Set((e.policy?.checks||[]).filter(c=>c.status==='review').flatMap(c=>c.related_claims||[]))];
    add('Supporting claims at capture','claim',[...saved,...referenced.filter(id=>id!==e.claim?.claim_id&&!saved.some(c=>c.claim_id===id)).map(claim_id=>({claim_id,snapshot_note:'Only the claim identifier was saved in this legacy snapshot.'}))],'claim_id');
  } else if(item.case_type==='circular_payment') {
    const rows=e.transfers||[];
    const missing=(e.transaction_ids||[]).filter(id=>!rows.some(r=>r.transaction_id===id)).map(transaction_id=>({transaction_id,snapshot_note:'Record fields were not saved in this legacy snapshot.'}));
    add('All transfers in the cycle','transfer',[...rows,...missing],'transaction_id');
  } else if(item.case_type==='reconciliation') {
    add('Claim at capture','claim',[e.claim||{claim_id:e.claim_id,claimed_amount:e.claim_amount,currency:e.claim_currency,status:e.claim_status,approved_at:e.approved_at}],'claim_id');
    add('All payments at capture','transfer',e.payments||[],'transaction_id');
  } else {
    add('Vendors at capture','vendor',e.vendors||[],'vendor_id');
    add('Vendor-linked transfers at capture','transfer',e.transactions||[],'transaction_id');
    add('Payroll payments at capture','payroll_payment',e.payments|| (e.payment?[e.payment]:[]),'payment_id');
    add('Roster records at capture','employee',e.employees||e.roster_records||(e.employee?[e.employee]:e.roster_record?[e.roster_record]:[]),'employee_id');
  }
  return groups;
}
export function evidenceReferences(item){return [...snapshotGroups(item).flatMap(g=>g.rows.filter(r=>r[g.idKey]).map(r=>({kind:g.kind,id:String(r[g.idKey])}))),...(item.evidence?.policy?.checks||[]).flatMap(c=>(c.related_claims||[]).map(id=>({kind:'claim',id})))];}
