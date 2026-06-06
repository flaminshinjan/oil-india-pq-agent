"""Shared prompt-building utilities.

Every agent prompt is prefixed with the current-date / Indian-FY context
block so 'last 5 years', 'recent', and 'current FY' resolve correctly
against today's date — not the model's training cutoff.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def india_fy(d: datetime) -> tuple[int, int]:
    """(start_year, end_year) of the Indian FY containing `d`. Apr 1 → Mar 31."""
    if d.month >= 4:
        return d.year, d.year + 1
    return d.year - 1, d.year


def fy_label(start: int) -> str:
    return f"FY {start}-{str(start + 1)[-2:]}"


def date_block() -> str:
    """Date-aware preamble injected at the top of every agent prompt."""
    now = datetime.now(IST)
    cur, _ = india_fy(now)
    last = cur - 1
    five = last - 4
    return (
        f"# Current date and fiscal context\n"
        f"Today is **{now.strftime('%A, %d %B %Y')}** (Asia/Kolkata).\n\n"
        f"Indian fiscal year runs **1 April – 31 March**:\n"
        f"- Current FY (in progress): **{fy_label(cur)}**\n"
        f"- Most recently completed FY: **{fy_label(last)}**\n"
        f"- 'Last 5 years' default window: **{fy_label(five)} through {fy_label(last)}**\n\n"
        f"Always resolve relative dates ('last 5 years', 'recent', 'current FY')\n"
        f"against today's date — not against your training cutoff.\n"
    )
