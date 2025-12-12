# Plan for Issue #30: add support for HTTP/HTTPS proxy and SSL verification configuration

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/30

## Description
## Description

Currently, Mistral Vibe does not expose configuration options for HTTP/HTTPS proxies or SSL certificate verification in `config.toml`. This makes it difficult to use Vibe in environments that require:

1. **Proxy usage** - Users behind corporate proxies or firewalls
2. **SSL verification control** - Testing environments with self-signed certificates or custom CAs

### Current Limitations

While httpx (the underlying HTTP client) supports proxies and SSL verification settings, these cannot be configured through Vibe's configuration system. Users must resort to:
- Environment variables like `HTTP_PROXY` and `HTTPS_PROXY` (inconsistent behavior across platforms)
- Modifying environment before running Vibe

### Desired Solution

Add configuration fields to `ProviderConfig` in `config.toml`:

```toml
[[providers]]
name = "example_provider"
api_base = "https://api.example.ai/v1"
api_key_env_var = "EXAMPLE_API_KEY"
backend = "generic"
http_proxy = "http://proxy.example.com:8080"
https_proxy = "https://proxy.example.com:8443"
verify_ssl = false  # True by default if not specified
```

## Implementation Details

### Changes Required

1. **`vibe/core/config.py`**
   - Add `http_proxy: str | None = None` to `ProviderConfig`
   - Add `https_proxy: str | None = None` to `ProviderConfig`
   - Add `verify_ssl: bool | str = True` to `ProviderConfig` (supports bool or path to CA bundle)

2. **`vibe/core/llm/backend/generic.py`**
   - Update `GenericBackend.__aenter__` to pass proxy and verify_ssl to `httpx.AsyncClient`
   - Handle proxy configuration: `{"http://": proxy, "https://": proxy}`

### Example Implementation

```python
# In GenericBackend.__aenter__
if self._client is None:
    proxies = None
    if self._provider.http_proxy or self._provider.https_proxy:
        proxies = {
            "http://": self._provider.http_proxy,
            "https://": self._provider.https_proxy,
        }

    self._client = httpx.AsyncClient(
        timeout=httpx.Timeout(self._timeout),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        proxies=proxies,
        verify=self._provider.verify_ssl,  # bool or path to CA bundle
    )
```

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
