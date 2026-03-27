"""Tests for FlexClient — retry logic, error handling, fetch flow."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from ibkr_flex_client import FlexClient, FlexError

# --- Sample XML responses ---

SEND_REQUEST_OK = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexStatementResponse timestamp="27 March, 2026 10:00 AM EST">
<Status>Success</Status>
<ReferenceCode>REF123456</ReferenceCode>
<Url>https://example.com/GetStatement</Url>
</FlexStatementResponse>"""

SEND_REQUEST_AUTH_ERROR = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexStatementResponse>
<Status>Fail</Status>
<ErrorCode>1012</ErrorCode>
<ErrorMessage>Token has expired</ErrorMessage>
</FlexStatementResponse>"""

SEND_REQUEST_RATE_LIMITED = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexStatementResponse>
<Status>Warn</Status>
<ErrorCode>1018</ErrorCode>
<ErrorMessage>Too many requests</ErrorMessage>
</FlexStatementResponse>"""

GET_STATEMENT_STILL_PROCESSING = """\
<FlexStatementResponse>
<Status>Warn</Status>
<ErrorCode>1019</ErrorCode>
<ErrorMessage>Statement generation in progress.</ErrorMessage>
</FlexStatementResponse>"""

GET_STATEMENT_ERROR = """\
<FlexStatementResponse>
<Status>Fail</Status>
<ErrorCode>1020</ErrorCode>
<ErrorMessage>Invalid reference code</ErrorMessage>
</FlexStatementResponse>"""

VALID_STATEMENT = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexQueryResponse queryName="Test" type="AF">
<FlexStatements count="1">
<FlexStatement accountId="U7777777" fromDate="20260101" toDate="20260327">
<Trades>
<Trade symbol="SPY" quantity="100" />
</Trades>
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>"""


def _mock_response(text: str) -> AsyncMock:
    """Create a mock aiohttp response that returns *text*."""
    resp = AsyncMock()
    resp.text = AsyncMock(return_value=text)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_session(*responses: str) -> MagicMock:
    """Create a mock session that returns responses in order."""
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[_mock_response(r) for r in responses]
    )
    return session


class TestFlexClientFetch:
    async def test_happy_path(self) -> None:
        session = _mock_session(SEND_REQUEST_OK, VALID_STATEMENT)
        client = FlexClient(token="tok", query_id="qid")

        stmt = await client.fetch(session)

        assert stmt.account_id == "U7777777"
        assert stmt.from_date == date(2026, 1, 1)
        trades = list(stmt.iter("Trade"))
        assert len(trades) == 1
        assert trades[0].get("symbol") == "SPY"

    async def test_auth_error_raises(self) -> None:
        session = _mock_session(SEND_REQUEST_AUTH_ERROR)
        client = FlexClient(token="bad", query_id="qid")

        with pytest.raises(FlexError, match="Token has expired"):
            await client.fetch(session)


class TestSendRequestRetry:
    async def test_rate_limit_then_success(self) -> None:
        session = _mock_session(
            SEND_REQUEST_RATE_LIMITED,
            SEND_REQUEST_OK,
            VALID_STATEMENT,
        )
        client = FlexClient(token="tok", query_id="qid", backoff_base=0.01)

        stmt = await client.fetch(session)
        assert stmt.account_id == "U7777777"
        # 3 calls: rate-limited SendRequest, success SendRequest, GetStatement
        assert session.get.call_count == 3

    async def test_rate_limit_exhausted(self) -> None:
        # 5 rate-limited responses (SendRequest max_retries=5)
        session = _mock_session(*([SEND_REQUEST_RATE_LIMITED] * 5))
        client = FlexClient(token="tok", query_id="qid", backoff_base=0.01)

        with pytest.raises(FlexError, match="rate-limited after 5"):
            await client.fetch(session)

    async def test_no_reference_code_raises(self) -> None:
        bad_response = """\
<FlexStatementResponse>
<Status>Success</Status>
</FlexStatementResponse>"""
        session = _mock_session(bad_response)
        client = FlexClient(token="tok", query_id="qid")

        with pytest.raises(FlexError, match="no ReferenceCode"):
            await client.fetch(session)


class TestGetStatementRetry:
    async def test_still_processing_then_success(self) -> None:
        session = _mock_session(
            SEND_REQUEST_OK,
            GET_STATEMENT_STILL_PROCESSING,
            VALID_STATEMENT,
        )
        client = FlexClient(token="tok", query_id="qid", backoff_base=0.01)

        stmt = await client.fetch(session)
        assert stmt.account_id == "U7777777"
        assert session.get.call_count == 3

    async def test_get_statement_error_raises(self) -> None:
        session = _mock_session(SEND_REQUEST_OK, GET_STATEMENT_ERROR)
        client = FlexClient(token="tok", query_id="qid")

        with pytest.raises(FlexError, match="Invalid reference code"):
            await client.fetch(session)

    async def test_get_statement_timeout(self) -> None:
        session = _mock_session(
            SEND_REQUEST_OK,
            *([GET_STATEMENT_STILL_PROCESSING] * 3),
        )
        client = FlexClient(
            token="tok", query_id="qid",
            max_retries=3, backoff_base=0.01,
        )

        with pytest.raises(FlexError, match="timed out after 3"):
            await client.fetch(session)
