import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Landing from './pages/Landing.jsx';
import './styles/theme.css';
import './styles/shared.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Landing />
  </StrictMode>
);
