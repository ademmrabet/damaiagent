import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Dashboard from './pages/Dashboard.jsx';
import './styles/theme.css';
import './styles/shared.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Dashboard />
  </StrictMode>
);
