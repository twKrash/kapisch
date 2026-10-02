from __future__ import annotations

import json
from typing import Any

from ._authority import _unique_pairs
from .bundle import canonical_json

def _json(data: bytes, label: str) -> Any:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is malformed JSON") from error
    if canonical_json(value) != data:
        raise ValueError(f"{label} is not canonical JSON")
    return value
