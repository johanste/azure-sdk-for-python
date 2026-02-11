# Migration Guide: Converting `**kwargs` to `request_parameters` TypedDict

This guide describes how to convert Azure SDK for Python service client APIs from using
untyped `**kwargs` for request configuration to using a typed `request_parameters` dictionary.

## Overview

Previously, service client operation methods accepted infrastructure-level parameters
(headers, API version, polling configuration, etc.) through `**kwargs`. This made it
difficult for users to discover what parameters were available and caused type-checking
tools to miss errors.

The new pattern introduces `RequestParameters` TypedDict classes that explicitly declare
the available infrastructure parameters for each type of operation.

## Step-by-Step Migration

### Step 1: Create the `types` module

Create a `types.py` file in the library's package directory (next to `__init__.py`). This
module defines TypedDict classes for request parameters.

There are three tiers of TypedDict, reflecting the three categories of operations:

1. **`RequestParameters`** — base parameters common to all operations (GET, simple POST, etc.)
2. **`LRORequestParameters`** — extends `RequestParameters` with long-running operation parameters
3. **`PagingRequestParameters`** — for paginated list operations (same as `RequestParameters` but
   documents that `cls` callback receives page elements)

```python
# types.py
from typing import Any, Callable, Dict, Optional, Union

from typing_extensions import NotRequired, TypedDict

from azure.core.pipeline import PipelineResponse
from azure.core.polling import PollingMethod
from azure.core.rest import HttpRequest, HttpResponse


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

    stream: bool
    """Whether to stream the response body instead of loading it into memory."""


class LRORequestParameters(RequestParameters, total=False):
    """Parameters for long-running operations (begin_* methods).

    Extends RequestParameters with polling and continuation support.
    """

    polling: Union[bool, PollingMethod]
    """Polling strategy. True for default polling, False for no polling,
    or a custom PollingMethod instance."""

    polling_interval: int
    """Time in seconds between polling requests. Overrides the client default."""

    continuation_token: str
    """Token to resume a previously started long-running operation."""
```

### Step 2: Export types from the package

Add the TypedDict classes to the package's `__init__.py` or ensure they are importable
from a `types` submodule.

### Step 3: Add `request_parameters` to operation method signatures

For each public method in the operations classes:

**Before:**
```python
@distributed_trace
def get(
    self,
    resource_group_name: str,
    name: str,
    expand: Optional[str] = None,
    **kwargs: Any
) -> Model:
```

**After:**
```python
@distributed_trace
def get(
    self,
    resource_group_name: str,
    name: str,
    expand: Optional[str] = None,
    *,
    request_parameters: Optional[RequestParameters] = None,
    **kwargs: Any
) -> Model:
```

For LRO methods (`begin_*`), use `LRORequestParameters`:

```python
@distributed_trace
def begin_create(
    self,
    resource_group_name: str,
    name: str,
    parameters: Union[Model, IO[bytes]],
    *,
    request_parameters: Optional[LRORequestParameters] = None,
    **kwargs: Any
) -> LROPoller[Model]:
```

### Step 4: Merge `request_parameters` into kwargs at the start of each method

Add a merge step at the beginning of each method body to combine `request_parameters`
into kwargs, giving `request_parameters` lower priority (kwargs override):

```python
def get(self, ..., *, request_parameters=None, **kwargs):
    # Merge request_parameters into kwargs (kwargs take precedence)
    if request_parameters:
        for key, value in request_parameters.items():
            kwargs.setdefault(key, value)

    # Existing method body continues unchanged...
    error_map = { ... }
    error_map.update(kwargs.pop("error_map", {}) or {})
    _headers = kwargs.pop("headers", {}) or {}
    ...
```

This approach ensures:
- Full backward compatibility (`**kwargs` still works)
- `request_parameters` provides discoverability and type checking
- If both are specified, explicit `**kwargs` values take precedence

### Step 5: Update overloads

If a method has `@overload` decorators, add `request_parameters` to each overload
signature as well.

### Step 6: Update the async variant

The `aio/operations/` module mirrors the sync operations. Apply the same changes
to async method signatures.

### Step 7: Update `__init__.py` exports

Make sure the `types` module types are accessible to users:

```python
# In the package __init__.py or types module
from .types import RequestParameters, LRORequestParameters
```

## Checklist for Each Library

- [ ] Create `types.py` with `RequestParameters` and `LRORequestParameters`
- [ ] Add `request_parameters` parameter to all public sync operation methods
- [ ] Add `request_parameters` parameter to all public async operation methods
- [ ] Update `@overload` signatures if present
- [ ] Export types from package `__init__.py`
- [ ] Verify backward compatibility (existing `**kwargs` usage still works)
- [ ] Run existing tests to ensure no regressions

## Notes

- The `request_parameters` parameter is always optional and keyword-only
- All fields in the TypedDict use `total=False` (all optional)
- The method body logic is unchanged; only the signature and a small merge step are added
- This is a purely additive, non-breaking change
