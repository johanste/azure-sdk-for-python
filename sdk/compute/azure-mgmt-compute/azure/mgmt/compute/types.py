# ---------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# ---------------------------------------------------------------------------

"""Typed dictionaries for service client request parameters.

These TypedDict classes provide explicit typing for the infrastructure-level
parameters that control how HTTP requests are constructed and sent through
the Azure SDK pipeline. They replace the untyped ``**kwargs`` pattern for
better discoverability and type-checking support.
"""

from typing import Callable, Dict, List, Union

from typing_extensions import TypedDict

from azure.core.pipeline import PipelineRequest, PipelineResponse
from azure.core.polling import PollingMethod


class RequestParameters(TypedDict, total=False):
    """Common parameters for all service client operations.

    These parameters control how the HTTP request is constructed and sent
    through the Azure SDK pipeline, including retry, redirect, tracing,
    logging, and transport-level behavior.
    """

    # -- Request construction --

    api_version: str
    """Override the API version used for this request."""

    headers: Dict[str, str]
    """Custom HTTP headers to include in the request."""

    params: Dict[str, str]
    """Custom query parameters to include in the request."""

    content_type: str
    """Override the Content-Type header for the request."""

    request_id: str
    """Custom request ID to set in the request header
    (consumed by :class:`~azure.core.pipeline.policies.RequestIdPolicy`)."""

    # -- Response handling --

    stream: bool
    """Whether to stream the response body instead of loading it into memory."""

    decompress: bool
    """Whether to decompress the response body. Defaults to ``True``."""

    # -- Hooks --

    raw_request_hook: Callable[[PipelineRequest], None]
    """Callback invoked with the :class:`~azure.core.pipeline.PipelineRequest`
    before the request is sent
    (consumed by :class:`~azure.core.pipeline.policies.CustomHookPolicy`)."""

    raw_response_hook: Callable[[PipelineResponse], None]
    """Callback invoked with the :class:`~azure.core.pipeline.PipelineResponse`
    after the response is received
    (consumed by :class:`~azure.core.pipeline.policies.CustomHookPolicy`)."""

    # -- Logging --

    logging_enable: bool
    """Enable HTTP logging for this request
    (consumed by :class:`~azure.core.pipeline.policies.HttpLoggingPolicy`).
    Defaults to ``False``."""

    # -- Retry policy --

    retry_total: int
    """Total number of retries to allow
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``10``."""

    retry_connect: int
    """Number of connection-related retries
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``3``."""

    retry_read: int
    """Number of retries on read errors
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``3``."""

    retry_status: int
    """Number of retries on bad status codes
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``3``."""

    retry_backoff_factor: float
    """Backoff factor for retry delays
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``0.8``."""

    retry_backoff_max: int
    """Maximum backoff time in seconds
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``120``."""

    retry_on_methods: List[str]
    """HTTP methods that are eligible for retry
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`)."""

    timeout: int
    """Overall timeout for the operation in seconds, including all retries
    (consumed by :class:`~azure.core.pipeline.policies.RetryPolicy`).
    Defaults to ``604800`` (7 days)."""

    # -- Redirect policy --

    permit_redirects: bool
    """Whether to follow redirects
    (consumed by :class:`~azure.core.pipeline.policies.RedirectPolicy`).
    Defaults to ``True``."""

    redirect_max: int
    """Maximum number of redirects to follow
    (consumed by :class:`~azure.core.pipeline.policies.RedirectPolicy`).
    Defaults to ``30``."""

    # -- Distributed tracing --

    network_span_namer: Callable[..., str]
    """Callable that receives the HTTP request and returns a span name string
    (consumed by :class:`~azure.core.pipeline.policies.DistributedTracingPolicy`)."""

    tracing_attributes: Dict[str, str]
    """Extra attributes to set on the tracing span
    (consumed by :class:`~azure.core.pipeline.policies.DistributedTracingPolicy`)."""

    # -- Transport / connection --

    connection_timeout: float
    """Connection timeout in seconds
    (consumed by the HTTP transport)."""

    read_timeout: float
    """Read timeout in seconds
    (consumed by the HTTP transport)."""

    connection_verify: Union[bool, str]
    """SSL certificate verification. Pass ``False`` to disable,
    or a path to a CA bundle
    (consumed by the HTTP transport)."""

    connection_cert: Union[str, tuple]
    """Client-side certificate. A path to a file or a ``(cert, key)`` tuple
    (consumed by the HTTP transport)."""

    proxy: str
    """Proxy URL for this request
    (consumed by the HTTP transport)."""


class LRORequestParameters(RequestParameters, total=False):
    """Parameters for long-running operations (``begin_*`` methods).

    Extends :class:`RequestParameters` with polling and continuation support.
    """

    polling: Union[bool, PollingMethod]
    """Polling strategy. ``True`` for default polling, ``False`` for no polling,
    or a custom :class:`~azure.core.polling.PollingMethod` instance."""

    polling_interval: int
    """Time in seconds between polling requests. Overrides the client default."""

    continuation_token: str
    """Token to resume a previously started long-running operation."""
