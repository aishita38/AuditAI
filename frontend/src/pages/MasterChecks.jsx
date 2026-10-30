import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, RefreshCw } from 'lucide-react';
import { masterDataApi } from '../api/client';
import CaseEvidence from '../components/CaseEvidence';
import { evidenceReferences } from '../components/evidenceRecords';
import { RecordLinksProvider } from '../components/RecordLink';
import './ReviewCases.css';

export default function MasterChecks({ dataset }) {
  const [data, setData] = useState(null),
    [selected, setSelected] = useState(null),
    [rule, setRule] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [status, setStatus] = useState([]);

  useEffect(() => {
    let active = true;
    setData(null);
    setSelected(null);
    setRule('');
    setError('');
    masterDataApi
      .status()
      .then((r) => {
        if (active) setStatus(r.data);
      })
      .catch(() => {
        if (active) setError('Could not load dataset status.');
      });
    masterDataApi
      .findings(dataset)
      .then((r) => {
        if (active) setData(r.data);
      })
      .catch(() => {
        if (active) setError('Could not load findings.');
      });
    return () => {
      active = false;
    };
  }, [dataset]);

  const run = async () => {
    setBusy(true);
    setError('');
    setSelected(null);
    try {
      setData((await masterDataApi.run(dataset)).data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not run checks.');
    } finally {
      setBusy(false);
    }
  };

  const send = async (finding) => {
    setBusy(true);
    setError('');
    try {
      const caseId = (await masterDataApi.send(finding.id)).data.case_id;
      setData((d) => ({
        ...d,
        items: d.items.map((f) => (f.id === finding.id ? { ...f, case_id: caseId } : f)),
      }));
      setSelected((f) => (f?.id === finding.id ? { ...f, case_id: caseId } : f));
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not send finding to review.');
    } finally {
      setBusy(false);
    }
  };

  const missing = (dataset === 'vendor' ? ['vendor-master'] : ['employee-roster', 'payroll-payments']).filter(
    (key) => !status.find((s) => s.dataset === key)?.rows_loaded
  );
  const caseItem = selected
    ? { case_type: dataset === 'vendor' ? 'vendor_check' : 'payroll_check', evidence: selected.evidence }
    : null;

  const filteredItems = data?.items?.filter((f) => !rule || f.rule_id === rule) || [];

  return (
    <section className="master-checks">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold">{dataset === 'vendor' ? 'Vendor Master Checks' : 'Payroll Checks'}</h2>
        <div className="check-actions" style={{ margin: 0 }}>
          <button className="btn btn-primary text-xs flex items-center gap-1.5" disabled={busy} onClick={run}>
            <RefreshCw size={14} className={busy ? 'animate-spin' : ''} />
            <span>{busy ? 'Working...' : 'Recheck (optional)'}</span>
          </button>
          <Link className="btn btn-secondary text-xs" to="/upload">
            Import / update datasets
          </Link>
        </div>
      </div>

      <p className="text-secondary text-xs mb-3">
        Findings are review signals, never proof of fraud, based on the imported data only. Checks run automatically when these datasets are uploaded. Synthetic examples demonstrate rules and do not establish real-world performance.
      </p>

      {missing.length > 0 && (
        <div className="glass-card mb-4 p-3 border-l-4 border-status-warning text-xs" role="status">
          Import {missing.join(', ')} to enable this check.{' '}
          <Link to="/upload" className="text-accent-primary underline font-medium ml-1">
            Open Data Import
          </Link>
        </div>
      )}

      <p className="text-muted text-xs mb-4">
        {dataset === 'vendor'
          ? 'Tax IDs: format check, not verification. New-vendor large payment: Cannot evaluate, vendor-linked transactions unavailable. Vendor names are never used to link payments.'
          : 'Duplicate payees: bank-account matching across roster and payments; PAN matching on roster only. Salary comparisons do not adjust for bonuses, partial months, taxes, or arrears.'}
      </p>

      {data?.config && (
        <p className="text-muted text-[11px] mb-4">
          Configured thresholds: new vendor INR {data.config.new_vendor_amount_inr}, {data.config.new_vendor_days} days; salary tolerance {Number(data.config.salary_tolerance) * 100}%.
        </p>
      )}

      {error && <p role="alert" className="glass-card mb-4 text-xs text-status-danger">{error}</p>}

      {data && (
        <>
          <div className="flex items-center justify-between mb-4">
            <label className="text-xs text-secondary flex items-center gap-2">
              Filter by rule
              <select
                className="input text-xs py-1 px-2"
                style={{ width: 'auto' }}
                value={rule}
                onChange={(e) => setRule(e.target.value)}
              >
                <option value="">All rules</option>
                {[...new Set(data.items.map((f) => f.rule_id))].sort().map((id) => (
                  <option key={id}>{id}</option>
                ))}
              </select>
            </label>
            <span className="text-xs text-muted">
              {filteredItems.length} findings. Re-running unchanged data preserves finding and case identities.
            </span>
          </div>

          {filteredItems.length === 0 ? (
            <div className="glass-card flex flex-col items-center justify-center py-10 text-center mb-6">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center mb-3"
                style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--status-success)' }}
              >
                <CheckCircle2 size={22} />
              </div>
              <h4 className="text-sm font-semibold text-primary mb-1">
                {dataset === 'vendor' ? 'No Vendor Collusion Anomaly Detected' : 'No Payroll Discrepancies Detected'}
              </h4>
              <p className="text-xs text-secondary max-w-md">
                {dataset === 'vendor'
                  ? 'All vendor tax identifiers, addresses, and registration profiles passed screening.'
                  : 'Roster accounts, payroll payees, and compensation thresholds match company records.'}
              </p>
            </div>
          ) : (
            <div className="table-container glass-card mb-6">
              <table>
                <thead>
                  <tr>
                    <th>Rule</th>
                    <th>Severity</th>
                    <th>Reason</th>
                    <th>Evidence</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredItems.map((f) => (
                    <tr key={f.id}>
                      <td className="font-semibold text-xs text-primary">{f.rule_id}</td>
                      <td>
                        <span
                          className={`badge text-xs uppercase ${
                            f.severity === 'critical' || f.severity === 'high'
                              ? 'badge-red'
                              : f.severity === 'medium'
                              ? 'badge-amber'
                              : 'badge-blue'
                          }`}
                        >
                          {f.severity}
                        </span>
                      </td>
                      <td className="text-xs text-secondary">{f.explanation}</td>
                      <td>
                        <button className="btn btn-secondary text-xs py-1 px-3" onClick={() => setSelected(f)}>
                          View evidence
                        </button>
                      </td>
                      <td>
                        {f.case_id ? (
                          <Link
                            className="case-number-link text-xs"
                            to={`/review/cases/${f.case_id}?returnTo=${encodeURIComponent(
                              '/review-queue?case_type=' + (dataset === 'vendor' ? 'vendor_check' : 'payroll_check')
                            )}`}
                          >
                            Open case #{f.case_id}
                          </Link>
                        ) : (
                          <button
                            className="btn btn-primary text-xs py-1 px-3"
                            disabled={busy}
                            onClick={() => send(f)}
                          >
                            Send to review
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {caseItem && (
        <aside className="glass-card" aria-label="Finding evidence">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-accent-primary">{selected.rule_id}</h3>
            <button className="btn btn-secondary text-xs py-1 px-2.5" onClick={() => setSelected(null)}>
              Close evidence
            </button>
          </div>
          <RecordLinksProvider records={evidenceReferences(caseItem)}>
            <CaseEvidence item={caseItem} />
          </RecordLinksProvider>
          <div className="mt-4 pt-3 border-t border-glass flex items-center justify-end">
            {selected.case_id ? (
              <Link className="btn btn-secondary text-xs" to={`/review/cases/${selected.case_id}`}>
                Open case #{selected.case_id}
              </Link>
            ) : (
              <button className="btn btn-primary text-xs" disabled={busy} onClick={() => send(selected)}>
                Send to review
              </button>
            )}
          </div>
        </aside>
      )}
    </section>
  );
}
