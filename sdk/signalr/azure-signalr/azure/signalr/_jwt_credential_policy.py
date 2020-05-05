import datetime
import jwt
from azure.core.credentials import AzureKeyCredential
from azure.core.pipeline import PipelineRequest
from azure.core.pipeline.policies import SansIOHTTPPolicy
class JwtCredentialPolicy(SansIOHTTPPolicy):

    NAME_CLAIM_TYPE = 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name'

    def __init__(self, credential, user=None):
        self._credential= credential
        self._user = user

    def on_request(self, request):
        # type: (PipelineRequest) -> Union[None, Awaitable[None]]
        """Is executed before sending the request from next policy.

        :param request: Request to be modified before sent from next policy.
        :type request: ~azure.core.pipeline.PipelineRequest
        """
        request.http_request.headers['Authorization'] = 'Bearer ' + self._encode(request.http_request.url)

    def _encode(self, url):
        # type: (AzureKeyCredential) -> str
        data = {
                'aud': url,
                'exp': datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds=10),   
        }
        if self._user:
            data[self.NAME_CLAIM_TYPE] = self._user

        return jwt.encode(
            payload=data,
            key=self._credential.key,
            algorithm='HS256',
        ).decode(encoding='utf8')