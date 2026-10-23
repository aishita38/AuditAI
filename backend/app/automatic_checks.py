"""Run the relevant detectors after committed imports; review decisions stay manual."""
import logging
from threading import RLock
from backend.app.models.master_finding import MasterFinding  # register before create_all
from backend.app.master_rule_service import run
from backend.app.api.master_checks import write_lock
logger=logging.getLogger(__name__)
claim_lock=RLock()


def after_import(db,user,source,claim_ids=None):
    stages=[]
    def attempt(name,fn):
        try:
            result=fn();db.commit();stages.append(dict(result or {},detector=name,status='completed'))
        except Exception as exc:
            db.rollback();logger.exception('Automatic %s failed after %s import',name,source)
            message=getattr(exc,'detail',None)
            stages.append(dict(detector=name,status='failed',message=str(message or 'Check could not complete. Imported data is saved; retry checks.')))
    if source in ('vendor-master','employee-roster','payroll-payments','all'):
        datasets=['vendor','payroll'] if source=='all' else ['vendor'] if source=='vendor-master' else ['payroll']
        for dataset in datasets:
            def masters(dataset=dataset):
                with write_lock:
                    result=run(db,dataset);db.commit()
                    return dict(finding_count=len(result['items']),availability=result['statuses'],missing_datasets=result['missing_datasets'])
            attempt(dataset,masters)
    if source in ('claims','receipt','all') and (claim_ids or source=='all'):
        def model():
            from backend.app.api.fraud import score_selected_claims
            with claim_lock:return score_selected_claims(db,user,claim_ids=claim_ids)
        attempt('expense_model',model)
    if source in ('transfers','claims','receipt','all') and any(role in ('admin','maker','checker') for role in user.roles):
        def transfer_checks():
            from backend.app.api.transfers import cycles
            from backend.app.api.reconciliation import reconciliation
            circular=cycles(7,4,db,user);reconciled=reconciliation(db,user)
            return dict(circular_findings=len(circular['cycles']),reconciliation_findings=sum(bool(r['flags']) for r in reconciled['items']),search_limited=circular.get('search_limited',False))
        attempt('bank_transfers',transfer_checks)
    return dict(status='completed' if all(s['status']=='completed' for s in stages) else 'partial',stages=stages)
