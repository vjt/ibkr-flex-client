# Changelog

## 0.2.0 (2026-03-27)

### Breaking changes

- `_send_request()` now returns a `SendRequestResult` dataclass instead of a
  plain `str`. This is an internal method, so external consumers are unaffected
  — the public `fetch()` API is unchanged.

### Added

- **`SendRequestResult`** dataclass: typed container for the reference code and
  download URL returned by IB's SendRequest endpoint.
- `_send_request()` now parses the `<Url>` element from the SendRequest response
  and passes it to `_get_statement()`. Previously the GetStatement URL was
  hardcoded; now it uses the URL that IB returns (falling back to the default
  gdcdyn endpoint if absent).
- **`from_date` / `to_date`** constructor parameters: optional date range
  override (yyyyMMdd format) passed as `fd`/`td` query parameters to
  SendRequest. Limited by IB to recent dates.
- `SendRequestResult` exported from the package.

### Changed

- SendRequest endpoint changed from `gdcdyn.interactivebrokers.com` to
  `ndcdyn.interactivebrokers.com` (the documented endpoint that respects
  `fd`/`td` overrides).
- `_get_statement()` now accepts a `SendRequestResult` instead of a bare
  reference code string.
