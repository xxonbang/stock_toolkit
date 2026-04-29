import { HashRouter, Routes, Route, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Portfolio from './pages/Portfolio'
import AutoTrader from './pages/AutoTrader'
import Scanner from './pages/Scanner'
import StockInsight from './pages/StockInsight'
import Login from './pages/Login'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './lib/AuthContext'


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

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    // 즉시 실행 + DOM 레이아웃 안정화 후 재실행 (Outlet 교체 시 레이아웃 시프트 대응)
    window.scrollTo(0, 0);
    const raf = requestAnimationFrame(() => window.scrollTo(0, 0));
    const timer = setTimeout(() => window.scrollTo(0, 0), 100);
    return () => { cancelAnimationFrame(raf); clearTimeout(timer); };
  }, [pathname]);
  return null;
}

export default function App() {
  const { dark, toggle } = useTheme();

  useEffect(() => {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  }, []);

  return (
    <HashRouter>
      <AuthProvider>
        <ScrollToTop />
        <div className="min-h-screen pb-4 no-select" style={{ background: 'var(--bg)' }}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<ProtectedRoute><Dashboard onToggleTheme={toggle} isDark={dark} /></ProtectedRoute>}>
              <Route index element={null} />
              <Route path="portfolio" element={<Portfolio />} />
              <Route path="auto-trader" element={<AutoTrader />} />
              <Route path="stock-insight" element={<StockInsight />} />
            </Route>
            <Route path="/scanner" element={<ProtectedRoute><Scanner onToggleTheme={toggle} isDark={dark} /></ProtectedRoute>} />
          </Routes>
        </div>
      </AuthProvider>
    </HashRouter>
  )
}
