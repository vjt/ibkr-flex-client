# ibkr-flex-client

Minimal async client for IB's Flex Web Service. Extracted from
[Gastone](https://github.com/vjt/gastone) trading bot.

## What This Does

Two-step IB FlexQuery fetch (SendRequest → GetStatement) with
rate-limit retry and exponential backoff. Returns a `FlexStatement`
XML wrapper — consumers bring their own models for parsing.

## Architecture

```
FlexClient.fetch(session)
  ├─ _send_request()  → ReferenceCode  (retries on 1018)
  └─ _get_statement() → raw XML        (retries on 1018/1019)
     └─ FlexStatement(xml)             → parsed metadata + iter()
```

Three files, one concern each:
- `client.py` — HTTP flow and retry logic
- `statement.py` — XML wrapper and date parsing
- `errors.py` — `FlexError` exception

## Tech Stack

- **Python 3.12+**, async (`aiohttp`)
- **No Pydantic** — `FlexStatement` is a plain class (XML wrapping
  doesn't benefit from it). Consumers define their own Pydantic
  models for parsing XML elements.
- **stdlib logging** — no structlog. Library consumers configure
  their own handlers.

## Engineering Standards

- **Zero Gastone dependencies.** This is a standalone library.
  Never import from Gastone or add domain-specific types.
- **Minimal surface area.** Public API: `FlexClient`, `FlexStatement`,
  `FlexError`, `parse_ib_date`. That's it. Resist adding features
  that belong in the consumer.
- **aiohttp is the only runtime dependency.** Keep it that way.
  stdlib for everything else.
- Type annotations on all signatures.
- No default arguments that bypass behavior. `max_retries=10` and
  `backoff_base=10.0` are genuine production defaults, not escapes.
- Tests assert outcomes, not call sequences.

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -x -q --timeout=5
```

## Commit Messages

One logical change per commit. Message explains WHY, not WHAT.
