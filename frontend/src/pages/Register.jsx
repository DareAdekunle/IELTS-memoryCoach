import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register, googleLogin } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const [form, setForm] = useState({
    email: '', username: '', password: '', full_name: ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { loginUser } = useAuth()
  const navigate = useNavigate()

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await register(form)
      loginUser(res.data.access_token, res.data)
      navigate('/onboarding')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">🎯 IELTS MemoryCoach</h1>
          <p className="text-gray-400">Start your personalised IELTS journey</p>
        </div>

        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8">
          <h2 className="text-xl font-semibold text-white mb-6">Create account</h2>

          <button
            onClick={googleLogin}
            className="w-full flex items-center justify-center gap-3 bg-white
                       text-gray-900 font-medium py-3 px-4 rounded-xl
                       hover:bg-gray-100 transition-colors mb-6"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-gray-800" />
            <span className="text-gray-500 text-sm">or</span>
            <div className="flex-1 h-px bg-gray-800" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Full name</label>
              <input
                name="full_name"
                value={form.full_name}
                onChange={handleChange}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white placeholder-gray-500
                           focus:outline-none focus:border-brand-500 transition-colors"
                placeholder="Your full name"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Username</label>
              <input
                name="username"
                value={form.username}
                onChange={handleChange}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white placeholder-gray-500
                           focus:outline-none focus:border-brand-500 transition-colors"
                placeholder="Choose a username"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Email address</label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white placeholder-gray-500
                           focus:outline-none focus:border-brand-500 transition-colors"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Password</label>
              <input
                type="password"
                name="password"
                value={form.password}
                onChange={handleChange}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white placeholder-gray-500
                           focus:outline-none focus:border-brand-500 transition-colors"
                placeholder="Choose a strong password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50
                         text-white font-semibold py-3 px-4 rounded-xl
                         transition-colors"
            >
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-500 hover:text-brand-400">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}