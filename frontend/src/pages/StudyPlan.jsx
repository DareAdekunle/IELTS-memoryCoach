import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  getMySchedule, setupSchedule, cancelSchedule,
  getCalendarConnectUrl, disconnectCalendar,
} from '../api/schedule'
import {
  Calendar, Clock, Trash2, Check, AlertCircle,
  ExternalLink, Unlink, RefreshCw,
} from 'lucide-react'

const DAYS     = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const DURATIONS = [15, 30, 45, 60]

function detectTimezone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone } catch { return 'UTC' }
}

export default function StudyPlan() {
  const [searchParams] = useSearchParams()
  const [schedule, setSchedule] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [saving,  setSaving]    = useState(false)
  const [banner,  setBanner]    = useState(null) // {type:'success'|'error', msg}

  // Edit form state
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    days: ['Mon', 'Wed', 'Fri'],
    study_time: '07:00',
    duration_minutes: 30,
    timezone: detectTimezone(),
  })

  useEffect(() => {
    loadSchedule()
    // Handle OAuth callback redirects
    const calendarStatus = searchParams.get('calendar')
    const calendarError  = searchParams.get('error')
    if (calendarStatus === 'connected') {
      setBanner({ type: 'success', msg: 'Google Calendar connected — study sessions added to your calendar!' })
      loadSchedule()
    } else if (calendarError) {
      const msgs = {
        bad_state:       'Calendar connection failed: invalid state.',
        token_exchange:  'Calendar connection failed: could not exchange token.',
        no_schedule:     'Set up a study schedule before connecting Google Calendar.',
        calendar_create: 'Schedule saved, but could not create calendar events. Try reconnecting.',
      }
      setBanner({ type: 'error', msg: msgs[calendarError] || 'Calendar connection failed.' })
    }
  }, [])

  const loadSchedule = async () => {
    setLoading(true)
    try {
      const data = await getMySchedule()
      if (data.has_schedule) {
        setSchedule(data)
        setForm({
          days:             data.days,
          study_time:       data.study_time,
          duration_minutes: data.duration_minutes,
          timezone:         data.timezone,
        })
      } else {
        setSchedule(null)
        setEditing(true) // no schedule yet — open form
      }
    } catch {
      setSchedule(null)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (form.days.length === 0) {
      setBanner({ type: 'error', msg: 'Select at least one study day.' })
      return
    }
    setSaving(true)
    setBanner(null)
    try {
      const saved = await setupSchedule(form)
      setSchedule({ has_schedule: true, ...saved })
      setEditing(false)
      setBanner({ type: 'success', msg: 'Study schedule saved.' })
    } catch (err) {
      setBanner({ type: 'error', msg: err.response?.data?.detail || 'Could not save schedule.' })
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = async () => {
    if (!window.confirm('Cancel your study schedule? This will remove calendar events too.')) return
    try {
      await cancelSchedule()
      setSchedule(null)
      setEditing(true)
      setBanner({ type: 'success', msg: 'Schedule cancelled.' })
    } catch {
      setBanner({ type: 'error', msg: 'Could not cancel schedule.' })
    }
  }

  const handleConnectCalendar = async () => {
    try {
      const { auth_url } = await getCalendarConnectUrl()
      window.location.href = auth_url
    } catch (err) {
      setBanner({ type: 'error', msg: err.response?.data?.detail || 'Could not start Google Calendar connection.' })
    }
  }

  const handleDisconnectCalendar = async () => {
    if (!window.confirm('Disconnect Google Calendar? Future events will be deleted.')) return
    try {
      await disconnectCalendar()
      await loadSchedule()
      setBanner({ type: 'success', msg: 'Google Calendar disconnected.' })
    } catch {
      setBanner({ type: 'error', msg: 'Could not disconnect calendar.' })
    }
  }

  const toggleDay = (day) => {
    setForm(f => ({
      ...f,
      days: f.days.includes(day) ? f.days.filter(d => d !== day) : [...f.days, day],
    }))
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center text-gray-400">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading schedule…
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Calendar className="w-6 h-6 text-brand-500" /> Study Plan
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Set when you study — Qonda adds the sessions to your Google Calendar.
        </p>
      </div>

      {/* Banner */}
      {banner && (
        <div className={'flex items-start gap-3 p-4 rounded-xl mb-6 border ' +
          (banner.type === 'success'
            ? 'bg-green-50 border-green-200 text-green-800'
            : 'bg-red-50 border-red-200 text-red-700')}>
          {banner.type === 'success'
            ? <Check className="w-5 h-5 flex-shrink-0 mt-0.5" />
            : <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />}
          <p className="text-sm">{banner.msg}</p>
        </div>
      )}

      {/* ── Current schedule (view mode) ─────────────────────────────────── */}
      {schedule && !editing && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Your schedule</h2>
              <button
                onClick={() => setEditing(true)}
                className="text-sm text-brand-600 hover:text-brand-700 font-medium"
              >
                Edit
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex gap-2 flex-wrap">
                {DAYS.map(d => (
                  <span
                    key={d}
                    className={'px-3 py-1.5 rounded-lg text-sm font-medium ' +
                      (schedule.days.includes(d)
                        ? 'bg-brand-100 text-brand-700'
                        : 'bg-gray-100 text-gray-300')}
                  >
                    {d}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4" /> {schedule.study_time}
                </span>
                <span>{schedule.duration_minutes} min per session</span>
                <span className="text-gray-400">{schedule.timezone}</span>
              </div>
            </div>

            <button
              onClick={handleCancel}
              className="mt-4 flex items-center gap-1.5 text-sm text-red-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" /> Cancel schedule
            </button>
          </div>

          {/* Google Calendar card */}
          <div className="bg-white rounded-2xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-1">Google Calendar</h2>
            {schedule.has_calendar ? (
              <div>
                <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-xl px-3 py-2 mb-4">
                  <Check className="w-4 h-4" />
                  Connected as <strong>{schedule.google_email}</strong>
                </div>
                <p className="text-sm text-gray-500 mb-4">
                  Your study sessions are in your Google Calendar with reminders 10 min before each session.
                </p>
                <button
                  onClick={handleDisconnectCalendar}
                  className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-500 transition-colors"
                >
                  <Unlink className="w-4 h-4" /> Disconnect Google Calendar
                </button>
              </div>
            ) : (
              <div>
                <p className="text-sm text-gray-500 mb-4">
                  Add your study sessions directly to Google Calendar so they sit alongside
                  your meetings and commutes — exactly where a juggler needs them.
                </p>
                <button
                  onClick={handleConnectCalendar}
                  className="flex items-center gap-2 bg-white border border-gray-300 rounded-xl
                             px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  Connect Google Calendar
                  <ExternalLink className="w-3.5 h-3.5 text-gray-400" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Schedule form (create / edit) ─────────────────────────────────── */}
      {(!schedule || editing) && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-6">
          <h2 className="font-semibold text-gray-900">
            {schedule ? 'Edit schedule' : 'Set up your study schedule'}
          </h2>

          {/* Days */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Which days will you study?
            </label>
            <div className="flex gap-2 flex-wrap">
              {DAYS.map(day => {
                const active = form.days.includes(day)
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
              What time? <span className="text-gray-400 font-normal text-xs">({form.timezone})</span>
            </label>
            <input
              type="time"
              value={form.study_time}
              onChange={e => setForm(f => ({ ...f, study_time: e.target.value }))}
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
                  onClick={() => setForm(f => ({ ...f, duration_minutes: d }))}
                  className={'py-2.5 rounded-xl text-sm font-medium border transition-colors ' +
                    (form.duration_minutes === d
                      ? 'bg-brand-500 border-brand-500 text-white'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300')}
                >
                  {d} min
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || form.days.length === 0}
              className="flex-1 bg-brand-500 hover:bg-brand-600 disabled:opacity-50
                         text-white font-semibold py-3 rounded-xl transition-colors"
            >
              {saving ? 'Saving…' : 'Save schedule'}
            </button>
            {editing && schedule && (
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="px-4 py-3 rounded-xl border border-gray-200 text-gray-600
                           hover:bg-gray-50 transition-colors text-sm"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
