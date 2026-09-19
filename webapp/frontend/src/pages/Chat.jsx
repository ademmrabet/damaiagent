import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import Header from '../components/Header.jsx';
import LlmPicker from '../components/LlmPicker.jsx';
import LanguagePicker from '../components/LanguagePicker.jsx';
import ConversationSidebar from '../components/ConversationSidebar.jsx';
import LogoutButton from '../components/LogoutButton.jsx';
import useConversations from '../hooks/useConversations.js';
import { askQuestion, isLoggedIn } from '../api.js';
import { LANGUAGE_NAMES, RTL_LANGUAGES, stringsFor } from '../i18n.js';
import './chat.css';

function isLowConfidence(data) {
  return (
    data.method !== 'smalltalk' &&
    (!data.node_id || (data.method === 'text_search' && data.score < 0.3))
  );
}

function metaLabel(data, t) {
  let label;
  if (data.method === 'id') {
    label = t.matchedById;
  } else if (data.method === 'context_carryover') {
    label = t.carriedOver;
  } else {
    label = t.matchedByText;
  }
  if (data.score !== null && data.score !== undefined) {
    label += ' · ' + t.confidence + ' ' + data.score.toFixed(2);
  }
  return label;
}

function TypingIndicator() {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.25 });
    const dots = ref.current.querySelectorAll('.typing-dot');
    const tl = gsap.timeline({ repeat: -1 });
    tl.to(dots, { y: -5, duration: 0.3, stagger: 0.12, ease: 'power1.out' }).to(
      dots,
      { y: 0, duration: 0.3, stagger: 0.12, ease: 'power1.in' },
      '-=0.2'
    );
    return () => tl.kill();
  }, []);

  return (
    <div className="msg agent typing" ref={ref}>
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </div>
  );
}

function MessageBubble({ message, index, t }) {
  const ref = useRef(null);
  const [showDeterministic, setShowDeterministic] = useState(false);

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(
      ref.current,
      { opacity: 0, y: 14, scale: 0.98 },
      {
        opacity: 1,
        y: 0,
        scale: 1,
        duration: 0.35,
        delay: Math.min(index * 0.04, 0.6),
        ease: 'power2.out',
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { role, text, meta } = message;
  const lowConfidence = !!(meta && meta.lowConfidence);
  const showMeta = !!(meta && meta.showMeta);
  const canToggleDeterministic =
    meta &&
    meta.usedLlm &&
    meta.deterministicAnswer &&
    meta.deterministicAnswer !== text;
  const answeredInOtherLanguage =
    meta && meta.answerLanguage && meta.answerLanguage !== 'en' && meta.usedLlm;
  const languageFellBack =
    meta && meta.answerLanguage && meta.answerLanguage !== 'en' && !meta.usedLlm;

  return (
    <div
      ref={ref}
      className={'msg ' + role + (lowConfidence ? ' low-confidence' : '')}
    >
      {text}

      {showMeta && (
        <div className="meta">
          {lowConfidence && <span className="flag">&#9888; {t.lowConfidence}</span>}
          <span>{metaLabel(meta, t)}</span>
          {meta.usedLlm && (
            <span className="llm-badge">&#10022; {t.phrasedBy} {meta.llmProvider}</span>
          )}
          {!meta.usedLlm && meta.llmRequested && meta.llmError && !languageFellBack && (
            <span className="llm-fallback" title={meta.llmError}>
              &#9888; {t.llmUnavailable}
            </span>
          )}
          {answeredInOtherLanguage && (
            <span className="lang-badge">
              &#127760; {t.answeredIn} {LANGUAGE_NAMES[meta.answerLanguage] || meta.answerLanguage}
            </span>
          )}
          {(meta.translationError || languageFellBack) && (
            <span className="llm-fallback" title={meta.translationError || meta.llmError || ''}>
              &#9888; {t.translationFailed}
            </span>
          )}
        </div>
      )}

      {canToggleDeterministic && (
        <>
          <button
            type="button"
            className="toggle-deterministic"
            onClick={() => setShowDeterministic((s) => !s)}
          >
            {showDeterministic ? t.hideDeterministic : t.showDeterministic}
          </button>
          {showDeterministic && (
            <div className="deterministic-box">{meta.deterministicAnswer}</div>
          )}
        </>
      )}
    </div>
  );
}

export default function Chat() {
  const {
    conversations,
    activeConversation,
    createConversation,
    selectConversation,
    deleteConversation,
    appendMessage,
  } = useConversations();

  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [llmMode, setLlmMode] = useState('auto');
  const [uiLanguage, setUiLanguage] = useState('auto');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const chatRef = useRef(null);

  const messages = activeConversation ? activeConversation.messages : [];
  const t = stringsFor(uiLanguage);
  const isRtl = RTL_LANGUAGES.has(uiLanguage);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.replace('/login');
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || !activeConversation) return;

    const targetId = activeConversation.id;

    let previousNodeId = null;
    for (let i = activeConversation.messages.length - 1; i >= 0; i -= 1) {
      const m = activeConversation.messages[i];
      if (m.role === 'agent' && m.meta && m.meta.nodeId) {
        previousNodeId = m.meta.nodeId;
        break;
      }
    }

    appendMessage(targetId, { role: 'user', text: question });
    setInput('');
    setSending(true);

    try {
      const data = await askQuestion(question, llmMode, previousNodeId, uiLanguage);
      appendMessage(targetId, {
        role: 'agent',
        text: data.answer,
        meta: {
          nodeId: data.node_id,
          showMeta: !!data.node_id || !!data.translation_error,
          method: data.method,
          score: data.score,
          lowConfidence: isLowConfidence(data),
          usedLlm: data.used_llm,
          llmProvider: data.llm_provider,
          llmError: data.llm_error,
          llmRequested: llmMode !== 'off',
          deterministicAnswer: data.deterministic_answer,
          detectedLanguage: data.detected_language,
          answerLanguage: data.answer_language,
          translationError: data.translation_error,
        },
      });
    } catch {
      appendMessage(targetId, {
        role: 'agent',
        text: t.connectionError,
        meta: { lowConfidence: true },
      });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-page" dir={isRtl ? 'rtl' : 'ltr'}>
      <Header
        title="DAM AI Agent"
        subtitle={t.subtitle}
        navHref="/dashboard"
        navLabel={t.dashboardLink}
        right={
          <>
            <LanguagePicker value={uiLanguage} onChange={setUiLanguage} />
            <LlmPicker value={llmMode} onChange={setLlmMode} />
            <LogoutButton />
          </>
        }
        onMenuClick={() => setSidebarOpen((o) => !o)}
      />

      <div className="chat-body">
        <div
          className={'sidebar-backdrop' + (sidebarOpen ? ' visible' : '')}
          onClick={() => setSidebarOpen(false)}
        />
        <ConversationSidebar
          conversations={conversations}
          activeId={activeConversation?.id ?? null}
          onSelect={selectConversation}
          onCreate={createConversation}
          onDelete={deleteConversation}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="chat-main">
          <div id="chat" ref={chatRef}>
            <div className="chat-inner">
              {messages.length === 0 && <div className="empty-state">{t.emptyState}</div>}
              {messages.map((m, i) => (
                <MessageBubble key={i} message={m} index={i} t={t} />
              ))}
              {sending && <TypingIndicator />}
            </div>
          </div>

          <form id="form" onSubmit={handleSubmit}>
            <div className="form-inner">
              <input
                id="question"
                type="text"
                placeholder={t.placeholder}
                autoComplete="off"
                value={input}
                onChange={(e) => setInput(e.target.value)}
              />
              <button id="send" type="submit" disabled={sending}>
                {t.send}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
