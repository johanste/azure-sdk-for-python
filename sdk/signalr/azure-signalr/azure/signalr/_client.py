import typing # pylint: disable=unused-import
import msrest
import azure.core as core
import azure.core.exceptions as exceptions
from azure.core.credentials import AzureKeyCredential
from azure.core.pipeline import policies, transport
from azure.core.tracing.decorator import distributed_trace
from . import _generated
from ._jwt_credential_policy import JwtCredentialPolicy

def _create_policies(creds, user, **kwargs):
    # type: (AzureKeyCredential, **typing.Any) -> typing.List[Any]
    return [
        policies.HeadersPolicy(**kwargs),
        policies.UserAgentPolicy(base_user_agent=''), # BUGBUG: Provide correct user agent base...
        policies.ProxyPolicy(**kwargs),
        policies.ContentDecodePolicy(**kwargs),
        policies.RedirectPolicy(**kwargs),
        policies.RetryPolicy(**kwargs),
        JwtCredentialPolicy(creds, user, **kwargs),
        policies.CustomHookPolicy(**kwargs),
        policies.DistributedTracingPolicy(**kwargs),
        policies.NetworkTraceLoggingPolicy(**kwargs),
        policies.HttpLoggingPolicy(**kwargs),
    ]

def _parse_connection_string(connection_string):
    # type: (str) -> typing.Dict[str, str]
    try:
        parts = [
            part.split("=", maxsplit=1) for part in connection_string.split(";") if part
        ]
        parsed = {name: value for name, value in parts}
    except ValueError:
        raise ValueError("Invalid connection string '{0}'".format(connection_string))

    if not "endpoint" in parsed or not "key" in parsed:
        raise ValueError(
            "Missing 'key' or 'endpoint' in connection string '{0}'".format(
                connection_string
            )
        )
    return parsed


def _data_from_message(message):
    # type: (typing.Any) -> str
    try:
        return message.read()
    except AttributeError:
        return message


class SignalRClient(object):
    """Client for communicating with the SignalR HTTP/REST APIs.
    """

    def __init__(self, endpoint, credentials, **kwargs):
        # type: (str, AzureKeyCredential, **typing.Any) -> None
        """Create a new SignalRClient instance

        :param endpoint: Endpoint to connect to.
        :type endpoint: str
        :param credentials: Credentials to use to connect to endpoint.
        :type credentials: ~azure.core.credentials.AzureKeyCredentials
        :keyword hub: Optional hub to connect to.
        :type hub: str
        :keyword api_version: Api version to use when communicating with the service.
        :type api_version: str
        """
        self._endpoint = endpoint
        self._hub = kwargs.pop("hub", None)
        self._credentials = credentials
        self._user = kwargs.pop('user', None)
        self._client = core.PipelineClient(
            endpoint, policies=_create_policies(credentials, self._user, **kwargs)
        )

        # BUGBUG: Operations classes should be clients (have the same signature). Autorest improvement.
        self._operations = _generated.operations.WebSocketConnectionApiOperations(
            self._client, None, msrest.Serializer(), msrest.Deserializer()
        )
        self._health_operations = _generated.operations.HealthApiOperations(
            self._client, None, msrest.Serializer(), msrest.Deserializer()
        )

        assert self._client
        assert self._operations

    @classmethod
    def from_connectionstring(cls, connection_string, **kwargs):
        # type: (str, **Any) -> SignalRClient
        """Create a new SignalRClient instance

        :param connection_string: Connection string to access the signalR service.
        :type connection_string: str
        :keyword hub: Optional hub to connect to.
        :type hub: str
        :keyword api_version: Api version to use when communicating with the service.
        :type api_version: str
        """
        parsed_connection_string = _parse_connection_string(connection_string)
        creds = AzureKeyCredential(parsed_connection_string.pop("key"))
        parsed_connection_string.update(**kwargs)
        return cls(credentials=creds, **parsed_connection_string)

    @distributed_trace
    def close_connection(self, connection_id, **kwargs):
        # type: (str, typing.Optional[str]) -> None
        """Close the given connection

        :param connection_id: Id of connection to close
        :type connection_id: str
        :keyword reason: [Optional] the reason the connection is closed.
        :type reason: str
        """
        kwargs.setdefault("reason", None)
        self._operations.delete_close_client_connection(
            self._hub, connection_id, **kwargs
        )

    @distributed_trace
    def connection_exists(self, connection_id, **kwargs):
        # type: (str, **Any) -> bool
        """Check if the given connection exists

        :param connection_id: Id of connection to look for
        :type connection_id: str
        """
        try:
            self._operations.head_check_default_hub_connection_existence(
                connection_id, **kwargs
            )
            return True
        except exceptions.ResourceNotFoundError:
            return False

    @distributed_trace
    def group_exists(self, group, **kwargs):
        # type: (str, **Any) -> bool
        """Check if the given group exists.

        :param group: The group to look for.
        :type group: str
        :rtype: bool
        """
        try:
            self._operations.head_check_default_hub_group_existence(group, **kwargs)
            return True
        except exceptions.ResourceNotFoundError:
            return False

    @distributed_trace
    def user_exists(self, user, **kwargs):
        # type: (str, **Any) -> bool
        """Check if the given user exists.

        :param user: Name of user to check if it exists.
        :type user: str
        :rtype: bool
        """
        try:
            self._operations.head_check_default_hub_user_existence(user, **kwargs)
            return True
        except exceptions.ResourceNotFoundError:
            return False

    @distributed_trace
    def remove_user(self, user, **kwargs):
        # type: (str, **Any) -> None
        """Remove the given user.

        :param user: Name of user to remove
        :type user: str
        """
        self._operations.delete_remove_user_from_all_default_hub_groups(user, **kwargs)

    @distributed_trace
    def send_to_all(self, message, **kwargs):
        # type: (typing.Union[str, typing.IO], **Any) -> None
        """Broadcast message to all.

        :param message: Message to send.
        :type message: typing.Union[str, typing.IO]
        :keyword excluded: Exclude these recipients.
        :type excluded: typing.List[str]
        :rtype: None
        """
        kwargs.setdefault("excluded", None)
        if self._hub:
            self._operations.post_broadcast(
                self._hub, _data_from_message(message), **kwargs
            )
        else:
            self._operations.post_default_hub_broadcast(
                _data_from_message(message), **kwargs
            )

    @distributed_trace
    def send_to_connection(self, connection_id, message, **kwargs):
        # type: (str, typing.Union[str, typing.IO], **Any) -> None
        """Send message to the given ~connection_id

        :param connection_id: ID of connection to send message to.
        :type connection_id: str
        :param message: Message to send.
        :type message: typing.Union[str, typing.IO]
        """
        self._operations.post_send_to_connection(
            self._hub, connection_id, _data_from_message(message), **kwargs
        )

    @distributed_trace
    def send_to_user(self, user, message, **kwargs):
        # type: (str, typing.Union[str, typing.IO], **Any) -> None
        """Send message to the given ~user

        :param user: User to send message to.
        :type user: str
        :param message: Message to send.
        :type message: typing.Union[str, typing.IO]
        """
        self._operations.post_send_to_user(
            self._hub, user, _data_from_message(message), **kwargs
        )

    @distributed_trace
    def get_group_client(self, group, **kwargs):
        # type: (str, **Any) -> SignalRGroupClient
        """Retrive a client connected to the given ~group.

        :param group: Group to connect to.
        :type group: str
        :rtype: SignalRGroupClient
        """
        return SignalRGroupClient(
            self._endpoint,
            self._credentials,
            group,
            hub=self._hub,
            _client=self._client,  # Share the client...
            **kwargs
        )

    @distributed_trace
    def is_available(self, **kwargs):
        # type: (**Any) -> bool
        """Check if the service is available/healthy.

        :retval: True if service is healthy/available, False otherwise.
        :rtype: bool
        """
        try:
            # BUGBUG: Should autorest generate code that return False on head/404
            self._health_operations.head_index(**kwargs)
            return True
        except exceptions.ResourceNotFoundError:
            return False


class SignalRGroupClient(object):
    """Client for communicating to a specific group using the SignalR REST/HTTP interface.
    """

    def __init__(self, endpoint, credentials, group, hub, **kwargs):
        # type: (str, AzureKeyCredential, str, str, **typing.Any) -> None
        """Create a new SignalRClient associated to a specific group

        :param endpoint: Endpoint to connect to.
        :type endpoint: str
        :param credentials: Credentials to use.
        :type credentials: ~azure.core.credentials.AzureKeyCredential
        :param group: Group to connect to.
        :type group: str
        :param hub: Hub to connect to.
        :type hub: str
        :rtype: None
        """
        self._endpoint = endpoint
        self._credentials = credentials
        self._hub = hub
        self._group = group
        self._client = kwargs.pop("_client", None)
        self._user = kwargs.pop('user', None)
        if not self._client:
            self._client = core.PipelineClient(
                endpoint, policies=_create_policies(credentials, self._user, **kwargs)
            )
        self._operations = _generated.operations.WebSocketConnectionApiOperations(
            self._client, None, msrest.Serializer(), msrest.Deserializer()
        )

    @classmethod
    def from_connection_string(cls, connection_string, group, **kwargs):
        # type: (str, str, **typing.Any) -> SignalRGroupClient
        """Create a SignalRGroupClient from a connection string.

        :param connection_string: Connection string
        :type connection_string: str
        :param group: Group to connect to.
        :type group: str
        :keyword hub: Optional Hub to attach to
        :type hub: str
        :rtype: SignalRGroupClient
        :retval: New client.
        """
        parsed_connection_string = _parse_connection_string(connection_string)
        creds = AzureKeyCredential(key=parsed_connection_string.pop("key"))
        parsed_connection_string.update(**kwargs)
        return SignalRGroupClient(credentials=creds, group=group, **parsed_connection_string)

    @distributed_trace
    def add_connection(self, connection_id, **kwargs):
        # type: (str, **typing.Any) -> None
        """Add a connection to this group.

        :param connection_id: Connection id to add.
        :type connection_id: str
        """
        if self._hub:
            self._operations.put_add_connection_to_group(
                self._hub, self._group, connection_id, **kwargs
            )
        else:
            self._operations.put_add_connection_to_default_hub_group(
                self._group, connection_id, **kwargs
            )

    @distributed_trace
    def add_user(self, user, **kwargs):
        # type: (str, **typing.Any) -> None
        """Add user to the group

        :param user: User to add.
        :type user: str
        :keyword ttl: If specified, time for the user to remain in the group (in seconds).
        :type ttl: int
        """
        kwargs.setdefault("ttl", None)
        if self._hub:
            self._operations.put_add_user_to_group(self._hub, self._group, user, **kwargs)
        else:
            self._operations.put_add_user_to_default_hub_group(self._group, user, **kwargs)

    @distributed_trace
    def remove_user(self, user, **kwargs):
        # type: (str, **typing.Any) -> None
        """Remove user from the group

        :param user: User to remove.
        :type user: str
        """
        self._operations.delete_remove_user_from_group(
            self._hub, self._group, user, **kwargs
        )

    @distributed_trace
    def close_connection(self, connection_id, **kwargs):
        # type: (str, typing.Optional[str], **typing.Any) -> None
        """Close the given connection

        :param connection_id: Id of connection to close.
        :type connection_id: str
        :keyword reason: Reason to close the connection.
        :type reason: str
        :rtype: None
        """
        kwargs.setdefault("reason", None)
        self._operations.delete_close_client_connection(
            self._hub, connection_id, **kwargs
        )

    @distributed_trace
    def user_exists(self, user, **kwargs):
        # type: (str, **typing.Any) -> bool
        """Does the given user exist in this group.

        :param user: Name of user to look for.
        :type user: str
        :rtype: bool
        """
        # BUGBUG: AutoRest Python CodeGen does not return boolean for HEAD/exists methods.
        # This may be a swagger issue
        try:
            if self._hub:
                self._operations.head_check_user_existence_in_group(
                    self._hub, self._group, user, **kwargs
                )
            else:
                self._operations.head_check_user_existence_in_default_hub_group(
                    self._group, user, **kwargs
                )
            return True
        except exceptions.ResourceNotFoundError:
            return False

    @distributed_trace
    def send(self, message, **kwargs):
        # type: (typing.Union[str, typing.IO], **typing.Any) -> None
        """Broadcast message to this group.

        :param message: Message to send.
        :type message: typing.Union[str, typing.IO],
        :keyword excluded: Exclude these recipients.
        :type excluded: typing.List[str]
        :rtype: None
        """
        self._operations.post_group_broadcast(
            self._hub, self._group, _data_from_message(message), **kwargs
        )
