import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getSummary, getSkillRanks, getInsights } from '../api/progress'
import {
  PenLine, BookOpen, TrendingUp, Brain, Target, Zap, Trophy,
  ChevronRight, Mic, Headphones, AlertTriangle, ArrowUpRight,
  Sparkles, Clock,
} from 'lucide-react'

const SECTION_CONFIG = {
  Writing:   { icon: PenLine,    color: 'text-violet-600', bg: 'bg-violet-50',  border: 'border-violet-100' },
  Reading:   { icon: BookOpen,   color: 'text-blue-600',   bg: 'bg-blue-50',    border: 'border-blue-100' },
  Speaking:  { icon: Mic,        color: 'text-emerald-600',bg: 'bg-emerald-50', border: 'border-emerald-100' },
  Listening: { icon: Headphones, color: 'text-amber-600',  bg: 'bg-amber-50',   border: 'border-amber-100' },
}

const QUICK_ACTIONS = [
  { to: '/writing',   icon: PenLine,    title: 'Writing Coach',   desc: 'Submit an essay for AI scoring & feedback',    color: 'text-violet-600', bg: 'bg-violet-50' },
  { to: '/reading',   icon: BookOpen,   title: 'Reading Coach',   desc: 'Practice passages matched to your band level', color: 'text-blue-600',   bg: 'bg-blue-50' },
  { to: '/speaking',  icon: Mic,        title: 'Speaking Coach',  desc: '3-part session with AI examiner',              color: 'text-emerald-600',bg: 'bg-emerald-50' },
  { to: '/listening', icon: Headphones, title: 'Listening Coach', desc: 'Listen once, answer, get instant feedback',    color: 'text-amber-600',  bg: 'bg-amber-50' },
  { to: '/chat',      icon: Sparkles,   title: 'IELTS Tutor',     desc: 'Chat with your memory-aware AI tutor',         color: 'text-brand-600',  bg: 'bg-brand-50' },
  { to: '/progress',  icon: TrendingUp, title: 'Progress',        desc: 'Track score trends and skill growth',          color: 'text-indigo-600', bg: 'bg-indigo-50' },
]

function StatCard({ icon: Icon, label, value, color, bg }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5">
      <div className={'w-9 h-9 rounded-xl flex items-center justify-center mb-3 ' + bg}>
        <Icon className={'w-4.5 h-4.5 ' + color + ' w-[18px] h-[18px]'} />
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-gray-500 text-sm mt-0.5">{label}</p>
    </div>
  )
}

function SectionBandCard({ section, band }) {
  const cfg = SECTION_CONFIG[section]
  const Icon = cfg.icon
  return (
    <div className={'bg-white rounded-2xl border p-4 ' + cfg.border}>
      <div className="flex items-center gap-2 mb-2">
        <div className={'w-7 h-7 rounded-lg flex items-center justify-center ' + cfg.bg}>
          <Icon className={'w-3.5 h-3.5 ' + cfg.color} />
        </div>
        <span className="text-gray-500 text-xs font-medium">{section}</span>
      </div>
      <p className="text-gray-900 font-bold text-lg">
        {band !== null ? `Band ${band.toFixed(1)}` : <span className="text-gray-400 text-base font-normal">No data yet</span>}
      </p>
    </div>
  )
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function Dashboard() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [skills, setSkills] = useState([])
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getSummary(),
      getSkillRanks(),
      getInsights().catch(() => null),
    ]).then(([sumRes, skillRes, insRes]) => {
      setSummary(sumRes.data)
      setSkills(skillRes.data.skills || [])
      setInsights(insRes?.data || null)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const firstName = user?.full_name?.split(' ')[0] || user?.username || 'there'
  const overallBand = insights?.overall_band_display || summary?.overall_band_display || null
  const assessedSkills = skills.filter(s => s.total_evidence > 0)
  const weakest = assessedSkills.length
    ? [...assessedSkills].sort((a, b) => (a.band ?? 0) - (b.band ?? 0))[0]
    : null

  const hasSectionBands = insights?.section_bands &&
    Object.values(insights.section_bands).some(v => v !== null)

  return (
    <div className="p-6 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-8">
        <p className="text-gray-500 text-sm mb-1">{getGreeting()},</p>
        <h1 className="text-2xl font-bold text-gray-900">{firstName} 👋</h1>
        {overallBand && (
          <div className="mt-3 inline-flex items-center gap-2 bg-brand-50 border border-brand-100 rounded-xl px-4 py-2">
            <Trophy className="w-4 h-4 text-brand-600" />
            <span className="text-brand-700 font-semibold text-sm">Overall Band {overallBand}</span>
          </div>
        )}
      </div>

      {/* Stats */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-gray-200 p-5 h-28 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard icon={PenLine}    label="Writing attempts"  value={summary?.writing_attempts ?? 0}  color="text-violet-600" bg="bg-violet-50" />
          <StatCard icon={BookOpen}   label="Reading attempts"  value={summary?.reading_attempts ?? 0}  color="text-blue-600"   bg="bg-blue-50" />
          <StatCard icon={Brain}      label="Active memories"   value={summary?.active_memories ?? 0}   color="text-brand-600"  bg="bg-brand-50" />
          <StatCard icon={Trophy}     label="Skills tracked"    value={assessedSkills.length}           color="text-amber-600"  bg="bg-amber-50" />
        </div>
      )}

      {/* Section bands */}
      {hasSectionBands && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {['Writing', 'Reading', 'Speaking', 'Listening'].map(s => (
            <SectionBandCard key={s} section={s} band={insights.section_bands[s]} />
          ))}
        </div>
      )}

      {/* Tutor suggestion banner */}
      {weakest && (
        <div className="bg-brand-600 rounded-2xl p-5 mb-8 flex items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center flex-shrink-0">
              <Zap className="w-4.5 h-4.5 text-white w-[18px] h-[18px]" />
            </div>
            <div>
              <p className="text-white/80 text-xs font-medium mb-0.5">Your tutor suggests</p>
              <p className="text-white font-semibold">{weakest.skill_name}</p>
              <p className="text-white/70 text-sm">{weakest.category_name} · {weakest.band_display || 'Unranked'}</p>
            </div>
          </div>
          <Link
            to="/chat"
            className="flex items-center gap-1.5 bg-white text-brand-700 text-sm font-semibold px-4 py-2 rounded-xl hover:bg-brand-50 transition-colors flex-shrink-0"
          >
            Start drill <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">

        {/* Quick actions */}
        <div className="lg:col-span-2 space-y-6">

          {/* Cross-section insights */}
          {insights?.cross_section_patterns?.length > 0 && (
            <div>
              <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                Cross-section insights
              </h2>
              <div className="space-y-3">
                {insights.cross_section_patterns.slice(0, 2).map((pattern, i) => (
                  <div key={i} className="bg-white rounded-2xl border border-gray-200 p-4">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 bg-amber-50 rounded-xl flex items-center justify-center flex-shrink-0">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {pattern.sections_affected.map(s => {
                            const cfg = SECTION_CONFIG[s]
                            return cfg ? (
                              <span key={s} className={'text-xs font-medium px-2 py-0.5 rounded-full ' + cfg.bg + ' ' + cfg.color}>
                                {s}
                              </span>
                            ) : null
                          })}
                          <span className={'text-xs font-medium px-2 py-0.5 rounded-full ' +
                            (pattern.severity === 'high' ? 'bg-red-50 text-red-600' :
                             pattern.severity === 'medium' ? 'bg-amber-50 text-amber-600' :
                             'bg-blue-50 text-blue-600')}>
                            {pattern.severity}
                          </span>
                        </div>
                        <p className="text-gray-700 text-sm mb-1">{pattern.pattern}</p>
                        <Link to="/chat" className="text-brand-600 text-xs font-medium hover:underline inline-flex items-center gap-1">
                          Work on this <ArrowUpRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick actions */}
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-3">Continue learning</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {QUICK_ACTIONS.map(({ to, icon: Icon, title, desc, color, bg }) => (
                <Link
                  key={to}
                  to={to}
                  className="flex items-center gap-3 p-4 bg-white rounded-2xl border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all group"
                >
                  <div className={'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ' + bg}>
                    <Icon className={'w-5 h-5 ' + color} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-900 font-semibold text-sm">{title}</p>
                    <p className="text-gray-500 text-xs truncate">{desc}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-gray-400 flex-shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel: skills */}
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-gray-900">Writing skills</h2>

          <div className="bg-white rounded-2xl border border-gray-200 p-4">
            {skills.length === 0 ? (
              <div className="text-center py-6">
                <div className="w-10 h-10 bg-gray-50 rounded-xl flex items-center justify-center mx-auto mb-3">
                  <PenLine className="w-5 h-5 text-gray-300" />
                </div>
                <p className="text-gray-500 text-sm">Submit a writing essay to see your skill profile</p>
                <Link to="/writing" className="mt-3 inline-flex items-center gap-1 text-brand-600 text-sm font-medium hover:underline">
                  Start writing <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {skills.slice(0, 7).map(skill => {
                  const band = skill.band ?? null
                  const pct = band !== null ? Math.min(100, ((band - 4.0) / 5.0) * 100) : 0
                  return (
                    <div key={skill.skill_id}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-gray-700 text-xs font-medium truncate flex-1">{skill.skill_name}</span>
                        <span className="text-gray-500 text-xs ml-2 flex-shrink-0 font-mono">
                          {band !== null ? `B${band.toFixed(1)}` : '—'}
                        </span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full transition-all duration-500"
                          style={{ width: pct + '%' }}
                        />
                      </div>
                    </div>
                  )
                })}
                <Link to="/skills" className="mt-2 flex items-center gap-1 text-brand-600 text-xs font-medium hover:underline">
                  View all skills <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            )}
          </div>

          {/* Memory quick link */}
          <Link
            to="/memory"
            className="flex items-center gap-3 p-4 bg-white rounded-2xl border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all group"
          >
            <div className="w-10 h-10 bg-brand-50 rounded-xl flex items-center justify-center flex-shrink-0">
              <Brain className="w-5 h-5 text-brand-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-gray-900 font-semibold text-sm">Memory Timeline</p>
              <p className="text-gray-500 text-xs">{summary?.active_memories ?? 0} active memories</p>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-gray-400 flex-shrink-0" />
          </Link>
        </div>
      </div>
    </div>
  )
}
