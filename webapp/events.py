"""
Real-time push for conversation changes (2026-09-20, see
docs/decisions.md) - closes a gap where a newly shared conversation,
or a new message on one already shared, only showed up in a
colleague's sidebar after a manual page refresh. useConversations.js
used to fetch the conversation list exactly once, on mount; nothing
ever told an already-open tab that the list had changed.

A tiny in-memory pub/sub, not a message queue: each connected browser
tab holds one asyncio.Queue, keyed by user id (a user with several
tabs open just gets several queues), and any mutation that should be
visible to that user - a new share, an unshare, a new message on a
conversation they can see, a QR/link share being claimed - drops an
event into every queue registered for them. webapp/backend.py's
/api/events endpoint is what turns a queue into an actual SSE stream.

This is deliberately per-process. That's fine for the single Render
web service instance this app actually runs on, but it would NOT fan
out across multiple instances without a shared broker (Redis pub/sub
or similar) if this app is ever scaled horizontally - noted here
rather than silently assumed away.

The frontend also polls on a timer regardless of this (see
useConversations.js) as a safety net: proxies and idle-connection
timeouts can silently drop a long-lived SSE stream, and a periodic
poll means the sidebar self-heals within that interval even if the
push side fails outright.
"""

import asyncio
import json
from collections import defaultdict

_subscribers: dict[str, "set[asyncio.Queue]"] = defaultdict(set)


def subscribe(user_id: str) -> "asyncio.Queue":
    """Registers a new queue for this user and returns it - call unsubscribe when the connection closes."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[user_id].add(queue)
    return queue


def unsubscribe(user_id: str, queue: "asyncio.Queue") -> None:
    _subscribers[user_id].discard(queue)
    if not _subscribers[user_id]:
        _subscribers.pop(user_id, None)


def notify_user(user_id: str, event: dict) -> None:
    """
    Fire-and-forget: if the user has no open tab right now, there's no
    queue to put this in and that's fine - the next poll or the next
    time they open a tab picks up the real state from the database,
    this is purely a "wake up and refetch" nudge, never the data
    itself.
    """
    payload = json.dumps(event)
    for queue in list(_subscribers.get(str(user_id), ())):
        queue.put_nowait(payload)


def notify_users(user_ids, event: dict) -> None:
    for user_id in {str(uid) for uid in user_ids}:
        notify_user(user_id, event)
