import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { createProfile } from '../api/progress'
import { Target } from 'lucide-react'

const focusOptions = ['Writing', 'Reading', 'Speaking', 'Listening']

export default function Onboarding() {
  const { user, loginUser } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    name: user?.full_name || '',
    target_score: 7.0,
    test_date: '',
    current_focus: 'Writing'
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await createProfile(form)
      // Refresh user context with updated learner_id
      const token = localStorage.getItem('token')
      loginUser(token, { ...user, learner_id: 'linked' })
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create profile.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4
                    bg-gray-950">
      <div className="w-full max-w-lg">

        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-brand-500/20 flex items-center
                          justify-center mx-auto mb-4">
            <Target className="w-8 h-8 text-brand-500" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">
            Set up your coaching profile
          </h1>
          <p className="text-gray-400">
            Help your coach personalise your IELTS preparation journey
          </p>
        </div>

        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-500/10 border border-red-500/30
                              rounded-lg p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Your name
              </label>
              <input
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white placeholder-gray-500
                           focus:outline-none focus:border-brand-500
                           transition-colors"
                placeholder="e.g. Amina"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Target IELTS band score
              </label>
              <select
                value={form.target_score}
                onChange={e => setForm(p => ({
                  ...p, target_score: parseFloat(e.target.value)
                }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white focus:outline-none
                           focus:border-brand-500 transition-colors"
              >
                {[5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9].map(score => (
                  <option key={score} value={score}>Band {score}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Target test date (optional)
              </label>
              <input
                type="date"
                value={form.test_date}
                onChange={e => setForm(p => ({
                  ...p, test_date: e.target.value
                }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-3 text-white focus:outline-none
                           focus:border-brand-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Where do you want to start?
              </label>
              <div className="grid grid-cols-2 gap-3">
                {focusOptions.map(option => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setForm(p => ({
                      ...p, current_focus: option
                    }))}
                    className={`py-3 px-4 rounded-xl border text-sm font-medium
                                transition-colors
                      ${form.current_focus === option
                        ? 'border-brand-500 bg-brand-500/15 text-brand-400'
                        : 'border-gray-700 text-gray-400 hover:border-gray-600'
                      }`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !form.name}
              className="w-full bg-brand-500 hover:bg-brand-600
                         disabled:opacity-50 text-white font-semibold
                         py-3 px-4 rounded-xl transition-colors mt-2"
            >
              {loading ? 'Setting up...' : 'Start my coaching journey →'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}