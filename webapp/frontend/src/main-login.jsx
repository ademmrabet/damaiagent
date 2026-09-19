import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Login from './pages/Login.jsx';
import './styles/theme.css';
import './styles/shared.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Login />
  </StrictMode>
);
