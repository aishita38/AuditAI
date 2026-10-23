"""Master imports and automatic rule evaluation on stored data."""
from fastapi import APIRouter,Depends,File,UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.automatic_checks import after_import
from backend.app.auth.security import require_roles
from backend.app.models.master_data import MasterImportHistory
from backend.app.master_import_service import DATASETS,MAX_BYTES,import_master_csv
from backend.app.schemas.master_data import MasterImportResponse,DatasetImportStatus

router=APIRouter(prefix='/api/v1/master-data',tags=['Master data imports'])


async def do_import(dataset,file,db,user):
    content=await file.read(MAX_BYTES+1)
    report,code=import_master_csv(db,dataset,content,file.filename,user.id)
    if code!=200: return JSONResponse(status_code=code,content=report)
    if report['status'] in ('completed','partial'):
        report['checks']=after_import(db,user,dataset)
    return report


@router.post('/vendor-master/import',response_model=MasterImportResponse)
async def vendor_import(file:UploadFile=File(...),db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    return await do_import('vendor-master',file,db,user)


@router.post('/employee-roster/import',response_model=MasterImportResponse)
async def employee_import(file:UploadFile=File(...),db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    return await do_import('employee-roster',file,db,user)


@router.post('/payroll-payments/import',response_model=MasterImportResponse)
async def payroll_import(file:UploadFile=File(...),db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    return await do_import('payroll-payments',file,db,user)


@router.get('/status',response_model=list[DatasetImportStatus])
def import_status(db:Session=Depends(get_db),user=Depends(require_roles('maker','checker','admin'))):
    result=[]
    for dataset,(model,_,_) in DATASETS.items():
        query=db.query(MasterImportHistory).filter_by(dataset=dataset)
        latest=query.order_by(MasterImportHistory.id.desc()).first()
        successful=query.filter(MasterImportHistory.status.in_(['completed','partial'])).order_by(MasterImportHistory.id.desc()).first()
        result.append(dict(dataset=dataset,rows_loaded=db.query(model).count(),last_imported_at=latest.imported_at.isoformat()+'Z' if latest else None,last_import_status=latest.status if latest else None,last_successful_imported_at=successful.imported_at.isoformat()+'Z' if successful else None))
    return result
