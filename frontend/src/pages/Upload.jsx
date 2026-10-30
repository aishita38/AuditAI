import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { claimsApi, fraudApi, receiptsApi } from '../api/client';
import FileUpload from '../components/FileUpload';
import MasterDataImport from '../components/MasterDataImport';
import AutomaticCheckResult from '../components/AutomaticCheckResult';
import { Play } from 'lucide-react';
import { isReviewer, useAuth } from '../auth/AuthContext';
import { useAuditProfile } from '../context/AuditProfileContext';

export default function Upload() {
  const [csvUploadState, setCsvUploadState] = useState('idle');
  const [rcpUploadState, setRcpUploadState] = useState('idle');
  const [rcpClaimId, setRcpClaimId] = useState('');
  const [receiptData, setReceiptData] = useState(null);
  const [message, setMessage] = useState(null);
  const [scoring, setScoring] = useState(false);
  const [automaticChecks,setAutomaticChecks]=useState(null);

  const navigate = useNavigate();
  const { user } = useAuth();
  const { profile, companyName, currency } = useAuditProfile();

  const handleCsvUpload = async (file) => {
    setCsvUploadState('uploading');
    setMessage(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await claimsApi.upload(formData);
      setCsvUploadState('complete');setAutomaticChecks(res.data.checks);
      setMessage({ type: 'success', text: res.data.message });
    } catch (err) {
      console.error(err);
      setCsvUploadState('error');
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || "Upload failed. Check file format."
      });
    }
  };

  const handleReceiptUpload = async (file) => {
    if (!rcpClaimId.trim()) {
      setRcpUploadState('error');
      setMessage({ type: 'error', text: 'Enter the existing Target Claim ID before uploading a receipt so the OCR evidence can be linked and scored.' });
      return;
    }
    setRcpUploadState('processing');
    setMessage(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await claimsApi.uploadReceipt(rcpClaimId, formData);
      if (res.data.upload_status !== 'processed') {
        throw new Error('Receipt saved, but OCR could not read it. Try a clearer single-page image or PDF.');
      }
      setAutomaticChecks(res.data.checks);
      const receiptResponse = await receiptsApi.get(res.data.receipt_id);
      setReceiptData(receiptResponse.data);
      setRcpUploadState('complete');
      setMessage({ type: 'success', text: `Receipt processed: ${res.data.receipt_id}. OCR fields are shown below. Relevant checks ran automatically. See the check status below.` });
    } catch (err) {
      console.error(err);
      setRcpUploadState('error');
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message || "Receipt upload failed." });
    }
  };

  const runScoring = async () => {
    setScoring(true);
    setMessage({ type: 'info', text: 'Running Autoencoder + Isolation Forest scoring pipeline...' });
    try {
      const res = await fraudApi.score();
      if (!res.data.scored_count) {
        setMessage({
          type: 'error',
          text: 'No pending claims were found to score. Upload a claims file or attach the receipt to a valid Target Claim ID first.'
        });
        return;
      }
      setMessage({
        type: 'success',
        text: `Scoring complete! Scored ${res.data.scored_count} claims. Found ${res.data.flagged_count} anomalies.`
      });
      setTimeout(() => navigate('/claims'), 3000);
    } catch (err) {
      console.error(err);
      setMessage({ type: 'error', text: err.response?.data?.detail || "Scoring pipeline failed. Try retraining the model first." });
    } finally {
      setScoring(false);
    }
  };

  return (
    <div className="main-content">
      {/* Header Context */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-sm text-muted">
          <span>Global Auditing</span>
          <span>/</span>
          <span className="text-secondary font-medium">{companyName} · {currency}</span>
        </div>
        <span
          className="badge text-xs"
          style={{ background: `${profile.color}20`, color: profile.color, border: `1px solid ${profile.color}40` }}
        >
          {profile.name}
        </span>
      </div>

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data Ingestion</h1>
          <p className="text-xs text-secondary mt-1">
            Upload expense batches, attach receipt evidence for OCR, and synchronize reference datasets.
          </p>
        </div>
      </div>

      {message && (
        <div className={`glass-card mb-6 flex items-center p-4 border-l-4 ${message.type === 'error' ? 'border-status-danger' :
            message.type === 'success' ? 'border-status-success' : 'border-accent-primary'
          }`}>
          <span className="text-sm">{message.text}</span>
        </div>
      )}

      {/* Main Upload Cards */}
      <div className="grid-cols-2 mb-6">
        <div className="glass-card">
          <h3 id="expense-import" className="text-lg font-semibold mb-1">1. Upload Expense Claims</h3>
          <p className="text-secondary text-xs mb-5">Upload employee expense claim CSV records for ML anomaly scoring.</p>

          <FileUpload
            label="Upload claims.csv"
            accept=".csv,.json"
            onUpload={handleCsvUpload}
            uploadState={csvUploadState}
          />
        </div>

        <div className="glass-card">
          <h3 id="receipt-import" className="text-lg font-semibold mb-1">2. Upload Receipt (Optional)</h3>
          <p className="text-secondary text-xs mb-5">Attach an invoice or receipt image to an existing claim for OCR text & amount extraction.</p>

          <div className="mb-4">
            <label className="text-xs text-secondary mb-1 block font-medium">Target Claim ID</label>
            <input
              type="text"
              className="input text-sm"
              placeholder="e.g. CLM-00001"
              value={rcpClaimId}
              onChange={(e) => setRcpClaimId(e.target.value)}
            />
          </div>

          <FileUpload
            label="Upload receipt image/PDF"
            accept="image/*,application/pdf"
            onUpload={handleReceiptUpload}
            uploadState={rcpUploadState}
          />

          {receiptData?.ocr_result && (
            <div className="glass-card mt-5" style={{ padding: '16px' }}>
              <div className="flex justify-between items-center mb-3">
                <h4 className="font-semibold text-accent-primary text-sm">OCR Extraction Result</h4>
                <span className="badge badge-green text-xs">Processed</span>
              </div>
              <div className="grid-cols-2 gap-3 text-xs">
                <div><span className="text-secondary">Vendor:</span> <div className="font-medium text-primary">{receiptData.ocr_result.extracted_vendor || 'Not detected'}</div></div>
                <div><span className="text-secondary">Amount:</span> <div className="font-medium text-primary">{receiptData.ocr_result.extracted_amount != null ? `₹${Number(receiptData.ocr_result.extracted_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : 'Not detected'}</div></div>
                <div><span className="text-secondary">Date:</span> <div className="font-medium text-primary">{receiptData.ocr_result.extracted_date || 'Not detected'}</div></div>
                <div><span className="text-secondary">Confidence:</span> <div className="font-medium text-primary">{receiptData.ocr_result.extraction_confidence != null ? `${Math.round(receiptData.ocr_result.extraction_confidence * 100)}%` : 'Not available'}</div></div>
              </div>
              {receiptData.ocr_result.raw_ocr_text && (
                <details className="mt-3">
                  <summary className="text-xs text-muted cursor-pointer hover:text-secondary">View raw OCR text</summary>
                  <pre className="mono-pre mt-2 text-xs p-2 rounded" style={{ whiteSpace: 'pre-wrap', maxHeight: '120px' }}>{receiptData.ocr_result.raw_ocr_text}</pre>
                </details>
              )}
            </div>
          )}
        </div>
      </div>

      {isReviewer(user) && <MasterDataImport/>}
      <AutomaticCheckResult checks={automaticChecks}/>

      {isReviewer(user) && (csvUploadState === 'complete' || rcpUploadState === 'complete') && (
        <div className="glass-card mb-6 flex items-center justify-between gap-5" style={{ padding: '18px 24px' }}>
          <div>
            <h3 className="font-semibold text-sm">Automated screening triggers after upload</h3>
            <p className="text-xs text-secondary mt-0.5">The pipeline combines claim metadata, vendor master checks, and any OCR extraction evidence.</p>
          </div>
          <button className="btn btn-primary text-xs" onClick={runScoring} disabled={scoring}>
            <Play size={15} />
            <span>{scoring ? 'Scoring…' : 'Run Pending Claim Scoring'}</span>
          </button>
        </div>
      )}

      <div className="glass-card">
        <h3 className="text-base font-semibold mb-4">Pipeline Status</h3>
        <div className="flex items-center justify-between text-xs">
          <div className={`flex flex-col items-center ${csvUploadState === 'complete' ? 'text-status-success' : 'text-muted'}`}>
            <div className="w-3.5 h-3.5 rounded-full bg-current mb-1.5"></div>
            <span>Data Ingestion</span>
          </div>
          <div className="h-px bg-border-light flex-1 mx-3"></div>
          <div className={`flex flex-col items-center ${rcpUploadState === 'complete' ? 'text-status-success' : 'text-muted'}`}>
            <div className="w-3.5 h-3.5 rounded-full bg-current mb-1.5"></div>
            <span>OCR Extraction</span>
          </div>
          <div className="h-px bg-border-light flex-1 mx-3"></div>
          <div className="flex flex-col items-center text-muted">
            <div className="w-3.5 h-3.5 rounded-full bg-current mb-1.5"></div>
            <span>Feature Engineering</span>
          </div>
          <div className="h-px bg-border-light flex-1 mx-3"></div>
          <div className="flex flex-col items-center text-muted">
            <div className="w-3.5 h-3.5 rounded-full bg-current mb-1.5"></div>
            <span>ML Scoring</span>
          </div>
        </div>
      </div>
    </div>
  );
}
