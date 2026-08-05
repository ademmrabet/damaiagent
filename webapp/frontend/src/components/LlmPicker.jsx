import { useEffect, useRef, useState } from 'react';
import { getLlmConfig } from '../api.js';

const OPTIONS = [
  { value: 'off', label: 'No LLM', sub: 'template answer' },
  { value: 'ollama', label: 'Ollama', sub: '(local)', modelKey: 'ollama_model' },
  { value: 'groq', label: 'Groq', sub: '(API)', modelKey: 'groq_model' },
  { value: 'auto', label: 'Auto', sub: 'API first, local fallback' },
];

const LABELS = {
  off: 'No LLM (template answer)',
  ollama: 'Ollama (local)',
  groq: 'Groq (API)',
  auto: 'Auto (API first, local fallback)',
};

export default function LlmPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState({ ollama_model: '', groq_model: '' });
  const rootRef = useRef(null);

  useEffect(() => {
    getLlmConfig()
      .then(setModels)
      .catch(() => {
        // Backend unreachable at load time - the option rows just
        // show no model name, no need to break the picker over it.
      });
  }, []);

  useEffect(() => {
    function onDocClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  return (
    <div className="llm-picker" ref={rootRef}>
      <button
        type="button"
        className="llm-picker-toggle"
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Optional: phrase the answer with an LLM instead of the template. Facts always come from the graph, never the model."
        onClick={() => setOpen((o) => !o)}
      >
        <span>{LABELS[value]}</span>
        <span className="llm-picker-caret">&#9662;</span>
      </button>
      <ul className="llm-picker-menu" role="listbox" hidden={!open}>
        {OPTIONS.map((opt) => (
          <li
            key={opt.value}
            className={'llm-picker-option' + (opt.value === value ? ' selected' : '')}
            data-value={opt.value}
            role="option"
            aria-selected={opt.value === value}
            onClick={() => {
              onChange(opt.value);
              setOpen(false);
            }}
          >
            <span className="option-label">{opt.label}</span>
            {opt.modelKey ? (
              <span className="option-model">{models[opt.modelKey] || ''}</span>
            ) : null}
            <span className="option-sub">{opt.sub}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
