import React from 'react';
import ReactDOM from 'react-dom/client';
import { FloatingWindow } from './components/FloatingWindow';
import './index.css';

// Set the Lawn theme for the floating window
document.documentElement.dataset.theme = 'dark';

// Override CSS variables for the floating window's specific color scheme
const style = document.createElement('style');
style.textContent = `
  :root, [data-theme="dark"] {
    --color-bg: #09131b;
    --color-panel: #0d1f2d;
    --color-dark: #09131b;
    --color-accent: #4af626;
    --color-border: #1a2d3d;
    --color-text: #8b9bb4;
    --color-success: #4af626;
    --color-warning: #f59e0b;
    --color-error: #ef4444;
    --color-info: #3b82f6;
    --color-scroll-track: #09131b;
    --color-scroll-thumb: #8b9bb4;
    --color-scroll-thumb-hover: #4af626;
  }
`;
document.head.appendChild(style);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <FloatingWindow />
  </React.StrictMode>,
);
