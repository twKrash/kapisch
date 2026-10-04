from __future__ import annotations

import re
from datetime import datetime, timezone

# RFC 3339 permits second 60 only on known leap-second days; datetime rejects 60.
# ponytail: IERS-listed leap seconds through Bulletin C 72; refresh set when IERS announces another.
_LEAP_SECOND_DAYS = frozenset(
    {
        "1972-06-30",
        "1972-12-31",
        "1973-12-31",
        "1974-12-31",
        "1975-12-31",
        "1976-12-31",
        "1977-12-31",
        "1978-12-31",
        "1979-12-31",
        "1981-06-30",
        "1982-06-30",
        "1983-06-30",
        "1985-06-30",
        "1987-12-31",
        "1989-12-31",
        "1990-12-31",
        "1992-06-30",
        "1993-06-30",
        "1994-06-30",
        "1995-12-31",
        "1997-06-30",
        "1998-12-31",
        "2005-12-31",
        "2008-12-31",
        "2012-06-30",
        "2015-06-30",
        "2016-12-31",
    }
)
# fromisoformat accepts broader ISO 8601 forms; this constrains the RFC 3339 shape.
_RFC3339_SHAPE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})"
)
_SHA256_DIGEST = re.compile(r"[0-9a-f]{64}")


def is_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256_DIGEST.fullmatch(value) is not None


def is_rfc3339_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_SHAPE.fullmatch(value):
        return False
    normalized = value[:10] + "T" + value[11:]
    if normalized[-1] in "Zz":
        normalized = normalized[:-1] + "+00:00"
    if (
        int(normalized[11:13]) > 23
        or int(normalized[14:16]) > 59
        or int(normalized[17:19]) > 60
        or int(normalized[-5:-3]) > 23
        or int(normalized[-2:]) > 59
    ):
        return False
    leap_second = normalized[17:19] == "60"
    if leap_second:
        normalized = normalized[:17] + "59" + normalized[19:]
    try:
        parsed = datetime.fromisoformat(normalized)
        if not leap_second:
            return parsed.utcoffset() is not None
        utc = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return False
    return (
        utc.hour == 23
        and utc.minute == 59
        and utc.date().isoformat() in _LEAP_SECOND_DAYS
    )
