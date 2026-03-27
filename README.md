# ibkr-flex-client

Minimal async Python client for Interactive Brokers'
[Flex Web Service](https://www.interactivebrokers.com/en/software/am/am/reports/activityflexqueries.htm).

Handles the two-step API flow (SendRequest → GetStatement) with
automatic retry on rate limits and processing delays. Returns a
thin XML wrapper — you bring your own Pydantic models for parsing.

## Prerequisites

You need a **Flex Web Service token** and at least one **query ID**
from IB Account Management → Reports → Flex Queries → Flex Web
Service. The token is account-scoped; each query ID corresponds to
a specific report configuration.

## Installation

```bash
pip install -e path/to/ibkr-flex-client
```

Or as a git submodule:

```bash
git submodule add git@github.com:vjt/ibkr-flex-client.git vendor/ibkr-flex-client
pip install -e vendor/ibkr-flex-client
```

Requires Python 3.12+ and `aiohttp`.

## Usage

```python
import aiohttp
from ibkr_flex_client import FlexClient, FlexStatement, FlexError

async def main():
    client = FlexClient(token="YOUR_TOKEN", query_id="YOUR_QUERY_ID")

    async with aiohttp.ClientSession() as session:
        statement: FlexStatement = await client.fetch(session)

    # Statement metadata
    print(statement.account_id)  # "U1234567"
    print(statement.from_date)   # date(2026, 1, 1)
    print(statement.to_date)     # date(2026, 3, 27)

    # Iterate over XML elements and parse into your own models
    for elem in statement.iter("Trade"):
        symbol = elem.get("symbol")
        quantity = float(elem.get("quantity", "0"))
        price = float(elem.get("tradePrice", "0"))
        print(f"{symbol}: {quantity} @ {price}")

    # Raw XML is available if needed
    print(len(statement.xml), "bytes")
```

## API

### `FlexClient(*, token, query_id, max_retries=10, backoff_base=10.0)`

Async client for IB's Flex Web Service.

- **token**: Flex Web Service token from IB Account Management.
- **query_id**: Flex Query ID for the specific report.
- **max_retries**: Max poll attempts for GetStatement (default 10).
- **backoff_base**: Base seconds for exponential backoff (default 10).

#### `await client.fetch(session) -> FlexStatement`

Fetches the report. Handles rate limiting (IB error 1018) and
still-processing (1019) with automatic retry. Raises `FlexError`
on auth failures, timeouts, or malformed responses.

### `FlexStatement(xml)`

Thin wrapper around the IB FlexQuery XML response.

| Attribute    | Type   | Description                          |
|-------------|--------|--------------------------------------|
| `account_id`| `str`  | IB account ID                        |
| `from_date` | `date` | Statement start date                 |
| `to_date`   | `date` | Statement end date                   |
| `xml`       | `str`  | Raw XML string                       |

#### `statement.iter(tag) -> Iterator[Element]`

Iterates all XML elements matching `tag`. Use this to extract
trade fills, NAV entries, conversion rates, or any other section
from the Flex report. Element attributes are strings — cast them
to your own types.

### `FlexError`

Exception raised on all API and parsing errors.

### `parse_ib_date(date_str) -> date`

Parses IB's `yyyyMMdd` format. Raises `ValueError` on bad input.

## Error Handling

IB's Flex Web Service has aggressive rate limiting. The client
handles this transparently:

| IB Error | Meaning          | Client Behavior                    |
|----------|------------------|------------------------------------|
| 1018     | Rate limited     | Exponential backoff, retry          |
| 1019     | Still processing | Fixed short backoff, retry          |
| 1012     | Token expired    | Raises `FlexError` immediately      |
| Other    | Various failures | Raises `FlexError` immediately      |

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -x -q
```

## License

MIT
