import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { logout } from '../api/auth'
import {
  LayoutDashboard,
  PenLine,
  BookOpen,
  TrendingUp,
  Brain,
  LogOut,
  Menu,
  Target,
  Mic,
  Headphones,
  MessageSquare,
} from 'lucide-react'

const navItems = [
  { to: '/dashboard',  icon: LayoutDashboard,  label: 'Dashboard' },
  { to: '/writing',    icon: PenLine,          label: 'Writing Coach' },
  { to: '/reading',    icon: BookOpen,         label: 'Reading Coach' },
  { to: '/speaking',   icon: Mic,              label: 'Speaking Coach' },
  { to: '/listening',  icon: Headphones,       label: 'Listening Coach' },
  { to: '/chat',       icon: MessageSquare,    label: 'Chat Coach' },
  { to: '/progress',   icon: TrendingUp,       label: 'Progress' },
  { to: '/memory',     icon: Brain,            label: 'Memory' },
]

export default function AppShell({ children }) {
  const { user, logoutUser } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = async () => {
    try { await logout() } catch {}
    logoutUser()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex bg-gray-950">

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-gray-900 border-r border-gray-800
        flex flex-col z-30 transform transition-transform duration-200
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:relative lg:translate-x-0 lg:flex
      `}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-800">
          <Target className="text-brand-500 w-7 h-7 flex-shrink-0" />
          <div>
            <p className="font-bold text-white text-sm leading-tight">
              IELTS MemoryCoach
            </p>
            <p className="text-gray-500 text-xs">AI-powered coaching</p>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm
                font-medium transition-colors
                ${isActive
                  ? 'bg-brand-500/15 text-brand-400'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }
              `}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User + logout */}
        <div className="px-3 py-4 border-t border-gray-800">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center
                            justify-center text-white text-sm font-bold flex-shrink-0">
              {(user?.full_name || user?.email || '?')[0].toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-white text-sm font-medium truncate">
                {user?.full_name || user?.username || 'User'}
              </p>
              <p className="text-gray-500 text-xs truncate">{user?.email}</p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl
                       text-sm text-gray-400 hover:text-white hover:bg-gray-800
                       transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center gap-4 px-4 py-3
                           bg-gray-900 border-b border-gray-800">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-400 hover:text-white"
          >
            <Menu className="w-6 h-6" />
          </button>
          <div className="flex items-center gap-2">
            <Target className="text-brand-500 w-5 h-5" />
            <span className="font-bold text-white text-sm">IELTS MemoryCoach</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}