"""Authenticator policy and short atomic verification; no second-factor bypass."""
import hashlib
import secrets
import time
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,delete
from cryptography.fernet import Fernet,InvalidToken
import pyotp
from .mfa_models import MfaFactor,MfaChallenge,MfaRecoveryCode
from .money import utcnow
from .security import DomainError,revoke_sessions
from . import audit,payments


def public_profile(settings):
    from .public_demo import PublicDemoSettings
    return isinstance(settings,PublicDemoSettings)


def required(settings,user):
    return not public_profile(settings) and user.role in ('ADMIN','FINANCE_MANAGER')


def key(settings,*,create=False):
    from .private_storage import private_path,protect_file
    path=private_path(settings.data_dir,'mfa-encryption-key')
    if not path.exists():
        if not create:raise DomainError(503,'MFA_KEY_UNAVAILABLE','Restore the private MFA key from backup. No factor has been removed.')
        # A missing key must not silently orphan existing factors.
        from .database import make_engine,transaction
        engine=make_engine(settings.data_dir/'buildtrust.db')
        try:
            with transaction(engine) as session:
                if session.scalar(select(MfaFactor.user_id).limit(1)) or session.scalar(select(MfaChallenge.id).where(MfaChallenge.pending_secret.is_not(None)).limit(1)):
                    raise DomainError(503,'MFA_KEY_UNAVAILABLE','Restore the private MFA key from backup.')
        finally:engine.dispose()
        try:
            import os
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            try:
                protect_file(path)
                os.write(descriptor,Fernet.generate_key())
            finally:os.close(descriptor)
        except FileExistsError:pass
    protect_file(path)
    try:return Fernet(path.read_bytes())
    except (ValueError,TypeError):raise DomainError(503,'MFA_KEY_UNAVAILABLE','The private MFA key is unavailable or invalid.')


def decrypt(settings,value):
    try:return key(settings).decrypt(value.encode()).decode()
    except InvalidToken:raise DomainError(503,'MFA_KEY_UNAVAILABLE','The private MFA key cannot decrypt this factor. Restore the matching backup.')


def needs_second_factor(session,settings,user):
    return not public_profile(settings) and (required(settings,user) or session.get(MfaFactor,user.id) is not None)


def issue(session,user,purpose):
    now=utcnow()
    session.execute(delete(MfaChallenge).where(MfaChallenge.expires_at<now))
    for prior in session.scalars(select(MfaChallenge).where(MfaChallenge.user_id==user.id,MfaChallenge.consumed_at.is_(None))):
        prior.consumed_at=now;prior.pending_secret=None
    token=secrets.token_urlsafe(32)
    expiry=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat().replace('+00:00','Z')
    session.add(MfaChallenge(id=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,user_version=user.version,purpose=purpose,expires_at=expiry))
    return {'status':'MFA_SETUP_REQUIRED' if purpose=='ENROLL' else 'MFA_REQUIRED','challenge_token':token,'expires_in':300}


def challenge(session,token,purpose):
    from .models import User
    row=session.get(MfaChallenge,hashlib.sha256(token.encode()).hexdigest())
    user=session.get(User,row.user_id) if row else None
    if not row or row.purpose!=purpose or row.consumed_at or row.expires_at<=utcnow() or row.attempts>=5 or not user or not user.active or row.user_version!=user.version:
        raise DomainError(401,'MFA_CHALLENGE_INVALID','The sign-in step is invalid or expired. Start again.')
    return row,user


def consume_factor(session,settings,user,code):
    factor=session.get(MfaFactor,user.id)
    if not factor:return False
    value=code.strip().replace('-','')
    if len(value)==6 and value.isdigit():
        totp=pyotp.TOTP(decrypt(settings,factor.encrypted_secret));now=int(time.time())//30
        for counter in (now,now-1,now+1):
            if counter>factor.last_counter and secrets.compare_digest(totp.at(counter*30),value):
                factor.last_counter=counter;return True
        return False
    row=session.get(MfaRecoveryCode,hashlib.sha256(value.encode()).hexdigest())
    if row and row.user_id==user.id and not row.consumed_at:
        row.consumed_at=utcnow();return True
    return False


def recovery_codes(session,user):
    session.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id))
    codes=[secrets.token_hex(16) for _ in range(10)]
    for code in codes:session.add(MfaRecoveryCode(user_id=user.id,code_hash=hashlib.sha256(code.encode()).hexdigest()))
    return ['-'.join(code[i:i+8] for i in range(0,32,8)) for code in codes]


def reset_factor(session,user,actor=None,*,owner=False):
    if not owner:raise DomainError(403,'OWNER_RECOVERY_REQUIRED','Only the local owner may reset a lost authenticator.')
    session.execute(delete(MfaFactor).where(MfaFactor.user_id==user.id))
    session.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id))
    for row in session.scalars(select(MfaChallenge).where(MfaChallenge.user_id==user.id)):
        row.consumed_at=utcnow();row.pending_secret=None
    user.version+=1;revoke_sessions(session,user.id);payments.invalidate_authority(session,actor,user.id)
    audit.append(session,actor,'MFA_RESET','user',user.id,{'local_owner':True})
