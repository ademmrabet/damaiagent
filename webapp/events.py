# tiny in-memory pub/sub for live notifications

import asyncio
import json
from collections import defaultdict

_subscribers: dict[str, "set[asyncio.Queue]"] = defaultdict(set)


# open a queue for this user and return it
def subscribe(user_id: str) -> "asyncio.Queue":
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[user_id].add(queue)
    return queue


# stop sending events to a closed connection
def unsubscribe(user_id: str, queue: "asyncio.Queue") -> None:
    _subscribers[user_id].discard(queue)
    if not _subscribers[user_id]:
        _subscribers.pop(user_id, None)


# push an event to every open connection of a user
def notify_user(user_id: str, event: dict) -> None:
    payload = json.dumps(event)
    for queue in list(_subscribers.get(str(user_id), ())):
        queue.put_nowait(payload)


# send the same event to several users
def notify_users(user_ids, event: dict) -> None:
    for user_id in {str(uid) for uid in user_ids}:
        notify_user(user_id, event)
