import { useEffect, useRef, useState } from 'react';
import { LANGUAGE_OPTIONS } from '../i18n.js';

export default function LanguagePicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    function onDocClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  const current = LANGUAGE_OPTIONS.find((o) => o.value === value) || LANGUAGE_OPTIONS[0];

  return (
    <div className="lang-picker" ref={rootRef}>
      <button
        type="button"
        className="lang-picker-toggle"
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Answer language - overrides auto-detection when set to anything other than Auto"
        onClick={() => setOpen((o) => !o)}
      >
        <span aria-hidden="true">&#127760;</span>
        <span>{current.label}</span>
        <span className="lang-picker-caret">&#9662;</span>
      </button>
      <ul className="lang-picker-menu" role="listbox" hidden={!open}>
        {LANGUAGE_OPTIONS.map((opt) => (
          <li
            key={opt.value}
            className={'lang-picker-option' + (opt.value === value ? ' selected' : '')}
            data-value={opt.value}
            role="option"
            aria-selected={opt.value === value}
            onClick={() => {
              onChange(opt.value);
              setOpen(false);
            }}
          >
            <span className="option-label">{opt.label}</span>
            {opt.sub ? <span className="option-sub">{opt.sub}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
