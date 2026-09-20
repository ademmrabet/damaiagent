import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createConversationApi,
  deleteConversationApi,
  listConversations,
  openEventSource,
  postConversationMessage,
  shareConversationApi,
  unshareConversationApi,
} from '../api.js';

const MAX_CONVERSATIONS = 100;
const LOCAL_PREFIX = 'local-';
const POLL_INTERVAL_MS = 30_000;

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function makeLocalConversation() {
  const now = Date.now();
  return {
    id: `${LOCAL_PREFIX}${makeId()}`,
    title: 'New chat',
    titleIsDefault: true,
    messages: [],
    createdAt: now,
    updatedAt: now,
    isOwner: true,
    ownerEmail: null,
    sharedWith: [],
  };
}

function isLocal(id) {
  return typeof id === 'string' && id.startsWith(LOCAL_PREFIX);
}

function fromApi(c) {
  return {
    id: c.id,
    title: c.title,
    titleIsDefault: c.title_is_default,
    messages: c.messages,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
    isOwner: c.is_owner,
    ownerEmail: c.owner_email,
    sharedWith: c.shared_with || [],
  };
}

function deriveTitle(question) {
  const trimmed = question.trim();
  return trimmed.length > 42 ? trimmed.slice(0, 40) + '…' : trimmed;
}

// A background refetch (polling or an SSE nudge - see below) always
// wins for everything except the message list itself, where it could
// otherwise race an optimistic send: appendMessage shows the user's
// message immediately, then posts it to the server, and if a refetch
// lands in between it would briefly show the conversation WITHOUT the
// message that's already on screen. Never shrinking the message list
// on a background refresh avoids that flash without needing to
// coordinate the two paths any more tightly than this.
function mergeConversations(prevList, freshList) {
  const prevById = new Map(prevList.map((c) => [c.id, c]));
  return freshList.map((fresh) => {
    const prev = prevById.get(fresh.id);
    if (prev && prev.messages.length > fresh.messages.length) {
      return { ...fresh, messages: prev.messages };
    }
    return fresh;
  });
}

/**
 * Conversations used to live only in this browser's localStorage (see
 * docs/decisions.md, 2026-09-19) - fine for one person on one device,
 * but there was never a copy anywhere a colleague could reach, so
 * sharing wasn't possible. This now talks to the /api/conversations*
 * backend instead; the hook's own exposed shape is kept as close to
 * the old one as possible so Chat.jsx and ConversationSidebar.jsx
 * needed minimal changes.
 *
 * Originally this fetched the list exactly once, on mount - fine for
 * your OWN conversations (every change to those goes through this
 * same tab), but a conversation someone else shares with you, or a
 * new message on one already shared, was invisible until you
 * manually refreshed the page (2026-09-20, see docs/decisions.md).
 * Two mechanisms now keep the lists current without that: a 30-second
 * poll (dumb, always correct eventually, costs one small request) and
 * an SSE subscription (webapp/events.py) that nudges an immediate
 * refetch the moment something changes server-side. Either one alone
 * would be enough; running both means a dropped SSE connection (an
 * idle-timing-out proxy, a Render restart) only ever costs up to
 * POLL_INTERVAL_MS of staleness instead of silence until next reload.
 *
 * Every mutation still updates local state optimistically first (the
 * UI should never feel like it's waiting on a network round trip to
 * show your own message), then reconciles with whatever the server
 * actually persisted. If the initial load fails outright (backend
 * unreachable), this falls open into a single local-only conversation
 * (id prefixed "local-") that never touches the network again - same
 * "storage problem degrades gracefully" philosophy the old
 * localStorage version had for a quota/private-browsing failure.
 */
export default function useConversations() {
  const [ownConversations, setOwnConversations] = useState([]);
  const [sharedConversations, setSharedConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(true);
  const mountedRef = useRef(true);

  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    []
  );

  const refreshConversations = useCallback(async () => {
    try {
      const data = await listConversations();
      const own = data.own.map(fromApi);
      const shared = data.shared_with_me.map(fromApi);
      if (!mountedRef.current) return true;

      setOwnConversations((prev) => {
        const localOnly = prev.filter((c) => isLocal(c.id));
        return [...localOnly, ...mergeConversations(prev, own)];
      });
      setSharedConversations((prev) => mergeConversations(prev, shared));
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      try {
        const data = await listConversations();
        let own = data.own.map(fromApi);
        const shared = data.shared_with_me.map(fromApi);

        if (own.length === 0) {
          const created = await createConversationApi();
          own = [fromApi(created)];
        }

        if (cancelled) return;
        setOwnConversations(own);
        setSharedConversations(shared);
        setActiveId(own[0].id);
      } catch {
        if (cancelled) return;
        const fallback = makeLocalConversation();
        setOwnConversations([fallback]);
        setSharedConversations([]);
        setActiveId(fallback.id);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  // Polling safety net - see this module's docstring for why this
  // runs alongside, not instead of, the SSE subscription below.
  useEffect(() => {
    const interval = setInterval(() => {
      refreshConversations();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshConversations]);

  // Real-time nudge: any share/unshare/new-message event server-side
  // triggers an immediate refetch instead of waiting for the next
  // poll tick. EventSource reconnects on its own per spec if the
  // connection drops; the poll above covers the gap either way.
  useEffect(() => {
    const source = openEventSource();
    if (!source) return undefined;

    source.onmessage = () => {
      refreshConversations();
    };

    return () => source.close();
  }, [refreshConversations]);

  // Keeps activeId valid no matter how the lists change - after a
  // delete removes whichever conversation was active.
  useEffect(() => {
    if (loading) return;
    const stillExists =
      ownConversations.some((c) => c.id === activeId) ||
      sharedConversations.some((c) => c.id === activeId);
    if (!stillExists) {
      setActiveId(ownConversations[0]?.id ?? sharedConversations[0]?.id ?? null);
    }
  }, [ownConversations, sharedConversations, activeId, loading]);

  const activeConversation =
    ownConversations.find((c) => c.id === activeId) ||
    sharedConversations.find((c) => c.id === activeId) ||
    null;

  const createConversation = useCallback(async () => {
    try {
      const created = await createConversationApi();
      const conv = fromApi(created);
      setOwnConversations((prev) => [conv, ...prev].slice(0, MAX_CONVERSATIONS));
      setActiveId(conv.id);
      return conv.id;
    } catch {
      // Fail open (see this module's docstring) rather than leaving
      // "+ New chat" looking like it did nothing.
      const conv = makeLocalConversation();
      setOwnConversations((prev) => [conv, ...prev].slice(0, MAX_CONVERSATIONS));
      setActiveId(conv.id);
      return conv.id;
    }
  }, []);

  const selectConversation = useCallback((id) => {
    setActiveId(id);
  }, []);

  const deleteConversation = useCallback(async (id) => {
    if (!isLocal(id)) {
      try {
        await deleteConversationApi(id);
      } catch {
        // Leave local state untouched if the backend couldn't delete
        // it - better a stale row than one that silently reappears.
        return;
      }
    }
    setOwnConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) {
        const fallback = makeLocalConversation();
        return [fallback];
      }
      return next;
    });
  }, []);

  const appendMessage = useCallback((targetId, message) => {
    const isFirstUserMessage = (c) => c.titleIsDefault && message.role === 'user';

    setOwnConversations((prev) =>
      prev.map((c) => {
        if (c.id !== targetId) return c;
        return {
          ...c,
          messages: [...c.messages, message],
          updatedAt: Date.now(),
          title: isFirstUserMessage(c) ? deriveTitle(message.text) : c.title,
          titleIsDefault: isFirstUserMessage(c) ? false : c.titleIsDefault,
        };
      })
    );

    if (isLocal(targetId)) return;

    postConversationMessage(targetId, message)
      .then((updated) => {
        const conv = fromApi(updated);
        setOwnConversations((prev) => prev.map((c) => (c.id === targetId ? conv : c)));
      })
      .catch((err) => {
        // The optimistic message stays visible either way - this is a
        // persistence failure, not a chat failure. Surfacing every
        // transient network hiccup as a UI error would be noisier than
        // useful for a message that's already showing on screen.
        console.error('Failed to save message to conversation', targetId, err);
      });
  }, []);

  const shareConversation = useCallback(async (id, email) => {
    const updated = await shareConversationApi(id, email);
    const conv = fromApi(updated);
    setOwnConversations((prev) => prev.map((c) => (c.id === id ? conv : c)));
    return conv;
  }, []);

  const unshareConversation = useCallback(async (id, targetUserId) => {
    const updated = await unshareConversationApi(id, targetUserId);
    const conv = fromApi(updated);
    setOwnConversations((prev) => prev.map((c) => (c.id === id ? conv : c)));
    return conv;
  }, []);

  return {
    conversations: ownConversations,
    sharedConversations,
    activeConversation,
    loading,
    createConversation,
    selectConversation,
    deleteConversation,
    appendMessage,
    shareConversation,
    unshareConversation,
    refreshConversations,
  };
}
