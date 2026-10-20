"""Same-origin browser requests and explicit non-browser mutation admission."""
import json
from urllib.parse import urlsplit


class RequestSecurity:
    def __init__(self,app,settings):self.app,self.settings=app,settings

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]));path=scope.get('path','');method=scope['method']
        code,message,status=None,None,403
        try:
            host=urlsplit('http://'+headers.get(b'host',b'').decode()).hostname
            if not host or host not in self.settings.trusted_hosts:
                code,message,status='UNTRUSTED_HOST','This host is not configured for the local application.',400
        except ValueError:code,message,status='UNTRUSTED_HOST','This host is not configured for the local application.',400
        if code is None and path.startswith('/api/'):
            origin=headers.get(b'origin');site=headers.get(b'sec-fetch-site',b'').decode()
            if origin is not None and origin.decode() not in self.settings.trusted_origins:
                code,message='UNTRUSTED_ORIGIN','The request origin is not allowed.'
            elif method in ('POST','PUT','PATCH','DELETE'):
                if site=='cross-site' or (site=='same-site' and origin is None):
                    code,message='CROSS_SITE_REQUEST','Browser actions require a trusted origin.'
                elif headers.get(b'x-buildtrust-request')!=b'1':
                    code,message='REQUEST_MARKER_REQUIRED','Mutating API calls require X-BuildTrust-Request: 1.'
        if code is None and path.lower().endswith('.map'):
            code,message,status='NOT_FOUND','Production source maps are not served.',404
        if code:
            payload=json.dumps({'error':{'code':code,'message':message,'request_id':scope.get('request_id')}}).encode()
            await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff')]})
            return await send({'type':'http.response.body','body':payload})
        return await self.app(scope,receive,send)
