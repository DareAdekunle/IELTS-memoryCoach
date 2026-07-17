import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { logout } from '../api/auth'
import {
  LayoutDashboard, PenLine, BookOpen, TrendingUp, Brain,
  LogOut, Menu, X, Target, Mic, Headphones, MessageSquare,
  Trophy, ChevronRight,
} from 'lucide-react'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    ],
  },
  {
    label: 'Practice',
    items: [
      { to: '/writing',   icon: PenLine,      label: 'Writing Coach' },
      { to: '/reading',   icon: BookOpen,     label: 'Reading Coach' },
      { to: '/speaking',  icon: Mic,          label: 'Speaking Coach' },
      { to: '/listening', icon: Headphones,   label: 'Listening Coach' },
      { to: '/chat',      icon: MessageSquare,label: 'IELTS Tutor' },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { to: '/progress', icon: TrendingUp, label: 'Progress' },
      { to: '/memory',   icon: Brain,      label: 'Memory' },
      { to: '/skills',   icon: Trophy,     label: 'Skill Mastery' },
    ],
  },
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

  const initials = (user?.full_name || user?.email || '?')
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-gray-100">
        <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <Target className="w-4.5 h-4.5 text-white w-[18px] h-[18px]" />
        </div>
        <div>
          <p className="font-700 text-gray-900 text-sm font-bold leading-tight">MemoryCoach</p>
          <p className="text-gray-400 text-xs">IELTS AI Tutor</p>
        </div>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {navGroups.map(group => (
          <div key={group.label}>
            <p className="text-[10px] font-600 text-gray-400 uppercase tracking-widest px-3 mb-1.5 font-semibold">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ' +
                    (isActive
                      ? 'bg-brand-50 text-brand-700 '
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50')
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon className={'w-[18px] h-[18px] flex-shrink-0 ' + (isActive ? 'text-brand-600' : 'text-gray-400')} />
                      <span className="flex-1">{label}</span>
                      {isActive && <div className="w-1.5 h-1.5 rounded-full bg-brand-500 flex-shrink-0" />}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* User + logout */}
      <div className="px-3 py-4 border-t border-gray-100">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-gray-50 mb-2">
          <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-gray-900 text-sm font-semibold truncate">
              {user?.full_name || user?.username || 'User'}
            </p>
            <p className="text-gray-400 text-xs truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-50 transition-colors"
        >
          <LogOut className="w-[18px] h-[18px]" />
          Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen flex bg-slate-50">

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={
        'fixed top-0 left-0 h-full w-60 bg-white border-r border-gray-200 ' +
        'flex flex-col z-30 transform transition-transform duration-200 ' +
        (sidebarOpen ? 'translate-x-0' : '-translate-x-full ') +
        'lg:relative lg:translate-x-0 lg:flex'
      }>
        <SidebarContent />
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 px-4 py-3 bg-white border-b border-gray-200">
          <button onClick={() => setSidebarOpen(v => !v)} className="text-gray-500 hover:text-gray-900">
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-brand-600 rounded-md flex items-center justify-center">
              <Target className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-gray-900 text-sm">MemoryCoach</span>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
