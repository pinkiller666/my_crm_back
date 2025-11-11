# backend/common/datetime.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from django.utils import timezone


def ensure_timezone(dt: Optional[datetime], *, tz=None) -> Optional[datetime]:
    """Return a timezone-aware datetime in the requested timezone.

    * Converts naive values to the current timezone (or provided `tz`).
    * Normalises aware values to the provided timezone when requested.
    * Leaves ``None`` untouched.
    """
    if dt is None:
        return None

    tz = tz or timezone.get_current_timezone()

    if timezone.is_naive(dt):
        return timezone.make_aware(dt, tz)

    if tz:
        return timezone.localtime(dt, tz)

    return dt
