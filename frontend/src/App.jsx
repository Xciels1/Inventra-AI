/**
 * src/App.jsx
 * ===========
 * Entry point aplikasi React Inventra AI.
 * Inisialisasi global CSS variables dan render Dashboard.
 */

import React from 'react';
import Dashboard from './pages/Dashboard';

// ── Global Styles (CSS variables + reset) ──────────────────
const GLOBAL_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg0: #070d18;
    --bg1: #0d1626;
    --bg2: #111e33;
    --bg3: #172540;
    --border: #1e3050;
    --border2: #243a5e;
    --text: #e8edf5;
    --text2: #8da0b8;
    --text3: #4d6480;
    --teal: #00d4aa;
    --teal2: #00b391;
    --teal-dim: rgba(0, 212, 170, 0.13);
    --amber: #f5a623;
    --amber-dim: rgba(245, 166, 35, 0.13);
    --red: #f0485a;
    --red-dim: rgba(240, 72, 90, 0.13);
    --blue: #4a9eff;
    --blue-dim: rgba(74, 158, 255, 0.13);
    --purple: #a78bfa;
    --purple-dim: rgba(167, 139, 250, 0.13);
    --green: #22c55e;
    --green-dim: rgba(34, 197, 94, 0.13);
    --font-ui: 'DM Sans', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  }

  html, body, #root {
    height: 100%;
    background: var(--bg0);
    color: var(--text);
    font-family: var(--font-ui);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }

  /* Scrollbar styling */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg1); }
  ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--teal); }

  /* Animations */
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }
  @keyframes dpulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
    50%       { box-shadow: 0 0 0 5px rgba(34, 197, 94, 0); }
  }

  /* Animation utilities */
  .animate-spin   { animation: spin .6s linear infinite; }
  .animate-pulse  { animation: pulse 1.5s ease infinite; }
  .animate-fadeUp { animation: fadeUp .2s ease; }
`;

function GlobalStyles() {
  return <style dangerouslySetInnerHTML={{ __html: GLOBAL_STYLE }} />;
}

export default function App() {
  return (
    <>
      <GlobalStyles />
      <Dashboard />
    </>
  );
}
