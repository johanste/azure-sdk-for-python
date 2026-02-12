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

    api_version: str
    headers: Dict[str, str]
    params: Dict[str, str]
    content_type: str
    request_id: str
    stream: bool
    decompress: bool
    raw_request_hook: Callable[[PipelineRequest], None]
    raw_response_hook: Callable[[PipelineResponse], None]
    logging_enable: bool
    retry_total: int
    retry_connect: int
    retry_read: int
    retry_status: int
    retry_backoff_factor: float
    retry_backoff_max: int
    retry_on_methods: List[str]
    timeout: int
    permit_redirects: bool
    redirect_max: int
    network_span_namer: Callable
    tracing_attributes: Dict[str, str]
    connection_timeout: float
    read_timeout: float
    connection_verify: Union[bool, str]
    connection_cert: Union[str, tuple]
    proxy: str


class LRORequestParameters(RequestParameters, total=False):
    """Parameters for long-running operations (begin_* methods).

    Extends RequestParameters with polling and continuation support.
    """

    polling: Union[bool, PollingMethod]
    polling_interval: int
    continuation_token: str
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

**Precedence rule**: When a user passes the same parameter through both
`request_parameters` and `**kwargs`, the `**kwargs` value wins. This is because
`setdefault` only sets a key if it's not already present in `kwargs`. This behavior
is intentional — it allows `request_parameters` to provide defaults while explicit
keyword arguments can still override them. Example:

```python
# In this call, headers from **kwargs wins:
client.vms.get("rg", "vm", request_parameters={"headers": {"X-From-RP": "1"}}, headers={"X-From-KW": "1"})
# Result: headers = {"X-From-KW": "1"}
```

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
