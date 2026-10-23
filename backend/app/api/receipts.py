"""
AuditAI — API endpoints for receipt upload and OCR processing.
"""
import logging
import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.config import RECEIPTS_DIR, MAX_UPLOAD_SIZE_MB
from backend.app.auth.security import assert_can_view_claim, get_current_user
from backend.app.db import get_db
from backend.app.models.auth import AuthUser, ClaimContributor
from backend.app.models.expense import ExpenseClaim, OcrResult, Receipt
from backend.app.ocr.engine import ocr_engine
from backend.app.ocr.extractor import extract_fields
from backend.app.ocr.preprocess import preprocess_image, _load_image
from backend.app.schemas.expense import OcrResultResponse, ReceiptResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/receipts", tags=["Receipts"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    file: UploadFile = File(...),
    claim_id: str = None,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """
    Upload a receipt image/PDF, run OCR + extraction, store results.

    Optionally link to a claim via claim_id query parameter.
    """
    if not file.filename:
        raise HTTPException(400, "No file provided.")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "pdf", "tiff", "bmp"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    claim = None
    if claim_id:
        claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
        if claim is None:
            raise HTTPException(404, f'Claim {claim_id} not found.')
        assert_can_view_claim(db, user, claim)

    # Save file to disk
    receipt_id = f"RCP-{uuid.uuid4().hex[:8].upper()}"
    file_type = "pdf" if ext == "pdf" else "image"
    save_dir = Path(RECEIPTS_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{receipt_id}.{ext}"

    try:
        contents = await file.read(MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
        if len(contents) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, 'Receipt exceeds the upload size limit.')
        with open(save_path, "wb") as f:
            f.write(contents)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {e}")

    # Create receipt record
    receipt = Receipt(
        receipt_id=receipt_id,
        file_path=str(save_path),
        file_type=file_type,
        upload_status="processing",
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # Run OCR pipeline
    try:
        # Preprocess
        # Neural OCR reads the original image best; aggressive binarization can
        # erase decimal points. Use preprocessing only if original OCR fails.
        preprocessed = _load_image(str(save_path))

        if preprocessed is not None:
            # OCR
            raw_text, confidence, method = ocr_engine.extract_text(preprocessed)
            if method == 'failed' or not raw_text.strip():
                raw_text, confidence, method = ocr_engine.extract_text(preprocess_image(str(save_path)))
            if method == 'failed' or not raw_text.strip():
                raise ValueError('No receipt text extracted. Check OCR installation and image quality.')

            # Structured extraction
            fields = extract_fields(raw_text, use_llm_fallback=False)

            # Store OCR result
            ocr_result = OcrResult(
                receipt_id=receipt.id,
                raw_ocr_text=raw_text,
                extracted_vendor=fields.get("vendor"),
                extracted_amount=fields.get("amount"),
                extracted_date=fields.get("date"),
                extracted_tax_id=fields.get("tax_id"),
                extracted_line_items=fields.get("line_items"),
                extraction_method=method,
                extraction_confidence=min(fields.get("confidence", 0), confidence),
            )
            db.add(ocr_result)
            receipt.ocr_result = ocr_result
            receipt.upload_status = "processed"
        else:
            receipt.upload_status = "failed"

    except Exception as e:
        logger.error("OCR processing failed for %s: %s", receipt_id, e)
        receipt.upload_status = "failed"

    # Link to claim if provided
    if claim:
        claim.receipt_id = receipt.id
        existing_contributor = db.query(ClaimContributor.id).filter(
            ClaimContributor.claim_id == claim.claim_id,
            ClaimContributor.user_id == user.id,
        ).first()
        if not existing_contributor:
            db.add(ClaimContributor(claim_id=claim.claim_id, user_id=user.id, source="receipt_upload"))
        # Existing OCR-dependent predictions are stale. Closed decisions remain
        # closed; open claims become eligible for the normal scoring endpoint.
        if claim.status not in ('approved', 'rejected'):
            if claim.prediction:
                db.delete(claim.prediction)
            claim.status = 'pending'

    if claim:
        from backend.app.models.policy import ClaimPolicy
        from backend.app.policy_service import run_checks
        p=db.get(ClaimPolicy,claim.claim_id)
        if not p: p=ClaimPolicy(claim_id=claim.claim_id,inputs={}); db.add(p)
        p.inputs={**(p.inputs or {}),'receipt_hash':hashlib.sha256(contents).hexdigest()}
        run_checks(db,True)
    db.commit()

    from backend.app.automatic_checks import after_import
    checks=after_import(db,user,'receipt',claim_ids=[claim.claim_id]) if claim and receipt.upload_status=='processed' else None
    return {
        'checks': checks,
        "status": "success" if receipt.upload_status == 'processed' else 'failed',
        "receipt_id": receipt_id,
        "upload_status": receipt.upload_status,
        "file_path": str(save_path),
    }


@router.get("/{receipt_id}", response_model=dict)
def get_receipt(receipt_id: str, db: Session = Depends(get_db),
                user: AuthUser = Depends(get_current_user)):
    """Get receipt metadata and OCR results."""
    receipt = db.query(Receipt).filter(Receipt.receipt_id == receipt_id).first()
    if not receipt:
        raise HTTPException(404, f"Receipt {receipt_id} not found.")
    if not receipt.claims:
        raise HTTPException(403, "This receipt is not linked to a claim.")
    for claim in receipt.claims:
        assert_can_view_claim(db, user, claim)

    ocr_resp = None
    if receipt.ocr_result:
        ocr = receipt.ocr_result
        ocr_resp = {
            "id": ocr.id,
            "raw_ocr_text": ocr.raw_ocr_text,
            "extracted_vendor": ocr.extracted_vendor,
            "extracted_amount": float(ocr.extracted_amount) if ocr.extracted_amount is not None else None,
            "extracted_date": ocr.extracted_date,
            "extracted_tax_id": ocr.extracted_tax_id,
            "extracted_line_items": ocr.extracted_line_items,
            "extraction_method": ocr.extraction_method,
            "extraction_confidence": ocr.extraction_confidence,
        }

    return {
        "receipt_id": receipt.receipt_id,
        "file_path": receipt.file_path,
        "file_type": receipt.file_type,
        "upload_status": receipt.upload_status,
        "uploaded_at": receipt.uploaded_at.isoformat(),
        "ocr_result": ocr_resp,
    }
