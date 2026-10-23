import React from 'react';
import RecordLink from './RecordLink';

export default function PolicyEvidence({ result }) {
  if (!result) return <p>Company policy checks have not run yet.</p>;
  return <div>
    <p><strong>{result.requires_review ? 'Company policy requires review' : 'No policy review trigger found'}</strong> · {result.policy_version}</p>
    <p>Required checker authority: {result.currency || 'Currency unavailable'} {result.required_approval_amount}</p>
    <div className="table-container"><table><thead><tr><th>Check</th><th>Result</th><th>Evidence</th></tr></thead><tbody>
      {result.checks.map(c => <tr key={c.code}><td>{c.code.replaceAll('_', ' ')}</td><td>{c.status === 'unavailable' ? 'Cannot evaluate — data missing' : c.status}</td><td className={c.status==='review'?'evidence-trigger':''}>{c.detail}{c.related_claims?.length > 0 && <div>Related: {c.related_claims.slice(0,10).map(id => <React.Fragment key={id}><RecordLink kind="claim" id={id}/>{' '}</React.Fragment>)}{c.related_claims.length > 10 && <details><summary>Show all {c.related_claims.length} claims</summary>{c.related_claims.slice(10).map(id=><p key={id}><RecordLink kind="claim" id={id}/></p>)}</details>}</div>}</td></tr>)}
    </tbody></table></div>
  </div>;
}
