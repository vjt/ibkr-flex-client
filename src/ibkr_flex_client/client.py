"""FlexClient — async client for IB's Flex Web Service API.

Two-step flow:
1. SendRequest with token + query_id -> SendRequestResult (ref code + download URL)
2. Poll GetStatement with reference code -> XML statement

Handles rate limiting (error 1018) and still-processing (error 1019)
with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import aiohttp

from ibkr_flex_client.errors import FlexError
from ibkr_flex_client.statement import FlexStatement

logger = logging.getLogger(__name__)

_SEND_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService.SendRequest"
_FALLBACK_GET_URL = "https://gdcdyn.interactivebrokers.com/AccountManagement/FlexWebService.GetStatement"

# IB FlexQuery API status/error constants
_STATUS_SUCCESS = "Success"
_ERROR_RATE_LIMITED = "1018"
_ERROR_STILL_PROCESSING = "1019"


@dataclass(frozen=True, slots=True)
class SendRequestResult:
    """Result of a successful SendRequest call.

    Attributes:
        reference_code: The reference code to poll GetStatement with.
        download_url: The URL to fetch the statement from, as returned
            by IB in the ``<Url>`` response element. Falls back to the
            default gdcdyn endpoint if not present.
    """

    reference_code: str
    download_url: str


class FlexClient:
    """Async client for IB's Flex Web Service API.

    Constructor injection: token and query_id from config.
    Optionally tune retry behavior via max_retries and backoff_base.
    """

    def __init__(
        self,
        *,
        token: str,
        query_id: str,
        max_retries: int = 10,
        backoff_base: float = 10.0,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> None:
        self._token = token
        self._query_id = query_id
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._from_date = from_date
        self._to_date = to_date

    async def fetch(self, session: aiohttp.ClientSession) -> FlexStatement:
        """Fetch and parse a FlexQuery statement.

        Returns a FlexStatement wrapping the XML. The caller iterates
        over elements and parses them into their own domain models.

        Raises FlexError on API errors or timeouts.
        """
        result = await self._send_request(session)
        xml_text = await self._get_statement(session, result)
        return FlexStatement(xml_text)

    async def _send_request(self, session: aiohttp.ClientSession) -> SendRequestResult:
        """Step 1: Send request, get reference code and download URL.

        Retries on 1018 (rate limit) with exponential backoff.
        """
        params: dict[str, str] = {"t": self._token, "q": self._query_id, "v": "3"}
        if self._from_date:
            params["fd"] = self._from_date
        if self._to_date:
            params["td"] = self._to_date

        max_retries = 5  # SendRequest has its own tighter limit
        for attempt in range(max_retries):
            async with session.get(_SEND_URL, params=params) as resp:
                text = await resp.text()

            root = ET.fromstring(text)

            status = root.findtext("Status")
            if status == _STATUS_SUCCESS:
                ref_code = root.findtext("ReferenceCode")
                if not ref_code:
                    raise FlexError("SendRequest returned no ReferenceCode")
                download_url = root.findtext("Url") or _FALLBACK_GET_URL
                logger.info("SendRequest OK, reference_code=%s", ref_code)
                return SendRequestResult(
                    reference_code=ref_code,
                    download_url=download_url,
                )

            error_code = root.findtext("ErrorCode", "unknown")
            error_msg = root.findtext("ErrorMessage", "unknown error")

            if error_code == _ERROR_RATE_LIMITED:
                wait = self._backoff_base * (attempt + 1)
                logger.warning(
                    "SendRequest rate-limited, attempt=%d, wait=%.0fs",
                    attempt + 1, wait,
                )
                await asyncio.sleep(wait)
                continue

            raise FlexError(
                f"SendRequest failed: [{error_code}] {error_msg}"
            )

        raise FlexError(
            f"SendRequest rate-limited after {max_retries} retries"
        )

    async def _get_statement(
        self, session: aiohttp.ClientSession, request: SendRequestResult,
    ) -> str:
        """Step 2: Poll for statement with retry on 1018/1019.

        Uses the download URL returned by SendRequest.

        1018 = rate limited (exponential backoff).
        1019 = still processing (fixed short backoff).
        """
        params = {"q": request.reference_code, "t": self._token, "v": "3"}

        for attempt in range(self._max_retries):
            async with session.get(request.download_url, params=params) as resp:
                text = await resp.text()

            # Error envelope check — real statements don't start with this tag
            if text.strip().startswith("<FlexStatementResponse"):
                root = ET.fromstring(text)
                status = root.findtext("Status")
                error_code = root.findtext("ErrorCode", "")

                if error_code in (_ERROR_RATE_LIMITED, _ERROR_STILL_PROCESSING):
                    wait = (
                        self._backoff_base * (attempt + 1)
                        if error_code == _ERROR_RATE_LIMITED
                        else self._backoff_base / 2
                    )
                    logger.warning(
                        "GetStatement retry, error_code=%s, attempt=%d, wait=%.0fs",
                        error_code, attempt + 1, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                if status != _STATUS_SUCCESS:
                    error_msg = root.findtext("ErrorMessage", "unknown")
                    raise FlexError(
                        f"GetStatement failed: [{error_code}] {error_msg}"
                    )

            # Got the actual statement XML
            logger.info("Statement received, size=%d bytes", len(text))
            return text

        raise FlexError(
            f"GetStatement timed out after {self._max_retries} retries"
        )
