"""FlexStatement — thin wrapper around IB FlexQuery XML response."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Iterator

from ibkr_flex_client.errors import FlexError


def parse_ib_date(date_str: str) -> date:
    """Parse IB's yyyyMMdd date format to a date object.

    Raises ValueError on malformed input.
    """
    return datetime.strptime(date_str, "%Y%m%d").date()


class FlexStatement:
    """Parsed IB FlexQuery statement.

    Wraps the raw XML and exposes statement metadata plus element
    iteration. The consumer defines their own models for parsing
    XML elements — this class handles the envelope only.

    Attributes:
        account_id: IB account ID from the FlexStatement element.
        from_date: Statement start date.
        to_date: Statement end date.
        xml: Raw XML string as received from IB.
    """

    __slots__ = ("account_id", "from_date", "to_date", "xml", "_root")

    def __init__(self, xml: str) -> None:
        self.xml = xml
        self._root = ET.fromstring(xml)

        stmt = self._root.find(".//FlexStatement")
        if stmt is None:
            raise FlexError("No FlexStatement element found in response")

        self.account_id: str = stmt.get("accountId", "")
        self.from_date: date = parse_ib_date(stmt.get("fromDate", ""))
        self.to_date: date = parse_ib_date(stmt.get("toDate", ""))

    def iter(self, tag: str) -> Iterator[ET.Element]:
        """Iterate over all XML elements matching *tag*."""
        return self._root.iter(tag)
