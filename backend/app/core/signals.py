"""Shared context store — every domain agent reads/writes here.

A single SQLite table backs the entire Atlas "intelligence layer". Agents
publish observations (a delayed well, a flat-line RRR, a PPE violation).
The orchestrator reads them, ranks them, and synthesises the morning brief.

Schema is deliberately thin — text columns + a JSON blob for refs.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

from ..config import settings


DB_PATH = settings.chroma_dir.parent / "atlas_signals.sqlite"

SEVERITY_RANK = {"info": 0, "low": 1, "med": 2, "high": 3, "critical": 4}


@dataclass
class Signal:
    id: int | None = None
    agent: str = ""                      # e.g. "production", "drilling", "hse"
    severity: str = "info"               # info | low | med | high | critical
    title: str = ""
    body: str = ""                       # short markdown
    refs: list[dict] = field(default_factory=list)  # [{filename, section, ...}]
    metric: dict | None = None           # optional structured numbers
    ts: float = field(default_factory=time.time)
    status: str = "open"                 # open | acked | resolved

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Signal":
        return cls(
            id=row["id"],
            agent=row["agent"],
            severity=row["severity"],
            title=row["title"],
            body=row["body"],
            refs=json.loads(row["refs"] or "[]"),
            metric=json.loads(row["metric"]) if row["metric"] else None,
            ts=row["ts"],
            status=row["status"],
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------
# Schema + connection management
# ------------------------------------------------------------------

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agent     TEXT    NOT NULL,
    severity  TEXT    NOT NULL,
    title     TEXT    NOT NULL,
    body      TEXT    NOT NULL,
    refs      TEXT,                 -- JSON
    metric    TEXT,                 -- JSON
    ts        REAL    NOT NULL,
    status    TEXT    NOT NULL DEFAULT 'open',
    dedup_key TEXT    UNIQUE        -- agent + title; lets us upsert
);
CREATE INDEX IF NOT EXISTS idx_signals_ts        ON signals(ts DESC);
CREATE INDEX IF NOT EXISTS idx_signals_agent     ON signals(agent);
CREATE INDEX IF NOT EXISTS idx_signals_severity  ON signals(severity);
"""


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    """Idempotent — call at app startup."""
    with _conn() as c:
        c.executescript(_INIT_SQL)


# ------------------------------------------------------------------
# Read / write API
# ------------------------------------------------------------------

def publish(sig: Signal) -> int:
    """Upsert by (agent, title). Returns the row id."""
    dedup = f"{sig.agent}::{sig.title}"
    with _conn() as c:
        c.execute(
            """INSERT INTO signals (agent, severity, title, body, refs, metric, ts, status, dedup_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(dedup_key) DO UPDATE SET
                   severity = excluded.severity,
                   body     = excluded.body,
                   refs     = excluded.refs,
                   metric   = excluded.metric,
                   ts       = excluded.ts,
                   status   = 'open'""",
            (
                sig.agent,
                sig.severity,
                sig.title,
                sig.body,
                json.dumps(sig.refs),
                json.dumps(sig.metric) if sig.metric else None,
                sig.ts,
                sig.status,
                dedup,
            ),
        )
        return c.execute("SELECT id FROM signals WHERE dedup_key = ?", (dedup,)).fetchone()["id"]


def publish_many(sigs: Iterable[Signal]) -> None:
    for s in sigs:
        publish(s)


def list_open(limit: int = 50, agent: str | None = None) -> list[Signal]:
    q = "SELECT * FROM signals WHERE status = 'open'"
    args: list = []
    if agent:
        q += " AND agent = ?"
        args.append(agent)
    q += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [Signal.from_row(r) for r in c.execute(q, args).fetchall()]


def list_ranked(limit: int = 8) -> list[Signal]:
    """Return open signals sorted by severity then recency.

    Severity is mapped via SEVERITY_RANK in Python, since SQLite has no enum.
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM signals WHERE status = 'open' ORDER BY ts DESC"
        ).fetchall()
    sigs = [Signal.from_row(r) for r in rows]
    sigs.sort(key=lambda s: (-SEVERITY_RANK.get(s.severity, 0), -s.ts))
    return sigs[:limit]


def clear(agent: str | None = None) -> int:
    """Remove signals — useful before agents republish. Returns rows deleted."""
    with _conn() as c:
        if agent:
            cur = c.execute("DELETE FROM signals WHERE agent = ?", (agent,))
        else:
            cur = c.execute("DELETE FROM signals")
        return cur.rowcount


def ack(signal_id: int) -> None:
    with _conn() as c:
        c.execute("UPDATE signals SET status = 'acked' WHERE id = ?", (signal_id,))
