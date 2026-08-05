import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import './conversationSidebar.css';

export default function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onCreate,
  onDelete,
}) {
  const listRef = useRef(null);

  // Only conversations with at least one message are listed - an
  // empty "New chat" you're currently composing in doesn't need its
  // own row (you're already looking at it), and clicking "+ New chat"
  // repeatedly without sending anything shouldn't pile up empty
  // entries in the list.
  const visible = conversations.filter(
    (c) => c.messages.length > 0 || c.id === activeId
  );

  useEffect(() => {
    if (!listRef.current) return;
    gsap.fromTo(
      listRef.current.children,
      { opacity: 0, x: -8 },
      { opacity: 1, x: 0, duration: 0.3, stagger: 0.03, ease: 'power2.out' }
    );
  }, [visible.length]);

  return (
    <aside className="conversation-sidebar">
      <button type="button" className="new-chat-btn" onClick={onCreate}>
        <span aria-hidden="true">+</span> New chat
      </button>

      <div className="conversation-list" ref={listRef}>
        {visible.map((c) => (
          <div
            key={c.id}
            className={'conversation-item' + (c.id === activeId ? ' active' : '')}
            onClick={() => onSelect(c.id)}
          >
            <span className="conversation-title">{c.title}</span>
            {conversations.length > 1 && (
              <button
                type="button"
                className="conversation-delete"
                title="Delete conversation"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
              >
                &times;
              </button>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
