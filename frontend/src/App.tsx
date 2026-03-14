import { HashRouter, Routes, Route, NavLink } from 'react-router-dom'
import { BarChart3, Filter } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Scanner from './pages/Scanner'

export default function App() {
  return (
    <HashRouter>
      <div className="min-h-screen bg-gray-50 pb-14">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scanner" element={<Scanner />} />
        </Routes>
        <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex shadow-[0_-1px_3px_rgba(0,0,0,0.05)]">
          <NavLink to="/" className={({ isActive }) =>
            `flex-1 flex flex-col items-center py-2.5 text-xs font-medium transition ${isActive ? 'text-blue-600' : 'text-gray-400 hover:text-gray-600'}`
          }>
            <BarChart3 size={20} />
            <span className="mt-0.5">대시보드</span>
          </NavLink>
          <NavLink to="/scanner" className={({ isActive }) =>
            `flex-1 flex flex-col items-center py-2.5 text-xs font-medium transition ${isActive ? 'text-blue-600' : 'text-gray-400 hover:text-gray-600'}`
          }>
            <Filter size={20} />
            <span className="mt-0.5">종목 스캐너</span>
          </NavLink>
        </nav>
      </div>
    </HashRouter>
  )
}
