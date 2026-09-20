"""
Unit tests for the SSE pub/sub in webapp/events.py - see its docstring
and webapp/backend.py's /api/events for how this backs the sidebar's
real-time refresh (2026-09-20, see docs/decisions.md). Deliberately
tested in isolation from FastAPI/TestClient here; test_backend.py
covers the actual /api/events route's auth handling.
"""

from webapp.events import notify_user, notify_users, subscribe, unsubscribe


def test_notify_user_delivers_to_a_subscribed_queue():
    queue = subscribe("user-1")
    try:
        notify_user("user-1", {"type": "shared", "conversation_id": "abc"})
        assert queue.qsize() == 1
        message = queue.get_nowait()
        assert "shared" in message
        assert "abc" in message
    finally:
        unsubscribe("user-1", queue)


def test_notify_user_with_no_subscribers_does_not_raise():
    notify_user("nobody-is-listening", {"type": "shared"})


def test_multiple_tabs_for_the_same_user_each_receive_the_event():
    q1 = subscribe("user-2")
    q2 = subscribe("user-2")
    try:
        notify_user("user-2", {"type": "message"})
        assert q1.qsize() == 1
        assert q2.qsize() == 1
    finally:
        unsubscribe("user-2", q1)
        unsubscribe("user-2", q2)


def test_notify_users_fans_out_without_duplicating_a_repeated_id():
    qa = subscribe("user-a")
    qb = subscribe("user-b")
    try:
        notify_users(["user-a", "user-b", "user-a"], {"type": "shared"})
        assert qa.qsize() == 1
        assert qb.qsize() == 1
    finally:
        unsubscribe("user-a", qa)
        unsubscribe("user-b", qb)


def test_unsubscribe_stops_further_delivery():
    queue = subscribe("user-3")
    unsubscribe("user-3", queue)
    notify_user("user-3", {"type": "shared"})
    assert queue.qsize() == 0


def test_notify_user_accepts_non_string_ids_matching_subscribe():
    # Callers in backend.py sometimes pass a SQLAlchemy UUID column
    # value straight through rather than str(...)-ing it first (e.g.
    # ConversationShare.shared_with_user_id) - notify_user normalizes
    # both sides to str so that still reaches the right queue.
    queue = subscribe("user-4")
    try:
        notify_user("user-4", {"type": "shared"})
        assert queue.qsize() == 1
    finally:
        unsubscribe("user-4", queue)
