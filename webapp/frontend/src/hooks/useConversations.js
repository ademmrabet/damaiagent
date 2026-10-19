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

// conversations live on the server; polling + sse keep the lists fresh
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

  useEffect(() => {
    const interval = setInterval(() => {
      refreshConversations();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshConversations]);

  useEffect(() => {
    const source = openEventSource();
    if (!source) return undefined;

    source.onmessage = () => {
      refreshConversations();
    };

    return () => source.close();
  }, [refreshConversations]);

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
