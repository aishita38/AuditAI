import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ShieldAlert, Users, Percent, UserCheck } from 'lucide-react';
import { analyticsApi } from '../api/client';
import ScoreBadge from '../components/ScoreBadge';
import RecordLink from '../components/RecordLink';
import { useSearchParams } from 'react-router-dom';
import CircularPayments from './CircularPayments';
import PaymentReconciliation from './PaymentReconciliation';
import PolicyChecks from './PolicyChecks';
import MasterChecks from './MasterChecks';

export default function AuditScreens() {
  const [params, setParams] = useSearchParams();
  const activeTab = params.get('tab') || 'benford';
  const setActiveTab = tab => setParams({ tab });
  const [benfordData, setBenfordData] = useState([]);
  const [relatedParties, setRelatedParties] = useState([]);
  const [sodViolations, setSodViolations] = useState([]);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const loaders = {
      benford: [analyticsApi.benford, setBenfordData],
      related: [analyticsApi.relatedParties, setRelatedParties],
      sod: [analyticsApi.sodViolations, setSodViolations],
    };
    const selected = loaders[activeTab];
    if (!selected) return;
    let active = true;
    setLoading(true);
    setError('');
    selected[0]().then(response => {
      if (active) selected[1](response.data);
    }).catch(() => {
      if (active) setError('This audit check could not load. Please retry.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [activeTab, retry]);

  return (
    <div className="main-content">
      {/* Header Context */}
      <div className="flex items-center gap-2 text-sm text-muted mb-2">
        <span>Global Auditing</span>
        <span>/</span>
        <span className="text-secondary font-medium">APAC Entity · INR</span>
      </div>

      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Compliance & Screening</h1>
      </div>

      {/* Tabs Row */}
      <div className="flex gap-2 mb-6 border-b border-glass pb-3" style={{ flexWrap: 'wrap' }}>
        <button
          className={`btn ${activeTab === 'benford' ? 'btn-primary' : 'btn-secondary'} py-2 px-4 text-sm`}
          onClick={() => setActiveTab('benford')}
        >
          <Percent size={16} /> Benford's Law
        </button>

        <button
          className={`btn ${activeTab === 'related' ? 'btn-primary' : 'btn-secondary'} py-2 px-4 text-sm`}
          onClick={() => setActiveTab('related')}
        >
          <Users size={16} /> Related-Party Screening
        </button>

        <button
          className={`btn ${activeTab === 'sod' ? 'btn-primary' : 'btn-secondary'} py-2 px-4 text-sm`}
          onClick={() => setActiveTab('sod')}
        >
          <UserCheck size={16} /> Segregation of Duties (SoD)
        </button>
        <button className={`btn ${activeTab === 'circular' ? 'btn-primary' : 'btn-secondary'} py-2 px-4 text-sm`} onClick={() => setActiveTab('circular')}>Circular Payments</button>
        <button className={`btn ${activeTab === 'reconciliation' ? 'btn-primary' : 'btn-secondary'} py-2 px-4 text-sm`} onClick={() => setActiveTab('reconciliation')}>Payment Reconciliation</button>
        <button className={`btn ${activeTab === 'policies' ? 'btn-primary' : 'btn-secondary'} py-2 px-4 text-sm`} onClick={() => setActiveTab('policies')}>Company Policy</button>
        <button className={`btn ${activeTab === 'vendor' ? 'btn-primary' : 'btn-secondary'}`} onClick={()=>setActiveTab('vendor')}>Vendor Master Checks</button>
        <button className={`btn ${activeTab === 'payroll' ? 'btn-primary' : 'btn-secondary'}`} onClick={()=>setActiveTab('payroll')}>Payroll Checks</button>
      </div>
      {activeTab === 'circular' && <CircularPayments />}
      {activeTab === 'reconciliation' && <PaymentReconciliation />}
      {activeTab === 'policies' && <PolicyChecks />}
      {['benford', 'related', 'sod'].includes(activeTab) && loading && <div className="glass-card" role="status">Loading selected audit check...</div>}
      {['benford', 'related', 'sod'].includes(activeTab) && error && <div className="glass-card" role="alert">{error} <button className="btn btn-secondary" onClick={() => setRetry(value => value + 1)}>Retry</button></div>}
      {activeTab === 'vendor' && <MasterChecks dataset="vendor"/>}
      {activeTab === 'payroll' && <MasterChecks dataset="payroll"/>}
      {/* Tab Contents */}
      {activeTab === 'benford' && !loading && !error && (
        <div className="glass-card">
          <div className="mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-2">
              <Percent className="text-accent-primary" />
              Benford's Law Screen
            </h3>
            <p className="text-sm text-secondary">
              Analyzes the frequency of leading digits (1-9) of all transaction amounts.
              Naturally occurring transaction amounts follow a logarithmic curve. Anomalous spikes may indicate manual fraud or artificial expense splitting.
            </p>
          </div>

          <div style={{ height: 350, width: '100%' }}>
            <ResponsiveContainer>
              <BarChart data={benfordData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="digit" />
                <YAxis unit="%" />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                <Legend />
                <Bar dataKey="actual" name="Actual Distribution" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expected" name="Expected Log Distribution" fill="rgba(255,255,255,0.15)" stroke="var(--border-light)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {activeTab === 'related' && !loading && !error && (
        <div className="glass-card">
          <div className="mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-2">
              <Users className="text-accent-primary" />
              Related-Party Detection
            </h3>
            <p className="text-sm text-secondary">
              Identifies claims where the employee's name matches or is highly similar to the vendor's name (e.g. employee "Sharma" claiming expenses against "Sharma consulting").
            </p>
          </div>

          {relatedParties.length === 0 ? (
            <p className="text-secondary text-center py-10 italic">No related-party transactions detected.</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Claim ID</th>
                    <th>Employee Name</th>
                    <th>Vendor Name</th>
                    <th>Amount</th>
                    <th>Matched Terms</th>
                    <th>Anomaly Index</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedParties.map((rp, idx) => (
                    <tr key={idx}>
                      <td className="font-semibold text-accent-primary"><RecordLink kind="claim" id={rp.claim_id} knownExists={rp.claim_exists}/></td>
                      <td>{rp.employee_name}</td>
                      <td>{rp.vendor_name}</td>
                      <td>₹{rp.claimed_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td>
                        {rp.matched_terms.map((term, i) => (
                          <span key={i} className="badge badge-amber text-xs mr-1">{term}</span>
                        ))}
                      </td>
                      <td><ScoreBadge score={rp.fraud_score} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'sod' && !loading && !error && (
        <div className="glass-card">
          <div className="mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-2">
              <ShieldAlert className="text-status-danger" />
              Segregation of Duties Violations
            </h3>
            <p className="text-sm text-secondary">
              Logs critical audit violations where duty segregation was bypassed (e.g. claimant acting as Maker/Checker or same user performing Maker and Checker actions).
            </p>
          </div>

          {sodViolations.length === 0 ? (
            <p className="text-secondary text-center py-10 italic">No Segregation of Duties violations logged.</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Claim ID</th>
                    <th>Employee Name</th>
                    <th>Violation Type</th>
                    <th>User Involved</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {sodViolations.map((sod, idx) => (
                    <tr key={idx}>
                      <td className="font-semibold text-accent-primary"><RecordLink kind="claim" id={sod.claim_id} knownExists={sod.claim_exists}/></td>
                      <td>{sod.employee_name}</td>
                      <td>
                        <span className="badge badge-red text-xs">{sod.type}</span>
                      </td>
                      <td className="font-medium">{sod.user_involved}</td>
                      <td className="text-secondary text-xs">{sod.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
