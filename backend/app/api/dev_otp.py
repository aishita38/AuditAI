"""Opt-in loopback-only developer sign-in. The displayed OTP is not a production factor."""
import os
import secrets
from collections import deque
from threading import Lock
from time import monotonic
from datetime import datetime,timedelta
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models.auth import AuthUser,AuthSession
from backend.app.auth.security import normalize_company_email,token_digest,user_payload,SESSION_HOURS

router=APIRouter(prefix='/api/v1/auth/dev-otp',tags=['Local developer login'])
_lock=Lock()
_challenges={}
_requests=deque()
_clock=monotonic
TTL_SECONDS=120


def local_enabled(request):
    if os.getenv('AUDITAI_DEV_OTP','').lower() not in ('1','true'):return False
    if not request.client or request.client.host not in ('127.0.0.1','::1'):return False
    if request.url.hostname not in ('localhost','127.0.0.1','::1'):return False
    origin=request.headers.get('origin')
    if origin and origin not in ('http://localhost:5173','http://127.0.0.1:5173','http://[::1]:5173'):return False
    return True


def require_local(request):
    if not local_enabled(request):raise HTTPException(404,'Developer OTP is unavailable.')


class Generate(BaseModel):
    email:str=Field(min_length=3,max_length=254)


class Verify(BaseModel):
    challenge_id:str=Field(min_length=10,max_length=100)
    otp:str=Field(pattern=r'^\d{6}$')


@router.get('/status')
def status(request:Request,response:Response,db:Session=Depends(get_db)):
    response.headers['Cache-Control']='no-store'
    enabled=local_enabled(request)
    accounts=[]
    if enabled:
        for u in db.query(AuthUser).filter(AuthUser.active.is_(True)).order_by(AuthUser.email).all():
            try: normalize_company_email(u.email)
            except ValueError:continue
            accounts.append(dict(email=u.email,name=u.display_name,roles=u.roles))
    return dict(enabled=enabled,accounts=accounts)


@router.post('/generate')
def generate(body:Generate,request:Request,response:Response,db:Session=Depends(get_db)):
    require_local(request)
    response.headers['Cache-Control']='no-store'
    now=_clock()
    with _lock:
        while _requests and _requests[0]<=now-60:_requests.popleft()
        if len(_requests)>=30:raise HTTPException(429,'Too many OTP requests. Try again in a minute.')
        _requests.append(now)
        for cid in list(_challenges):
            if _challenges[cid]['expires']<=now:_challenges.pop(cid)
    try:email=normalize_company_email(body.email)
    except ValueError:raise HTTPException(401,'Developer account unavailable.')
    user=db.query(AuthUser).filter_by(email=email,active=True).first()
    if not user:raise HTTPException(401,'Developer account unavailable.')
    cid=secrets.token_urlsafe(24);otp=f'{secrets.randbelow(1000000):06d}'
    with _lock:
        for old in list(_challenges):
            if _challenges[old]['user_id']==user.id:_challenges.pop(old)
        _challenges[cid]=dict(user_id=user.id,hash=token_digest(cid+':'+otp),expires=now+TTL_SECONDS,attempts=0)
    return dict(challenge_id=cid,otp=otp,expires_in=TTL_SECONDS)


@router.post('/verify')
def verify(body:Verify,request:Request,response:Response,db:Session=Depends(get_db)):
    require_local(request)
    response.headers['Cache-Control']='no-store'
    with _lock:
        challenge=_challenges.get(body.challenge_id)
        if not challenge or challenge['expires']<=_clock():
            _challenges.pop(body.challenge_id,None)
            raise HTTPException(401,'OTP expired or already used. Generate a new one.')
        challenge['attempts']+=1
        valid=secrets.compare_digest(challenge['hash'],token_digest(body.challenge_id+':'+body.otp))
        if not valid:
            if challenge['attempts']>=5:_challenges.pop(body.challenge_id,None)
            raise HTTPException(401,'Incorrect OTP. Generate a new one if needed.')
        user_id=challenge['user_id'];_challenges.pop(body.challenge_id)
    user=db.query(AuthUser).filter_by(id=user_id,active=True).first()
    if not user:raise HTTPException(401,'Developer account unavailable.')
    try:normalize_company_email(user.email)
    except ValueError:raise HTTPException(401,'Developer account unavailable.')
    token=secrets.token_urlsafe(32)
    user.failed_attempts=0;user.locked_until=None
    db.add(AuthSession(user_id=user.id,token_hash=token_digest(token),expires_at=datetime.utcnow()+timedelta(hours=SESSION_HOURS)))
    db.commit()
    return dict(access_token=token,token_type='bearer',user=user_payload(user))
