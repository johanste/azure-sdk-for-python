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

from typing import Dict, Union

from typing_extensions import TypedDict

from azure.core.polling import PollingMethod


class RequestParameters(TypedDict, total=False):
    """Common parameters for all service client operations.

    These parameters control how the HTTP request is constructed and sent
    through the Azure SDK pipeline.
    """

    api_version: str
    """Override the API version used for this request."""

    headers: Dict[str, str]
    """Custom HTTP headers to include in the request."""

    params: Dict[str, str]
    """Custom query parameters to include in the request."""

    content_type: str
    """Override the Content-Type header for the request."""


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
