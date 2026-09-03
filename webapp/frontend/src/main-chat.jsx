import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Chat from './pages/Chat.jsx';
import './styles/theme.css';
import './styles/shared.css';
import './styles/llmPicker.css';
import './styles/languagePicker.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Chat />
  </StrictMode>
);
