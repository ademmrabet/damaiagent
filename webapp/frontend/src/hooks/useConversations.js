import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'dam-agent-conversations-v1';
const MAX_CONVERSATIONS = 100;

function loadFromStorage() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.conversations) || parsed.conversations.length === 0) {
      return null;
    }
    return parsed;
  } catch {
    // Private browsing, storage disabled, quota exceeded, or corrupted
    // JSON - fail open into a fresh in-memory conversation rather than
    // crashing the chat page over a storage problem. History just
    // won't survive a reload in that case, which is the same as
    // before this feature existed.
    return null;
  }
}

function saveToStorage(conversations, activeId) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ conversations, activeId }));
  } catch {
    // Same fail-open reasoning as loadFromStorage.
  }
}

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function makeConversation() {
  const now = Date.now();
  return {
    id: makeId(),
    title: 'New chat',
    titleIsDefault: true,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

function deriveTitle(question) {
  const trimmed = question.trim();
  return trimmed.length > 42 ? trimmed.slice(0, 40) + '…' : trimmed;
}

/**
 * All conversation state lives here, persisted to localStorage - this
 * app has no backend user/session layer, so the browser's own storage
 * is the only place "history" can live without a much bigger feature
 * (accounts, a database). Every write fails open (see saveToStorage) -
 * a storage problem degrades to "this session's history won't
 * persist," never to a broken chat.
 */
export default function useConversations() {
  const [conversations, setConversations] = useState(() => {
    const stored = loadFromStorage();
    return stored ? stored.conversations : [makeConversation()];
  });
  const [activeId, setActiveId] = useState(() => {
    const stored = loadFromStorage();
    if (stored && stored.conversations.some((c) => c.id === stored.activeId)) {
      return stored.activeId;
    }
    return null;
  });

  // Keeps activeId valid no matter how conversations changes - first
  // mount (null -> first conversation), and after a delete removes
  // whichever conversation was active.
  useEffect(() => {
    if (!conversations.some((c) => c.id === activeId)) {
      setActiveId(conversations[0]?.id ?? null);
    }
  }, [conversations, activeId]);

  useEffect(() => {
    saveToStorage(conversations, activeId);
  }, [conversations, activeId]);

  const activeConversation = conversations.find((c) => c.id === activeId) || null;

  const createConversation = useCallback(() => {
    const conv = makeConversation();
    setConversations((prev) => [conv, ...prev].slice(0, MAX_CONVERSATIONS));
    setActiveId(conv.id);
    return conv.id;
  }, []);

  const selectConversation = useCallback((id) => {
    setActiveId(id);
  }, []);

  const deleteConversation = useCallback((id) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      return next.length === 0 ? [makeConversation()] : next;
    });
  }, []);

  const appendMessage = useCallback((targetId, message) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== targetId) return c;
        const isFirstUserMessage = c.titleIsDefault && message.role === 'user';
        return {
          ...c,
          messages: [...c.messages, message],
          updatedAt: Date.now(),
          title: isFirstUserMessage ? deriveTitle(message.text) : c.title,
          titleIsDefault: isFirstUserMessage ? false : c.titleIsDefault,
        };
      })
    );
  }, []);

  return {
    conversations,
    activeConversation,
    createConversation,
    selectConversation,
    deleteConversation,
    appendMessage,
  };
}
