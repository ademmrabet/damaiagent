import { useCallback, useEffect, useState } from 'react';
import {
  createConversationApi,
  deleteConversationApi,
  listConversations,
  postConversationMessage,
  shareConversationApi,
  unshareConversationApi,
} from '../api.js';

const MAX_CONVERSATIONS = 100;
const LOCAL_PREFIX = 'local-';

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

/**
 * Conversations used to live only in this browser's localStorage (see
 * docs/decisions.md, 2026-09-19) - fine for one person on one device,
 * but there was never a copy anywhere a colleague could reach, so
 * sharing wasn't possible. This now talks to the /api/conversations*
 * backend instead; the hook's own exposed shape is kept as close to
 * the old one as possible so Chat.jsx and ConversationSidebar.jsx
 * needed minimal changes.
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

  useEffect(() => {
    let cancelled = false;

    async function load() {
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

    load();
    return () => {
      cancelled = true;
    };
  }, []);

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
  };
}
