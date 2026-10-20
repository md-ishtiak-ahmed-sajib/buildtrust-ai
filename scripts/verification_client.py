"""Synthetic verification clients complete real MFA endpoints; no server bypass.

Only use in isolated test profiles. Secrets and recovery codes stay in process
memory and are never included in execution-evidence exports.
"""
import time
import httpx
import pyotp

MARKER={'X-BuildTrust-Request':'1'}


def complete_login(client,response,email,password,cache):
    if response.status_code!=200 or 'access_token' in response.json():return response
    result=response.json()
    if result.get('status') not in ('MFA_SETUP_REQUIRED','MFA_REQUIRED'):return response
    prefix='' if str(client.base_url).rstrip('/').endswith('/api/v1') else '/api/v1'
    def post(path,**kwargs):
        value=client.post(prefix+path,**kwargs)
        for _ in range(3):
            if value.status_code!=429:return value
            time.sleep(min(60,max(1,int(value.headers.get('Retry-After','1'))))+.1)
            value=client.post(prefix+path,**kwargs)
        return value
    token=result['challenge_token']
    if result['status']=='MFA_SETUP_REQUIRED':
        start=post('/auth/mfa/enroll/start',json={'challenge_token':token});start.raise_for_status();secret=start.json()['secret']
        finished=post('/auth/mfa/enroll/confirm',json={'challenge_token':token,'code':pyotp.TOTP(secret).now()});finished.raise_for_status()
        cache[email]={'secret':secret,'counter':int(time.time())//30,'codes':finished.json()['recovery_codes']}
        return finished
    state=cache.get(email)
    if not state:raise RuntimeError('Isolated verification lacks its enrolled MFA evidence. Use a fresh synthetic profile.')
    now=int(time.time())//30
    if now>state['counter']:code=pyotp.TOTP(state['secret']).now();state['counter']=now
    else:code=state['codes'].pop(0)
    finished=post('/auth/mfa/verify',json={'challenge_token':token,'code':code});finished.raise_for_status()
    if len(state['codes'])<=4:
        renewed=post('/auth/mfa/recovery-codes/regenerate',headers={'Authorization':'Bearer '+finished.json()['access_token']},json={'current_password':password,'code':state['codes'].pop(0)})
        renewed.raise_for_status();state['codes']=renewed.json()['recovery_codes'];finished=renewed
    return finished


class VerificationClient(httpx.Client):
    def __init__(self,*args,**kwargs):
        kwargs['headers']={**kwargs.get('headers',{}),**MARKER};super().__init__(*args,**kwargs);self.mfa_cache={}

    def post(self,url,*,complete_mfa=True,**kwargs):
        result=super().post(url,**kwargs)
        if complete_mfa and str(url).endswith('/auth/login'):
            data=kwargs.get('json') or {}
            return complete_login(self,result,data.get('email'),data.get('password'),self.mfa_cache)
        return result
