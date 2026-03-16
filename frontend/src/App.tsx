import { HashRouter, Routes, Route, NavLink } from 'react-router-dom'
import { BarChart3, Filter, Sun, Moon } from 'lucide-react'
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
  }, [dark]);

  return { dark, toggle: () => setDark(!dark) };
}

export default function App() {
  const { dark, toggle } = useTheme();

  return (
    <HashRouter>
      <div className="min-h-screen pb-20" style={{ background: 'var(--bg)' }}>
        <Routes>
          <Route path="/" element={<Dashboard onToggleTheme={toggle} isDark={dark} />} />
          <Route path="/scanner" element={<Scanner />} />
        </Routes>
        <nav
          className="fixed bottom-0 left-0 right-0 flex"
          style={{
            background: 'var(--bg-nav)',
            borderTop: '1px solid var(--border)',
            boxShadow: 'var(--shadow-nav)',
            paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          }}
        >
          <NavLink to="/" className={({ isActive }) =>
            `flex-1 flex flex-col items-center py-2.5 text-xs font-medium transition ${isActive ? 't-accent' : 't-text-dim'}`
          }>
            <BarChart3 size={20} />
            <span className="mt-0.5">대시보드</span>
          </NavLink>
          <NavLink to="/scanner" className={({ isActive }) =>
            `flex-1 flex flex-col items-center py-2.5 text-xs font-medium transition ${isActive ? 't-accent' : 't-text-dim'}`
          }>
            <Filter size={20} />
            <span className="mt-0.5">종목 스캐너</span>
          </NavLink>
        </nav>
      </div>
    </HashRouter>
  )
}
