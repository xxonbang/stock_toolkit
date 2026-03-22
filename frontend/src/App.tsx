import { HashRouter, Routes, Route } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Scanner from './pages/Scanner'


function useTheme() {
  const [dark, setDark] = useState(() => {
    if (typeof window === 'undefined') return false;
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
    document.querySelectorAll('meta[name="theme-color"]').forEach(meta => {
      meta.setAttribute('content', dark ? '#0b0f14' : '#f8fafc');
    });
  }, [dark]);

  return { dark, toggle: () => setDark(!dark) };
}

export default function App() {
  const { dark, toggle } = useTheme();

  useEffect(() => {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    window.scrollTo(0, 0);
  }, []);

  return (
    <HashRouter>
      <div className="min-h-screen pb-4" style={{ background: 'var(--bg)' }}>
        <Routes>
          <Route path="/" element={<Dashboard onToggleTheme={toggle} isDark={dark} />} />
          <Route path="/portfolio" element={<Dashboard onToggleTheme={toggle} isDark={dark} page="portfolio" />} />
          <Route path="/scanner" element={<Scanner onToggleTheme={toggle} isDark={dark} />} />
          <Route path="/auto-trader" element={<Dashboard onToggleTheme={toggle} isDark={dark} page="auto-trader" />} />
        </Routes>
      </div>
    </HashRouter>
  )
}
