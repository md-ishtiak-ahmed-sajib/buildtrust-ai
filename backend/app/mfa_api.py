"""Restricted second-factor endpoints; enrollment secrets never enter logs or URLs."""
import base64
from typing import Literal
from io import BytesIO
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel,ConfigDict,Field
import pyotp
import qrcode
from . import mfa,audit,payments
from .mfa_models import MfaFactor
from .database import transaction
from .security import DomainError,passwords,revoke_sessions,token_for
from .money import utcnow
from .admission import consume
from .api_support import user_view
from .schemas import LoginResponse


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')

class MfaChallengeResponse(Contract):
    status: Literal['MFA_SETUP_REQUIRED','MFA_REQUIRED']
    challenge_token: str
    expires_in: int

class EnrollmentInput(Contract):
    challenge_token: str | None = Field(default=None,min_length=20,max_length=128)
    current_password: str | None = Field(default=None,min_length=1,max_length=128)
    code: str | None = Field(default=None,min_length=6,max_length=64)

class EnrollmentResponse(MfaChallengeResponse):
    secret: str
    provisioning_uri: str
    qr_png_base64: str

class VerificationInput(Contract):
    challenge_token: str = Field(min_length=20,max_length=128)
    code: str = Field(min_length=6,max_length=64)

class FactorProof(Contract):
    current_password: str = Field(min_length=1,max_length=128)
    code: str = Field(min_length=6,max_length=64)

class Completed(LoginResponse):
    recovery_codes: list[str] = Field(default_factory=list)

class MfaStatus(Contract):
    enabled: bool
    required: bool
    public_demo: bool
    recovery_codes_remaining: int

class Message(Contract):
    message: str

def complete(session,request,user,*,codes=None):
    return {'access_token':token_for(user,request.app.state.secret,session,mfa_verified=True),'token_type':'bearer','expires_in':1800,'user':user_view(user,request.app.state.settings),'recovery_codes':codes or []}

def admission(request,group):
    address=request.client.host if request.client else 'local'
    consume(request.app.state.engine,[(f'mfa-ip:{address}',20,60),(f'mfa-operation:{group}:{address}',10,60)])

def available(request):
    if mfa.public_profile(request.app.state.settings):raise DomainError(403,'PUBLIC_DEMO_MFA','The separate public demo keeps its fixed README login flow.')

def create_router(context):
    router=APIRouter(prefix='/api/v1/auth/mfa',tags=['Authenticator security'])

    @router.get('/status',response_model=MfaStatus)
    def status(request:Request):
        from sqlalchemy import select,func
        from .mfa_models import MfaRecoveryCode
        with context(request) as (session,user):
            return {'enabled':session.get(MfaFactor,user.id) is not None,'required':mfa.required(request.app.state.settings,user),'public_demo':mfa.public_profile(request.app.state.settings),'recovery_codes_remaining':session.scalar(select(func.count()).select_from(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id,MfaRecoveryCode.consumed_at.is_(None)))}

    @router.post('/enroll/start',response_model=EnrollmentResponse)
    async def enrollment(data:EnrollmentInput,request:Request):
        available(request);admission(request,'enroll')
        settings,engine=request.app.state.settings,request.app.state.engine
        if data.challenge_token:
            if data.current_password is not None or data.code is not None:raise DomainError(422,'MFA_INPUT','Use the enrollment challenge or password confirmation, not both.')
            with transaction(engine) as session:mfa.challenge(session,data.challenge_token,'ENROLL')
            cipher=mfa.key(settings,create=True)
            with transaction(engine,True) as session:
                row,user=mfa.challenge(session,data.challenge_token,'ENROLL')
                if session.get(MfaFactor,user.id):raise DomainError(409,'MFA_CHANGED','Restart sign-in to verify the current authenticator.')
                token=data.challenge_token
                if row.pending_secret:secret=mfa.decrypt(settings,row.pending_secret)
                else:secret=pyotp.random_base32();row.pending_secret=cipher.encrypt(secret.encode()).decode()
        else:
            with context(request) as (session,user):identity,version,old=user.id,user.version,user.password_hash
            consume(engine,[(f'mfa-account:{identity}',5,60)])
            if not data.current_password or not await run_in_threadpool(passwords.verify,data.current_password,old):raise DomainError(403,'INVALID_PASSWORD','Current password is incorrect.')
            cipher=mfa.key(settings,create=True)
            with context(request,True) as (session,user):
                if user.version!=version or user.password_hash!=old:raise DomainError(409,'VERSION_CONFLICT','Account changed; sign in again.')
                if session.get(MfaFactor,user.id) and (not data.code or not mfa.consume_factor(session,settings,user,data.code)):raise DomainError(403,'MFA_CODE_INVALID','A current authenticator or unused recovery code is required.')
                response=mfa.issue(session,user,'ENROLL');token=response['challenge_token'];session.flush()
                row,_=mfa.challenge(session,token,'ENROLL');secret=pyotp.random_base32();row.pending_secret=cipher.encrypt(secret.encode()).decode()
        uri=pyotp.TOTP(secret).provisioning_uri(name=user.email,issuer_name='BuildTrust AI')
        stream=BytesIO();qrcode.make(uri).save(stream,format='PNG')
        return {'status':'MFA_SETUP_REQUIRED','challenge_token':token,'expires_in':300,'secret':secret,'provisioning_uri':uri,'qr_png_base64':base64.b64encode(stream.getvalue()).decode()}

    def finish(data,request,enroll):
        available(request);admission(request,'verify')
        engine,settings=request.app.state.engine,request.app.state.settings
        with transaction(engine) as session:
            _,user=mfa.challenge(session,data.challenge_token,'ENROLL' if enroll else 'VERIFY');identity=user.id
        consume(engine,[(f'mfa-account:{identity}',5,60)])
        denied=False;result=None
        with transaction(engine,True) as session:
            row,user=mfa.challenge(session,data.challenge_token,'ENROLL' if enroll else 'VERIFY')
            if enroll:
                secret=mfa.decrypt(settings,row.pending_secret) if row.pending_secret else None
                counter=None
                if secret and data.code.isdigit() and len(data.code)==6:
                    import time
                    now=int(time.time())//30
                    counter=next((c for c in (now,now-1,now+1) if pyotp.TOTP(secret).at(c*30)==data.code),None)
                valid=counter is not None
            else:valid=mfa.consume_factor(session,settings,user,data.code)
            if not valid:
                row.attempts+=1;denied=True
                audit.append(session,user,'MFA_VERIFICATION_FAILED','user',user.id,{'purpose':row.purpose})
            else:
                row.consumed_at=utcnow();codes=[]
                if enroll:
                    factor=session.get(MfaFactor,user.id)
                    if not factor:factor=MfaFactor(user_id=user.id,encrypted_secret=row.pending_secret,last_counter=counter);session.add(factor)
                    else:factor.encrypted_secret=row.pending_secret;factor.last_counter=counter;factor.enabled_at=utcnow()
                    row.pending_secret=None;user.version+=1;revoke_sessions(session,user.id);payments.invalidate_authority(session,user,user.id)
                    codes=mfa.recovery_codes(session,user)
                audit.append(session,user,'MFA_ENROLLED' if enroll else 'MFA_LOGIN','user',user.id)
                result=complete(session,request,user,codes=codes)
        if denied:raise DomainError(401,'MFA_CODE_INVALID','The code is invalid, expired or already used.')
        return result

    @router.post('/enroll/confirm',response_model=Completed)
    def confirm(data:VerificationInput,request:Request):return finish(data,request,True)

    @router.post('/verify',response_model=Completed)
    def verify(data:VerificationInput,request:Request):return finish(data,request,False)

    async def manage(data,request,disable):
        available(request);admission(request,'manage')
        with context(request) as (session,user):
            if disable and mfa.required(request.app.state.settings,user):raise DomainError(403,'MFA_REQUIRED','Your role requires MFA and cannot disable it.')
            identity,version,old=user.id,user.version,user.password_hash
        consume(request.app.state.engine,[(f'mfa-account:{identity}',5,60)])
        if not await run_in_threadpool(passwords.verify,data.current_password,old):raise DomainError(403,'INVALID_PASSWORD','Current password is incorrect.')
        with context(request,True) as (session,user):
            if user.version!=version or user.password_hash!=old:raise DomainError(409,'VERSION_CONFLICT','Account changed; sign in again.')
            if not mfa.consume_factor(session,request.app.state.settings,user,data.code):raise DomainError(403,'MFA_CODE_INVALID','A current authenticator or unused recovery code is required.')
            if disable:
                from sqlalchemy import delete
                from .mfa_models import MfaRecoveryCode
                session.execute(delete(MfaFactor).where(MfaFactor.user_id==user.id));session.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id))
            user.version+=1;revoke_sessions(session,user.id);payments.invalidate_authority(session,user,user.id)
            audit.append(session,user,'MFA_DISABLED' if disable else 'MFA_CODES_REGENERATED','user',user.id)
            return {'message':'MFA disabled. Sign in again.'} if disable else complete(session,request,user,codes=mfa.recovery_codes(session,user))

    @router.post('/recovery-codes/regenerate',response_model=Completed)
    async def regenerate(data:FactorProof,request:Request):return await manage(data,request,False)

    @router.post('/disable',response_model=Message)
    async def disable(data:FactorProof,request:Request):return await manage(data,request,True)

    return router
