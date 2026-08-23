"""Report writers: JSON for machines, JUnit for CI, HTML for humans."""

import json
from typing import Any

from ..score.scorecard import Scorecard
from .html import to_html
from .junit import to_junit


def to_json(card: Scorecard, **extra: Any) -> str:
    payload = card.to_dict()
    payload.update(extra)
    return json.dumps(payload, indent=2, sort_keys=True)


__all__ = ["to_html", "to_json", "to_junit"]
