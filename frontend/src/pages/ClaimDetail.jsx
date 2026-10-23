import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Shield, Clock, FileText, ClipboardList, Info } from 'lucide-react';
import { claimsApi, casesApi, reportsApi, reviewQueueApi } from '../api/client';
import ScoreGauge from '../components/ScoreGauge';
import ShapChart from '../components/ShapChart';
import ReviewEvidence from '../components/ReviewEvidence';
import PolicyEvidence from '../components/PolicyEvidence';
import LoadingSkeleton from '../components/LoadingSkeleton';
import { useAuth } from '../auth/AuthContext';

export default function ClaimDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const claimsReturnTo = location.state?.claimsReturnTo || '/claims';
  const { user } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [auditTrail, setAuditTrail] = useState([]);

  // Case Action Fields
  const [role, setRole] = useState('maker');
  const [submittingAction, setSubmittingAction] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [reportError, setReportError] = useState('');

  const fetchDetail = async () => {
    setLoading(true);setData(null);
    try {
      const response = await claimsApi.getDetail(id);
      setData(response.data);

      // Fetch case audit trail
      const trailResponse = await casesApi.getTrail(id);
      setAuditTrail(trailResponse.data);
    } catch (error) {
      console.error("Failed to fetch claim detail:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const reviewerRoles = ['maker', 'checker'].filter(candidate => user?.roles?.includes(candidate));
  useEffect(() => {
    if (reviewerRoles.length && !reviewerRoles.includes(role)) setRole(reviewerRoles[0]);
  }, [user, role]);

  const openSharedReview = async () => {
    setSubmittingAction(true);
    try { const item=(await reviewQueueApi.expense(id)).data; navigate(`/review/cases/${item.id}`); }
    catch(error) { alert(error.response?.data?.detail || 'Could not open the shared review case.'); }
    finally { setSubmittingAction(false); }
  };

  const handleGenerateReport = async () => {
    setGeneratingReport(true);
    setReportError('');
    try {
      await reportsApi.generate(id);
      await fetchDetail();
    } catch (error) {
      setReportError(error.response?.data?.detail || 'The report could not be generated. Please try again.');
    } finally {
      setGeneratingReport(false);
    }
  };

  if (loading) {
    return (
      <div className="main-content">
        <LoadingSkeleton type="detail" count={3} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="main-content text-center py-20">
        <h2 className="text-2xl mb-4">Claim not found</h2>
        <button className="btn btn-secondary" onClick={() => navigate(claimsReturnTo)}>Back to Claims</button>
      </div>
    );
  }

  const { claim, ocr_result, prediction, audit_report, review_permissions, case_review } = data;
  const reviewBlockReason = role === 'checker' ? review_permissions?.checker_block_reason : review_permissions?.maker_block_reason;
  const anomalyScore = prediction?.combined_fraud_score !== null && prediction?.combined_fraud_score !== undefined
    ? Math.round(prediction.combined_fraud_score * 100)
    : null;
  const modelEnabled = prediction?.feature_values?._model_enabled !== false;
  const modelThreshold = Number(prediction?.feature_values?._model_threshold ?? 0.5);
  const scoreInterpretation = !modelEnabled
    ? 'Expense ML is disabled for enterprise records. Policy and dedicated rules determine review.'
    : anomalyScore === null ? 'Waiting for a model score'
    : prediction.combined_fraud_score >= modelThreshold
      ? 'Model review recommended at the validation-selected cutoff'
      : prediction.is_flagged ? 'Policy review required; model score is below its cutoff'
      : 'Model score is below its validation-selected cutoff';
  const holidayPolicyFlag = Number(prediction?.feature_values?._holiday_policy_flag || 0) >= 0.5;
  const noReviewNeeded = claim.status === 'scored' && !prediction?.is_flagged && !holidayPolicyFlag && !data.policy?.requires_review;
  const timeKnown = Number(prediction?.feature_values?._event_time_known || 0) >= 0.5;
  const visibleShapValues = timeKnown ? prediction?.shap_values : Object.fromEntries(
    Object.entries(prediction?.shap_values || {}).filter(([feature]) => !['hour', 'is_after_hours'].includes(feature))
  );

  return (
    <div className="main-content">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <button className="text-secondary hover:text-primary" onClick={() => navigate(claimsReturnTo)}>
            <ArrowLeft size={24} />
          </button>
          <div className="flex flex-col">
            <span className="text-xs text-muted font-medium">APAC Entity · INR</span>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{claim.claim_id}</h1>
              <span className={`badge ${claim.status === 'approved' ? 'badge-green' :
                  claim.status === 'flagged' || claim.status === 'rejected' ? 'badge-red' :
                    claim.status === 'scored' ? 'badge-blue' : 'badge-amber'
                }`}>{claim.status.toUpperCase()}</span>
            </div>
          </div>
        </div>

        {reviewerRoles.length > 0 && <div className="flex items-center gap-2 glass-card" style={{ padding: '8px 16px', borderRadius: '12px' }}>
          <span className="text-xs text-muted uppercase font-semibold">Reviewing as:</span>
          {reviewerRoles.length === 1 ? <strong className="text-sm">{reviewerRoles[0]}</strong> : (
            <select className="input py-1 px-2 text-xs font-semibold" value={role} onChange={e => setRole(e.target.value)} style={{ width: 100 }}>
              {reviewerRoles.map(assignedRole => <option key={assignedRole} value={assignedRole}>{assignedRole}</option>)}
            </select>
          )}
        </div>}
      </div>

      {/* Top Grid: Metadata, OCR, Risk Gauges */}
      <div className="grid-cols-3 mb-6">
        {/* Left: Metadata */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 text-accent-primary">Claim Details</h3>
          <div className="flex flex-col gap-3 text-sm">
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Employee</span>
              <span className="font-medium">{claim.employee_name} ({claim.employee_id})</span>
            </div>
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Vendor</span>
              <span className="font-medium flex items-center gap-2">
                {claim.vendor_name}
                {claim.closest_vendor_match && (
                  <span
                    className="badge badge-amber text-xs flex items-center gap-1 cursor-help"
                    title={`Name resembles '${claim.closest_vendor_match}' (${Math.round(claim.vendor_similarity_score * 100)}% similarity); verify the vendor identity`}
                  >
                    ⚠ Typo
                  </span>
                )}
              </span>
            </div>
            {claim.closest_vendor_match && (
              <div className="bg-status-warning/10 border border-status-warning/30 rounded p-2 text-xs text-secondary mt-1">
                ⚠️ Possible vendor name typo: {Math.round(claim.vendor_similarity_score * 100)}% similarity to <strong>{claim.closest_vendor_match}</strong>. Confirm the vendor identity; this name check is separate from the anomaly score.
              </div>
            )}
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Amount</span>
              <span className="font-medium text-lg">₹{claim.claimed_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Date</span>
              <span className="font-medium">{claim.claimed_date}</span>
            </div>
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Category</span>
              <span className="font-medium">{claim.category || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Center: OCR */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 text-accent-primary">OCR Extraction</h3>
          {!ocr_result ? (
            <p className="text-secondary italic">No receipt processed for this claim.</p>
          ) : (
            <div className="flex flex-col gap-3 text-sm">
              <div className="flex justify-between border-b border-glass pb-2">
                <span className="text-secondary">Extracted Vendor</span>
                <span className={`font-medium ${ocr_result.extracted_vendor?.toLowerCase() !== claim.vendor_name.toLowerCase() ? 'text-status-warning' : ''}`}>
                  {ocr_result.extracted_vendor || 'None'}
                </span>
              </div>
              <div className="flex justify-between border-b border-glass pb-2">
                <span className="text-secondary">Extracted Amount</span>
                <span className={`font-medium ${ocr_result.extracted_amount && Math.abs(ocr_result.extracted_amount - claim.claimed_amount) > 1 ? 'text-status-danger' : ''}`}>
                  {ocr_result.extracted_amount ? `₹${ocr_result.extracted_amount}` : 'None'}
                </span>
              </div>
              <div className="flex justify-between border-b border-glass pb-2">
                <span className="text-secondary">Extraction Method</span>
                <span className="font-medium">{ocr_result.extraction_method}</span>
              </div>
              <div className="mt-2">
                <span className="text-secondary block mb-1">Raw Text Snippet:</span>
                <div className="mono-pre" style={{ maxHeight: '90px' }}>
                  {ocr_result.raw_ocr_text ? ocr_result.raw_ocr_text.substring(0, 150) + '...' : 'No text'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Scores */}
        <div className="glass-card flex flex-col justify-center">
          <h3 className="text-lg font-semibold mb-2 text-center text-accent-primary">Fraud Risk Assessment</h3>
          {!prediction ? (
            <p className="text-secondary text-center italic mt-4">Not scored yet.</p>
          ) : (
            <>
              <div className="flex justify-center mb-6">
                <ScoreGauge label="Anomaly index (0–100)" score={prediction.combined_fraud_score} size={180} />
              </div>
              <div className="flex justify-around">
                <div className="text-center">
                  <div className="text-xs text-secondary uppercase mb-1">Reconstruction Err</div>
                  <div className="font-bold">{prediction.reconstruction_error?.toFixed(4)}</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-secondary uppercase mb-1">Isolation Forest</div>
                  <div className="font-bold">{prediction.isolation_forest_score?.toFixed(4)}</div>
                </div>
              </div>
              <div className="risk-explanation">
                <div className="risk-explanation-heading">
                  <Info size={16} />
                  <span>How to read this score</span>
                </div>
                <p className="risk-explanation-lead">{scoreInterpretation}</p>
                {holidayPolicyFlag && (
                  <div className="risk-policy-alert">
                    <strong>Holiday receipt policy exception</strong>
                    <span>This claim is dated {claim.claimed_date}, which is on the configured holiday calendar. Receipts added on holidays require auditor confirmation under your policy.</span>
                  </div>
                )}
                <p>
                  This is an <strong>anomaly index</strong>: it measures how unusual the claim looks compared with patterns in the historical data.
                  A score of <strong>{anomalyScore ?? '—'}/100 does not mean a {anomalyScore ?? '—'}% chance of fraud</strong>.
                  It is a signal for an auditor to review, not a final fraud decision.
                </p>
                {Number(prediction.feature_values?._supervised_score || 0) >= 0.5 && (
                  <p>The active classifier produced this index from the claim’s combined features. A low-signal claim can still have a non-zero index; zero is not the default. Reconstruction error and Isolation Forest are supporting diagnostics, not direct explanations of the 0–100 index.</p>
                )}
                <div className="risk-signal-grid">
                  <div>
                    <strong>Reconstruction error</strong>
                    <span>How poorly the claim fits the model’s learned “normal claim” pattern.</span>
                  </div>
                  <div>
                    <strong>Isolation Forest</strong>
                    <span>How quickly this claim can be separated from other claims as unusual.</span>
                  </div>
                </div>
                <div className="risk-thresholds">
                  {modelEnabled?<span>Validation-selected model cutoff: <b>{(modelThreshold*100).toFixed(2)}/100</b>. Policy rules can also require review.</span>:<span>Historical expense-model score is inactive for this enterprise record.</span>}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <section className="glass-card mb-6"><h2 className="text-xl font-semibold mb-4">Company policy evidence</h2><PolicyEvidence result={data.policy} /></section>
      {/* SHAP explainability */}
      <div className="grid-cols-3 mb-6">
        <div className="col-span-2 h-[380px]" style={{ gridColumn: 'span 2' }}>
          {Object.keys(visibleShapValues || {}).length > 0 ? (
              <ShapChart
                shapValues={visibleShapValues}
                featureValues={prediction.feature_values || {}}
                maxFeatures={6}
                supervised={Boolean(prediction.feature_values?._supervised_score)}
              />
          ) : prediction ? <ReviewEvidence prediction={prediction} /> : (
            <div className="glass-card flex items-center justify-center h-full">
              <p className="text-secondary text-center px-6">This claim has not been scored yet.</p>
            </div>
          )}
        </div>

        {/* Maker-Checker Investigation / Action Drawer */}
        <div className="glass-card flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-accent-primary">
              <Shield size={20} />
              Case Review
            </h3>

            <div className="text-xs text-secondary mb-4">
              <strong>Status:</strong> <span className="badge badge-gray text-xs">{claim.case_status?.replace(/_/g, ' ')}</span>
            </div>

            {/* The checker sees the authenticated maker's recommendation. */}
            {role === 'checker' && case_review?.maker_recommendation && (
              <div className="bg-bg-surface border border-border-light rounded p-3 mb-4 text-xs">
                <div className="font-semibold text-accent-primary mb-1">Maker recommendation{case_review.maker_name ? ` · ${case_review.maker_name}` : ''}</div>
                <div className="text-secondary italic mb-2">"{case_review.maker_notes || 'No comments left.'}"</div>
                <div>Recommended: <strong>{case_review.maker_recommendation.toUpperCase()}</strong></div>
              </div>
            )}

            {noReviewNeeded
              ? <p className="review-block-message" role="status">This claim was scored below the review threshold. No maker-checker case is needed.</p>
              : reviewBlockReason && <p className="review-block-message" role="status">{reviewBlockReason}</p>}

            {!noReviewNeeded && user?.roles?.some(r=>['maker','checker','admin'].includes(r)) && <button className="btn btn-primary" onClick={openSharedReview} disabled={submittingAction}>Open shared review case</button>}
            <p className="text-secondary">Review actions and comments are handled in the shared review queue.</p>
          </div>
        </div>
      </div>

      {/* Audit Report and Case Audit Trail Timeline */}
      <div className="grid-cols-2 mb-6">
        {/* Left: AI Audit Report */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <FileText className="text-accent-primary" />
            AI Audit Report Summary
          </h3>

          {audit_report ? (
            <div className="bg-bg-surface p-6 rounded-lg border border-border-light relative overflow-hidden h-[240px] overflow-y-auto">
              <div className="absolute top-0 left-0 w-1 h-full bg-accent-primary"></div>
              <p className="text-sm italic leading-relaxed text-secondary">{audit_report.report_text}</p>
              <div className="mt-4 text-xs text-muted text-right">
                Generated by {audit_report.generated_by}
              </div>
            </div>
          ) : (
            <div className="bg-bg-surface p-6 rounded-lg border border-border-light text-center h-[240px] flex flex-col items-center justify-center gap-3">
              <p className="text-secondary italic">
                {claim.status === 'flagged' || claim.status === 'rejected'
                  ? 'No audit report has been generated for this claim yet.'
                  : 'Audit reports can be generated for flagged or rejected claims.'}
              </p>
              {(claim.status === 'flagged' || claim.status === 'rejected') && reviewerRoles.length > 0 && !review_permissions?.is_own_claim && (
                <button className="btn btn-secondary" onClick={handleGenerateReport} disabled={generatingReport}>
                  {generatingReport ? 'Generating report…' : 'Generate audit report'}
                </button>
              )}
              {reportError && <p className="text-status-danger text-xs" role="alert">{reportError}</p>}
            </div>
          )}
        </div>

        {/* Right: Append-Only Investigation Timeline */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <ClipboardList className="text-accent-primary" />
            Audit Case Timeline
          </h3>

          <div className="bg-bg-surface p-4 rounded-lg border border-border-light h-[240px] overflow-y-auto">
            {auditTrail.length === 0 ? (
              <p className="text-secondary text-center italic py-10">No investigation timeline logged.</p>
            ) : (
              <div className="timeline">
                {auditTrail.map((log, idx) => (
                  <div key={log.id || idx} className="flex gap-3 mb-4 text-xs">
                    <div className="flex flex-col items-center">
                      <div className="w-3 h-3 rounded-full bg-accent-primary"></div>
                      {idx < auditTrail.length - 1 && <div className="w-0.5 bg-border-light flex-1 my-1"></div>}
                    </div>
                    <div>
                      <div className="font-semibold text-secondary">
                        Action: <span className="text-primary uppercase">{log.action.replace(/_/g, ' ')}</span> by {log.performed_by.toUpperCase()}
                      </div>
                      {log.notes && <div className="text-muted italic mt-1">"{log.notes}"</div>}
                      <div className="text-[10px] text-muted mt-1">{new Date(log.timestamp).toLocaleString()}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
