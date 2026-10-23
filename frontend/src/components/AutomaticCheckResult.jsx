import React from 'react';
import {Link} from 'react-router-dom';
export default function AutomaticCheckResult({checks}){
 if(!checks)return null;
 return <section aria-label="Automatic check results"><h3>Automatic checks</h3>{checks.status==='partial'&&<p role="alert">Your upload was saved, but some checks could not finish. See the status below.</p>}<ul>{checks.stages.map(stage=><li key={stage.detector}><strong>{stage.detector.replaceAll('_',' ')}:</strong> {stage.status==='failed'?stage.message:stage.missing_datasets?.length?`Waiting for ${stage.missing_datasets.join(', ')}`:stage.finding_count!=null?`${stage.finding_count} current findings`:stage.scored_count!=null?`${stage.scored_count} claims scored, ${stage.flagged_count} flagged`:stage.circular_findings!=null?`${stage.circular_findings} cycles; ${stage.reconciliation_findings} reconciliation findings`:'Completed'}{stage.availability?.filter(s=>s.rule_id==='VENDOR_NEW_LARGE_PAYMENT').map(s=><p key={s.rule_id}>{s.message}</p>)}{stage.search_limited&&<p role="alert">Transfer search reached its limit; results are incomplete.</p>}</li>)}</ul><Link className="record-link" to="/">View all anomaly signals</Link></section>;
}
