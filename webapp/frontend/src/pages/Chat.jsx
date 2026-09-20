import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import Header from '../components/Header.jsx';
import LlmPicker from '../components/LlmPicker.jsx';
import LanguagePicker from '../components/LanguagePicker.jsx';
import ConversationSidebar from '../components/ConversationSidebar.jsx';
import LogoutButton from '../components/LogoutButton.jsx';
import useConversations from '../hooks/useConversations.js';
import {
  askQuestion,
  claimShareLinkApi,
  createShareLinkApi,
  getAttachmentUrl,
  isLoggedIn,
  revokeShareLinkApi,
  transcribeAudio,
  uploadFile,
} from '../api.js';
import { LANGUAGE_NAMES, RTL_LANGUAGES, SPEECH_LANG_TAGS, stringsFor } from '../i18n.js';
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

function AttachmentChip({ attachment, conversationId }) {
  const [opening, setOpening] = useState(false);

  async function handleOpen() {
    setOpening(true);
    try {
      const url = await getAttachmentUrl(conversationId, attachment.key);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch {
      window.alert('Could not open this attachment.');
    } finally {
      setOpening(false);
    }
  }

  return (
    <button type="button" className="attachment-chip" onClick={handleOpen} disabled={opening}>
      &#128206; {attachment.filename}
    </button>
  );
}

function SpeakButton({ text, lang, t }) {
  const [speaking, setSpeaking] = useState(false);

  if (typeof window === 'undefined' || !window.speechSynthesis) return null;

  function handleToggle() {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel(); // only one answer speaks at a time
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }

  return (
    <button
      type="button"
      className="speak-btn"
      onClick={handleToggle}
      title={speaking ? t.stopSpeaking : t.speakAnswer}
    >
      {speaking ? '⏹' : '🔊'}
    </button>
  );
}

function MessageBubble({ message, index, t, conversationId }) {
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

      {role === 'agent' && text && (
        <SpeakButton
          text={text}
          lang={SPEECH_LANG_TAGS[(meta && meta.answerLanguage) || 'en'] || 'en-US'}
          t={t}
        />
      )}

      {meta && meta.attachment && (
        <div className="attachment-row">
          <AttachmentChip attachment={meta.attachment} conversationId={conversationId} />
        </div>
      )}

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

function ShareModal({ conversationId, onClose, onShareEmail }) {
  const [email, setEmail] = useState('');
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState(null);
  const [emailSent, setEmailSent] = useState(false);

  const [link, setLink] = useState(null);
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkError, setLinkError] = useState(null);
  const [copied, setCopied] = useState(false);

  async function handleEmailSubmit(e) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setEmailBusy(true);
    setEmailError(null);
    try {
      await onShareEmail(trimmed);
      setEmail('');
      setEmailSent(true);
    } catch (err) {
      setEmailError(err.message || 'Could not share this conversation.');
    } finally {
      setEmailBusy(false);
    }
  }

  async function handleGenerateLink() {
    setLinkBusy(true);
    setLinkError(null);
    try {
      const created = await createShareLinkApi(conversationId);
      setLink(created);
    } catch (err) {
      setLinkError(err.message || 'Could not create a share link.');
    } finally {
      setLinkBusy(false);
    }
  }

  async function handleRevokeLink() {
    setLinkBusy(true);
    setLinkError(null);
    try {
      await revokeShareLinkApi(conversationId);
      setLink(null);
    } catch (err) {
      setLinkError(err.message || 'Could not revoke the share link.');
    } finally {
      setLinkBusy(false);
    }
  }

  function handleCopy() {
    if (!link || !navigator.clipboard) return;
    navigator.clipboard.writeText(link.url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="share-modal-backdrop" onClick={onClose}>
      <div className="share-modal" onClick={(e) => e.stopPropagation()}>
        <div className="share-modal-header">
          <h3>Share this conversation</h3>
          <button type="button" className="share-modal-close" onClick={onClose} title="Close">
            &times;
          </button>
        </div>

        <form className="share-modal-section" onSubmit={handleEmailSubmit}>
          <label htmlFor="share-email">Share with a colleague</label>
          <div className="share-modal-row">
            <input
              id="share-email"
              type="email"
              placeholder="colleague@company.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setEmailSent(false);
              }}
              disabled={emailBusy}
            />
            <button type="submit" disabled={emailBusy || !email.trim()}>
              {emailBusy ? '…' : 'Share'}
            </button>
          </div>
          {emailError && <p className="share-modal-error">{emailError}</p>}
          {emailSent && !emailError && <p className="share-modal-success">Shared.</p>}
        </form>

        <div className="share-modal-divider" />

        <div className="share-modal-section">
          <label>Share via QR code</label>
          {!link ? (
            <button type="button" onClick={handleGenerateLink} disabled={linkBusy}>
              {linkBusy ? 'Generating…' : 'Generate QR code'}
            </button>
          ) : (
            <div className="share-qr-block">
              {/* eslint-disable-next-line jsx-a11y/alt-text -- inline SVG data URI from our own backend */}
              <img src={link.qr_svg_data_uri} alt="QR code linking to this conversation" className="share-qr-image" />
              <div className="share-modal-row">
                <input
                  type="text"
                  readOnly
                  value={link.url}
                  onFocus={(e) => e.target.select()}
                />
                <button type="button" onClick={handleCopy}>
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <p className="share-link-note">
                Anyone with this link or QR code can view this conversation (read-only) once they sign in.
                Expires {new Date(link.expires_at).toLocaleDateString()}.
              </p>
              <button type="button" className="share-link-revoke" onClick={handleRevokeLink} disabled={linkBusy}>
                Revoke link
              </button>
            </div>
          )}
          {linkError && <p className="share-modal-error">{linkError}</p>}
        </div>
      </div>
    </div>
  );
}

export default function Chat() {
  const {
    conversations,
    sharedConversations,
    activeConversation,
    createConversation,
    selectConversation,
    deleteConversation,
    appendMessage,
    shareConversation,
    unshareConversation,
    refreshConversations,
  } = useConversations();

  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [llmMode, setLlmMode] = useState('auto');
  const [uiLanguage, setUiLanguage] = useState('auto');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pendingAttachment, setPendingAttachment] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState(null);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareClaimError, setShareClaimError] = useState(null);
  const chatRef = useRef(null);
  const fileInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);

  const messages = activeConversation ? activeConversation.messages : [];
  const t = stringsFor(uiLanguage);
  const isRtl = RTL_LANGUAGES.has(uiLanguage);
  // Sharing is view-only (see webapp/models.py's ConversationShare
  // docstring) - a conversation someone else shared with us can be
  // read but never posted into.
  const canPost = !activeConversation || activeConversation.isOwner;

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (!isLoggedIn()) {
      // Carries the current path (including a ?share_token=... from a
      // scanned QR code) through to Login.jsx, which sends the user
      // back here - rather than to the generic /chat - once they've
      // signed in. See Login.jsx's getRedirectTarget.
      const redirect = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.replace(`/login?redirect=${redirect}`);
    }
  }, []);

  // Handles landing here via a "Share via QR code" link
  // (?share_token=... - see ShareModal below and webapp/backend.py's
  // /api/conversations/shared/{token}/claim). Runs once: claims the
  // token (grants this account read access, same as an email invite
  // would), strips the token from the URL so it can't be re-claimed
  // by reloading or re-shared by copying the address bar, then
  // refreshes the conversation lists and switches to it.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('share_token');
    if (!token || !isLoggedIn()) return;

    window.history.replaceState({}, '', '/chat');

    (async () => {
      try {
        const conv = await claimShareLinkApi(token);
        await refreshConversations();
        selectConversation(conv.id);
      } catch (err) {
        setShareClaimError(err.message || 'This share link is invalid or has expired.');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAttachClick() {
    fileInputRef.current?.click();
  }

  async function handleFileSelected(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // lets picking the same file twice re-fire onChange
    if (!file) return;

    setUploadError(null);
    setUploading(true);
    try {
      const result = await uploadFile(file);
      setPendingAttachment(result);
    } catch (err) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }

  async function handleMicClick() {
    if (recording) {
      mediaRecorderRef.current?.stop();
      return;
    }

    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ['audio/webm', 'audio/mp4', 'audio/ogg'].find(
        (type) => window.MediaRecorder && window.MediaRecorder.isTypeSupported(type)
      );
      const recorder = new window.MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recordedChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);

        const blob = new Blob(recordedChunksRef.current, { type: mimeType || 'audio/webm' });
        if (blob.size === 0) return;

        setTranscribing(true);
        try {
          const text = await transcribeAudio(blob);
          setInput((prev) => (prev ? `${prev} ${text}` : text));
        } catch {
          setVoiceError(t.voiceError);
        } finally {
          setTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setVoiceError(t.voiceError);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || !activeConversation || !canPost) return;

    const targetId = activeConversation.id;

    let previousNodeId = null;
    for (let i = activeConversation.messages.length - 1; i >= 0; i -= 1) {
      const m = activeConversation.messages[i];
      if (m.role === 'agent' && m.meta && m.meta.nodeId) {
        previousNodeId = m.meta.nodeId;
        break;
      }
    }

    const attachment = pendingAttachment;
    appendMessage(targetId, {
      role: 'user',
      text: question,
      ...(attachment ? { meta: { attachment } } : {}),
    });
    setInput('');
    setPendingAttachment(null);
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
          sharedConversations={sharedConversations}
          activeId={activeConversation?.id ?? null}
          onSelect={selectConversation}
          onCreate={createConversation}
          onDelete={deleteConversation}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="chat-main">
          {activeConversation && (
            <div className="conversation-status-bar">
              {canPost ? (
                activeConversation.sharedWith.length > 0 ? (
                  <span className="conversation-shared-note">
                    Shared with{' '}
                    {activeConversation.sharedWith.map((s, i) => (
                      <span key={s.user_id}>
                        {i > 0 && ', '}
                        {s.email}
                        <button
                          type="button"
                          className="unshare-btn"
                          title={`Stop sharing with ${s.email}`}
                          onClick={() => unshareConversation(activeConversation.id, s.user_id)}
                        >
                          &times;
                        </button>
                      </span>
                    ))}
                  </span>
                ) : (
                  <span />
                )
              ) : (
                <span className="conversation-viewer-note">
                  &#128065; Viewing {activeConversation.ownerEmail}'s conversation (read-only)
                </span>
              )}
              {canPost && (
                <button type="button" className="share-btn" onClick={() => setShareModalOpen(true)}>
                  Share
                </button>
              )}
            </div>
          )}

          {shareClaimError && (
            <div className="upload-error share-claim-error">
              {shareClaimError}
              <button type="button" onClick={() => setShareClaimError(null)} title="Dismiss">
                &times;
              </button>
            </div>
          )}

          {shareModalOpen && activeConversation && (
            <ShareModal
              conversationId={activeConversation.id}
              onClose={() => setShareModalOpen(false)}
              onShareEmail={(email) => shareConversation(activeConversation.id, email)}
            />
          )}

          <div id="chat" ref={chatRef}>
            <div className="chat-inner">
              {messages.length === 0 && <div className="empty-state">{t.emptyState}</div>}
              {messages.map((m, i) => (
                <MessageBubble key={i} message={m} index={i} t={t} conversationId={activeConversation?.id} />
              ))}
              {sending && <TypingIndicator />}
            </div>
          </div>

          <form id="form" onSubmit={handleSubmit}>
            <div className="form-inner">
              {canPost && (
                <>
                  {pendingAttachment && (
                    <span className="pending-attachment-chip">
                      &#128206; {pendingAttachment.filename}
                      <button
                        type="button"
                        onClick={() => setPendingAttachment(null)}
                        title="Remove attachment"
                      >
                        &times;
                      </button>
                    </span>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="file-input-hidden"
                    onChange={handleFileSelected}
                  />
                  <button
                    type="button"
                    className="attach-btn"
                    onClick={handleAttachClick}
                    disabled={uploading || sending}
                    title="Attach a file"
                  >
                    {uploading ? '…' : '📎'}
                  </button>
                  <button
                    type="button"
                    className={'mic-btn' + (recording ? ' recording' : '')}
                    onClick={handleMicClick}
                    disabled={transcribing || sending}
                    title={recording ? t.stopRecording : t.recordVoice}
                  >
                    {transcribing ? '…' : recording ? '⏹' : '🎤'}
                  </button>
                </>
              )}
              <input
                id="question"
                type="text"
                placeholder={
                  !canPost
                    ? 'Read-only - this conversation is shared with you'
                    : transcribing
                    ? t.transcribing
                    : t.placeholder
                }
                autoComplete="off"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!canPost}
              />
              <button id="send" type="submit" disabled={sending || !canPost}>
                {t.send}
              </button>
            </div>
            {uploadError && <div className="upload-error">{uploadError}</div>}
            {voiceError && <div className="upload-error">{voiceError}</div>}
          </form>
        </div>
      </div>
    </div>
  );
}
