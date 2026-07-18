import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { createProfile } from '../api/progress'
import { setupSchedule } from '../api/schedule'
import { Target, Calendar, ChevronRight, Clock, Check } from 'lucide-react'

const focusOptions = ['Writing', 'Reading', 'Speaking', 'Listening']

const DAYS   = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const DURATIONS = [15, 30, 45, 60]

function detectTimezone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone } catch { return 'UTC' }
}

export default function Onboarding() {
  const { user, loginUser } = useAuth()
  const navigate = useNavigate()

  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState('')

  // Step 1 — profile
  const [profile, setProfile] = useState({
    name:          user?.full_name || '',
    target_score:  7.0,
    test_date:     '',
    current_focus: 'Writing',
  })

  // Step 2 — schedule
  const [schedule, setSchedule] = useState({
    days:             ['Mon', 'Wed', 'Fri'],
    study_time:       '07:00',
    duration_minutes: 30,
    timezone:         detectTimezone(),
  })

  // ── Step 1 submit ──────────────────────────────────────────────────────────
  const handleProfileSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createProfile(profile)
      const token = localStorage.getItem('token')
      loginUser(token, { ...user, learner_id: 'linked' })
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create profile.')
    } finally {
      setLoading(false)
    }
  }

  // ── Step 2 submit ──────────────────────────────────────────────────────────
  const handleScheduleSubmit = async (skip = false) => {
    if (skip) { navigate('/dashboard'); return }
    setError('')
    setLoading(true)
    try {
      await setupSchedule(schedule)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save schedule.')
    } finally {
      setLoading(false)
    }
  }

  const toggleDay = (day) => {
    setSchedule(s => ({
      ...s,
      days: s.days.includes(day)
        ? s.days.filter(d => d !== day)
        : [...s.days, day],
    }))
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-slate-50">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-brand-500/20 flex items-center justify-center mx-auto mb-4">
            {step === 1
              ? <Target className="w-8 h-8 text-brand-500" />
              : <Calendar className="w-8 h-8 text-brand-500" />}
          </div>
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className={'w-2 h-2 rounded-full ' + (step === 1 ? 'bg-brand-500' : 'bg-brand-200')} />
            <div className={'w-2 h-2 rounded-full ' + (step === 2 ? 'bg-brand-500' : 'bg-brand-200')} />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {step === 1 ? 'Set up your coaching profile' : 'Plan your study schedule'}
          </h1>
          <p className="text-gray-500 text-sm">
            {step === 1
              ? 'Help your coach personalise your IELTS preparation journey'
              : 'Qonda will remind you when it\'s time to practice'}
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-8">

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 mb-5">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          {/* ── Step 1: Profile ─────────────────────────────────────────────── */}
          {step === 1 && (
            <form onSubmit={handleProfileSubmit} className="space-y-5">
              <div>
                <label className="block text-sm text-gray-500 mb-1.5">Your name</label>
                <input
                  value={profile.name}
                  onChange={e => setProfile(p => ({ ...p, name: e.target.value }))}
                  required
                  placeholder="e.g. Amina"
                  className="w-full bg-gray-100 border border-gray-200 rounded-xl px-4 py-3
                             text-gray-900 placeholder-gray-400 focus:outline-none
                             focus:border-brand-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-500 mb-1.5">Target IELTS band score</label>
                <select
                  value={profile.target_score}
                  onChange={e => setProfile(p => ({ ...p, target_score: parseFloat(e.target.value) }))}
                  className="w-full bg-gray-100 border border-gray-200 rounded-xl px-4 py-3
                             text-gray-900 focus:outline-none focus:border-brand-500 transition-colors"
                >
                  {[5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9].map(s => (
                    <option key={s} value={s}>Band {s}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-500 mb-1.5">
                  Test date <span className="text-gray-400">(optional)</span>
                </label>
                <input
                  type="date"
                  value={profile.test_date}
                  onChange={e => setProfile(p => ({ ...p, test_date: e.target.value }))}
                  className="w-full bg-gray-100 border border-gray-200 rounded-xl px-4 py-3
                             text-gray-900 focus:outline-none focus:border-brand-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-500 mb-1.5">Where do you want to start?</label>
                <div className="grid grid-cols-2 gap-3">
                  {focusOptions.map(opt => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setProfile(p => ({ ...p, current_focus: opt }))}
                      className={'py-3 px-4 rounded-xl border text-sm font-medium transition-colors ' +
                        (profile.current_focus === opt
                          ? 'border-brand-500 bg-brand-500/15 text-brand-600'
                          : 'border-gray-200 text-gray-500 hover:border-gray-300')}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || !profile.name}
                className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50
                           text-white font-semibold py-3 px-4 rounded-xl transition-colors mt-2
                           flex items-center justify-center gap-2"
              >
                {loading ? 'Setting up...' : <><span>Continue</span><ChevronRight className="w-4 h-4" /></>}
              </button>
            </form>
          )}

          {/* ── Step 2: Study schedule ──────────────────────────────────────── */}
          {step === 2 && (
            <div className="space-y-6">
              {/* Days */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Which days will you study?
                </label>
                <div className="flex gap-2 flex-wrap">
                  {DAYS.map(day => {
                    const active = schedule.days.includes(day)
                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() => toggleDay(day)}
                        className={'px-3 py-2 rounded-xl text-sm font-medium border transition-colors ' +
                          (active
                            ? 'bg-brand-500 border-brand-500 text-white'
                            : 'border-gray-200 text-gray-500 hover:border-gray-300')}
                      >
                        {day}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Time */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Clock className="w-4 h-4 inline mr-1" />
                  What time? <span className="text-gray-400 font-normal">({schedule.timezone})</span>
                </label>
                <input
                  type="time"
                  value={schedule.study_time}
                  onChange={e => setSchedule(s => ({ ...s, study_time: e.target.value }))}
                  className="w-full bg-gray-100 border border-gray-200 rounded-xl px-4 py-3
                             text-gray-900 focus:outline-none focus:border-brand-500 transition-colors"
                />
              </div>

              {/* Duration */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  How long per session?
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {DURATIONS.map(d => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setSchedule(s => ({ ...s, duration_minutes: d }))}
                      className={'py-2.5 rounded-xl text-sm font-medium border transition-colors ' +
                        (schedule.duration_minutes === d
                          ? 'bg-brand-500 border-brand-500 text-white'
                          : 'border-gray-200 text-gray-500 hover:border-gray-300')}
                    >
                      {d} min
                    </button>
                  ))}
                </div>
              </div>

              {/* Calendar hint */}
              <div className="bg-brand-50 border border-brand-100 rounded-xl p-4 flex gap-3">
                <Calendar className="w-5 h-5 text-brand-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-brand-700">
                  After saving, connect Google Calendar from your Study Plan page
                  to get these sessions added directly to your calendar.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  disabled={loading || schedule.days.length === 0}
                  onClick={() => handleScheduleSubmit(false)}
                  className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50
                             text-white font-semibold py-3 px-4 rounded-xl transition-colors
                             flex items-center justify-center gap-2"
                >
                  {loading
                    ? 'Saving...'
                    : <><Check className="w-4 h-4" /><span>Save my study plan</span></>}
                </button>
                <button
                  type="button"
                  onClick={() => handleScheduleSubmit(true)}
                  className="w-full text-gray-400 text-sm py-2 hover:text-gray-600 transition-colors"
                >
                  Skip for now
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
