import { HashRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Scanner from './pages/Scanner'

export default function App() {
  return (
    <HashRouter>
      <div className="min-h-screen bg-gray-950 text-white pb-16">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scanner" element={<Scanner />} />
        </Routes>
        <nav className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 flex">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `flex-1 py-3 text-center text-sm font-medium ${isActive ? 'text-emerald-400' : 'text-gray-500'}`
            }
          >
            대시보드
          </NavLink>
          <NavLink
            to="/scanner"
            className={({ isActive }) =>
              `flex-1 py-3 text-center text-sm font-medium ${isActive ? 'text-emerald-400' : 'text-gray-500'}`
            }
          >
            종목 스캐너
          </NavLink>
        </nav>
      </div>
    </HashRouter>
  )
}
