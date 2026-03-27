"""Tests for FlexStatement XML wrapper."""

from __future__ import annotations

from datetime import date

import pytest

from ibkr_flex_client import FlexError, FlexStatement, parse_ib_date

STATEMENT_WITH_TRADES = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexQueryResponse queryName="Test Trades" type="AF">
<FlexStatements count="1">
<FlexStatement accountId="U1234567" fromDate="20250304" toDate="20260304">
<Trades>
<Trade currency="EUR" symbol="IGLD" conid="123456" quantity="10" />
<Trade currency="GBP" symbol="CSPX" conid="234567" quantity="5" />
<Trade currency="GBP" symbol="CSPX" conid="234567" quantity="3" />
</Trades>
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>"""

STATEMENT_EMPTY = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexQueryResponse queryName="Test" type="AF">
<FlexStatements count="1">
<FlexStatement accountId="U9999999" fromDate="20260101" toDate="20260301">
<Trades />
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>"""

STATEMENT_WITH_NAV = """\
<?xml version="1.0" encoding="utf-8"?>
<FlexQueryResponse queryName="Test NAV" type="AF">
<FlexStatements count="1">
<FlexStatement accountId="U1234567" fromDate="20260101" toDate="20260301">
<EquitySummaryInBase>
<EquitySummaryByReportDateInBase reportDate="20260201" total="50000" cash="10000" stock="40000" />
<EquitySummaryByReportDateInBase reportDate="20260202" total="51000" cash="9000" stock="42000" />
</EquitySummaryInBase>
<ConversionRates>
<ConversionRate fromCurrency="GBP" reportDate="20260201" rate="1.26" />
<ConversionRate fromCurrency="EUR" reportDate="20260201" rate="1.08" />
</ConversionRates>
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>"""


class TestFlexStatement:
    def test_metadata_parsed(self) -> None:
        stmt = FlexStatement(STATEMENT_WITH_TRADES)
        assert stmt.account_id == "U1234567"
        assert stmt.from_date == date(2025, 3, 4)
        assert stmt.to_date == date(2026, 3, 4)

    def test_raw_xml_preserved(self) -> None:
        stmt = FlexStatement(STATEMENT_WITH_TRADES)
        assert stmt.xml is STATEMENT_WITH_TRADES

    def test_iter_trades(self) -> None:
        stmt = FlexStatement(STATEMENT_WITH_TRADES)
        trades = list(stmt.iter("Trade"))
        assert len(trades) == 3
        assert trades[0].get("symbol") == "IGLD"
        assert trades[1].get("symbol") == "CSPX"
        assert trades[2].get("quantity") == "3"

    def test_iter_empty_section(self) -> None:
        stmt = FlexStatement(STATEMENT_EMPTY)
        trades = list(stmt.iter("Trade"))
        assert trades == []

    def test_iter_nav_entries(self) -> None:
        stmt = FlexStatement(STATEMENT_WITH_NAV)
        entries = list(stmt.iter("EquitySummaryByReportDateInBase"))
        assert len(entries) == 2
        assert entries[0].get("total") == "50000"

    def test_iter_conversion_rates(self) -> None:
        stmt = FlexStatement(STATEMENT_WITH_NAV)
        rates = list(stmt.iter("ConversionRate"))
        assert len(rates) == 2
        assert rates[0].get("fromCurrency") == "GBP"

    def test_no_flex_statement_raises(self) -> None:
        with pytest.raises(FlexError, match="No FlexStatement"):
            FlexStatement("<FlexQueryResponse></FlexQueryResponse>")

    def test_bad_date_raises(self) -> None:
        xml = """\
<FlexQueryResponse>
<FlexStatements count="1">
<FlexStatement accountId="U1" fromDate="garbage" toDate="20260101">
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>"""
        with pytest.raises(ValueError):
            FlexStatement(xml)

    def test_metadata_from_empty_statement(self) -> None:
        stmt = FlexStatement(STATEMENT_EMPTY)
        assert stmt.account_id == "U9999999"
        assert stmt.from_date == date(2026, 1, 1)
        assert stmt.to_date == date(2026, 3, 1)


class TestParseIbDate:
    def test_valid(self) -> None:
        assert parse_ib_date("20260315") == date(2026, 3, 15)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_ib_date("not-a-date")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_ib_date("")
