import { HashRouter, Routes, Route, NavLink } from 'react-router-dom'
import { TrendingUp, Filter, Sun, Moon } from 'lucide-react'
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

  useEffect(() => {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    window.scrollTo(0, 0);
  }, []);

  return (
    <HashRouter>
      <div className="min-h-screen pb-4 pt-12" style={{ background: 'var(--bg)' }}>
        {/* 상단 메뉴바 (대시보드 / 종목 스캐너) */}
        <nav
          className="fixed top-0 left-0 right-0 z-20 flex"
          style={{
            background: 'var(--bg-nav)',
            borderBottom: '1px solid var(--border)',
            boxShadow: 'var(--shadow-nav)',
          }}
        >
          <NavLink to="/" className={({ isActive }) =>
            `flex-1 flex flex-col items-center py-2 text-xs font-medium transition ${isActive ? 't-accent' : 't-text-dim'}`
          }>
            <TrendingUp size={18} />
            <span className="mt-0.5">대시보드</span>
          </NavLink>
          <NavLink to="/scanner" className={({ isActive }) =>
            `flex-1 flex flex-col items-center py-2 text-xs font-medium transition ${isActive ? 't-accent' : 't-text-dim'}`
          }>
            <Filter size={18} />
            <span className="mt-0.5">종목 스캐너</span>
          </NavLink>
        </nav>
        <Routes>
          <Route path="/" element={<Dashboard onToggleTheme={toggle} isDark={dark} />} />
          <Route path="/scanner" element={<Scanner />} />
        </Routes>
      </div>
    </HashRouter>
  )
}
