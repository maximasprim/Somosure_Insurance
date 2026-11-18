"""Reads the weekly report straight from a Google Sheet.

The sheet is downloaded as an .xlsx through Google's own export address, so the importer receives exactly what
it receives when someone uploads the workbook by hand - every tab, every column.

Access: the sheet's sharing must be "Anyone with the link can view". (A sheet that is private to named people needs
a Google login this system does not hold; the error below says so rather than guessing.)

Safety: the address that is fetched is *built here* from the sheet's id, which must be letters, digits, '-' and '_'.
Whatever else is typed into the link box is never requested, so the link cannot be used to make the server call
some other address.
"""

from __future__ import annotations

import re

import httpx

MAX_BYTES = 15 * 1024 * 1024  # the importer's own upload limit
TIMEOUT = httpx.Timeout(60.0, connect=15.0)

_LINK = re.compile(r"^https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,120})(?:[/?#].*)?$")
_ID = re.compile(r"^[A-Za-z0-9_-]{20,120}$")
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{30,120}$")  # a bare id must look like a real one (they are 44 characters)


class SheetLinkError(ValueError):
    """The text typed in is not a link to a Google Sheet."""


class SheetFetchError(RuntimeError):
    """Google would not give the file, or what came back is not a workbook. The message is safe to show staff."""


def parse_sheet_link(text: str) -> str:
    """The sheet id from a Google Sheets link (or from the bare id)."""
    value = (text or "").strip()
    match = _LINK.match(value)
    if match:
        return match.group(1)
    if _BARE_ID.match(value):
        return value
    if "drive.google.com" in value:
        raise SheetLinkError(
            "That is a Google Drive file link. Open the file as a Google Sheet (File > Save as Google Sheets) "
            "and paste the address that starts with https://docs.google.com/spreadsheets/d/..."
        )
    raise SheetLinkError("Paste the Google Sheet's address - it starts with https://docs.google.com/spreadsheets/d/")


def export_url(sheet_id: str) -> str:
    if not _ID.match(sheet_id or ""):
        raise SheetLinkError("Not a valid Google Sheet id.")
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"


async def fetch_workbook(sheet_id: str, *, client: httpx.AsyncClient | None = None) -> bytes:
    """Downloads the sheet as .xlsx bytes. Raises SheetFetchError with a plain-language reason."""
    url = export_url(sheet_id)
    owns = client is None
    client = client or httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT)
    try:
        try:
            async with client.stream("GET", url) as response:
                status = response.status_code
                content_type = response.headers.get("content-type", "")
                if status in (401, 403) or "accounts.google.com" in str(response.url):
                    raise SheetFetchError(_PRIVATE)
                if status == 404:
                    raise SheetFetchError("Google says that sheet does not exist. Check the link, or whether the sheet was deleted.")
                if status == 429:
                    raise SheetFetchError("Google is rate-limiting the download. It will be tried again later.")
                if status != 200:
                    raise SheetFetchError(f"Google answered with an error ({status}). It will be tried again later.")
                if "text/html" in content_type.lower():
                    raise SheetFetchError(_PRIVATE)
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise SheetFetchError("The sheet is larger than the 15MB import limit.")
                    chunks.append(chunk)
        except httpx.TimeoutException:
            raise SheetFetchError("Google took too long to answer. It will be tried again later.")
        except httpx.HTTPError as exc:
            raise SheetFetchError(f"Could not reach Google ({type(exc).__name__}). It will be tried again later.")
    finally:
        if owns:
            await client.aclose()

    data = b"".join(chunks)
    if not data.startswith(b"PK"):  # an .xlsx is a zip file
        raise SheetFetchError("What Google returned is not an Excel workbook. Check that the link is to a Google Sheet.")
    return data


_PRIVATE = (
    "The sheet is private. In Google Sheets choose Share > General access > \"Anyone with the link\" > Viewer, "
    "then try again."
)
