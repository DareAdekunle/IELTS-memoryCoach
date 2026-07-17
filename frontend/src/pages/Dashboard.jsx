import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getSummary, getSkillRanks, getInsights } from '../api/progress'
import {
  PenLine, BookOpen, TrendingUp, Brain,
  Target, Zap, Trophy, ChevronRight, Mic, Headphones,
  AlertTriangle, ArrowUpRight
} from 'lucide-react'

const BAND_COLORS = {
  Writing:   'text-purple-400 bg-purple-500/10',
  Reading:   'text-blue-400 bg-blue-500/10',
  Speaking:  'text-green-400 bg-green-500/10',
  Listening: 'text-yellow-400 bg-yellow-500/10',
}

const SECTION_ICONS = {
  Writing: PenLine,
  Reading: BookOpen,
  Speaking: Mic,
  Listening: Headphones,
}

function SeverityBadge({ severity }) {
  const styles = {
    high:   'bg-red-500/10 text-red-400 border-red-500/20',
    medium: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    low:    'bg-blue-500/10 text-blue-400 border-blue-500/20',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${styles[severity] || styles.low}`}>
      {severity}
    </span>
  )
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
      getInsights().catch(() => null)
    ]).then(([sumRes, skillRes, insRes]) => {
      setSummary(sumRes.data)
      setSkills(skillRes.data.skills || [])
      setInsights(insRes?.data || null)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const firstName = user?.full_name?.split(' ')[0] || user?.username || 'there'

  // Weakest Writing skill for coach recommendation
  const assessedSkills = skills.filter(s => s.total_evidence > 0)
  const weakest = assessedSkills.length
    ? [...assessedSkills].sort((a, b) => (a.band ?? 0) - (b.band ?? 0))[0]
    : null

  // Overall band from insights
  const overallBand = insights?.overall_band_display || summary?.overall_band_display || '—'

  return (
    <div className="p-6 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-1">
          Welcome back, {firstName} 👋
        </h1>
        <p className="text-gray-400">Your coach is ready — let's keep improving.</p>
      </div>

      {/* Stats row */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-900 rounded-2xl p-5 border border-gray-800 animate-pulse h-24" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Overall band', value: overallBand, icon: Trophy, color: 'text-yellow-400' },
            { label: 'Writing attempts', value: summary?.writing_attempts ?? 0, icon: PenLine, color: 'text-purple-400' },
            { label: 'Active memories', value: summary?.active_memories ?? 0, icon: Brain, color: 'text-green-400' },
            { label: 'Reading attempts', value: summary?.reading_attempts ?? 0, icon: BookOpen, color: 'text-blue-400' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gray-900 rounded-2xl p-5 border border-gray-800">
              <Icon className={`w-5 h-5 ${color} mb-3`} />
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-gray-500 text-sm mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Section bands row */}
      {insights?.section_bands && Object.keys(insights.section_bands).some(s => insights.section_bands[s] !== null) && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {['Writing', 'Reading', 'Speaking', 'Listening'].map(section => {
            const band = insights.section_bands[section]
            const Icon = SECTION_ICONS[section]
            const colorClass = BAND_COLORS[section]
            return (
              <div key={section} className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`w-4 h-4 ${colorClass.split(' ')[0]}`} />
                  <span className="text-gray-400 text-xs">{section}</span>
                </div>
                <p className="text-white font-bold text-lg">
                  {band !== null ? `Band ${band.toFixed(1)}` : 'No band yet'}
                </p>
              </div>
            )
          })}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">

        {/* Quick start + cross-section insights */}
        <div className="lg:col-span-2 space-y-6">

          {/* Cross-section insights */}
          {insights?.cross_section_patterns?.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
                Cross-section insights
              </h2>
              <div className="space-y-3">
                {insights.cross_section_patterns.slice(0, 3).map((pattern, i) => (
                  <div key={i} className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex flex-wrap gap-1.5">
                        {pattern.sections_affected.map(s => {
                          const Icon = SECTION_ICONS[s]
                          return (
                            <span key={s} className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${BAND_COLORS[s]}`}>
                              <Icon className="w-3 h-3" />{s}
                            </span>
                          )
                        })}
                      </div>
                      <SeverityBadge severity={pattern.severity} />
                    </div>
                    <p className="text-gray-300 text-sm mb-2">{pattern.pattern}</p>
                    <p className="text-gray-500 text-xs leading-relaxed">{pattern.recommendation}</p>
                    <Link
                      to="/chat"
                      className="inline-flex items-center gap-1 text-brand-400 text-xs mt-2 hover:opacity-80"
                    >
                      Work on this with your Tutor <ArrowUpRight className="w-3 h-3" />
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick start */}
          <div>
            <h2 className="text-lg font-semibold text-white mb-3">Quick start</h2>
            <div className="space-y-3">
              {[
                { to: '/writing',   icon: PenLine,    title: 'Writing Coach',   desc: 'Submit an essay and get personalised AI feedback',           color: 'bg-purple-500/15 text-purple-400' },
                { to: '/reading',   icon: BookOpen,   title: 'Reading Coach',   desc: 'Practice with passages matched to your current band level',  color: 'bg-blue-500/15 text-blue-400' },
                { to: '/speaking',  icon: Mic,        title: 'Speaking Coach',  desc: 'Complete a 3-part speaking session with AI examiner',        color: 'bg-green-500/15 text-green-400' },
                { to: '/listening', icon: Headphones, title: 'Listening Coach', desc: 'Listen once, answer questions, get instant feedback',        color: 'bg-yellow-500/15 text-yellow-400' },
                { to: '/progress',  icon: TrendingUp, title: 'Progress',        desc: 'See your score trends and skill improvements over time',     color: 'bg-brand-500/15 text-brand-400' },
                { to: '/memory',    icon: Brain,      title: 'Memory Timeline', desc: 'See everything your coach has learned about you',            color: 'bg-pink-500/15 text-pink-400' },
              ].map(({ to, icon: Icon, title, desc, color }) => (
                <Link
                  key={to}
                  to={to}
                  className="flex items-center gap-4 p-4 bg-gray-900 rounded-2xl border border-gray-800 hover:border-gray-700 transition-colors group"
                >
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium">{title}</p>
                    <p className="text-gray-500 text-sm truncate">{desc}</p>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-600 group-hover:text-gray-400 flex-shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Skill focus panel */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Skill focus</h2>

          {/* Coach recommendation */}
          {weakest && (
            <div className="bg-brand-500/10 border border-brand-500/30 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-brand-400" />
                <span className="text-brand-400 text-sm font-medium">Coach recommends</span>
              </div>
              <p className="text-white font-semibold mb-1">{weakest.skill_name}</p>
              <p className="text-gray-400 text-sm mb-2">{weakest.category_name}</p>
              <span className="inline-flex px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-800 text-gray-300">
                {weakest.band_display || 'Unranked'}
              </span>
              <div className="mt-3">
                <Link to="/chat" className="text-brand-400 text-xs hover:opacity-80 flex items-center gap-1">
                  Work with your Writing Tutor <ArrowUpRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          )}

          {/* Top Writing skills with band display */}
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
            <p className="text-sm font-medium text-gray-400 mb-3">Writing skills</p>
            {skills.length === 0 ? (
              <p className="text-gray-600 text-sm">Submit a writing essay to see your skill profile</p>
            ) : (
              <div className="space-y-3">
                {skills.slice(0, 6).map(skill => {
                  const band = skill.band ?? null
                  const pct = band !== null ? Math.min(100, ((band - 4.0) / 5.0) * 100) : 0
                  return (
                    <div key={skill.skill_id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-gray-300 text-xs truncate flex-1">{skill.skill_name}</span>
                        <span className="text-gray-500 text-xs ml-2 flex-shrink-0">
                          {band !== null ? `B${band.toFixed(1)}` : '—'}
                        </span>
                      </div>
                      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            <Link to="/skills" className="mt-4 flex items-center gap-1 text-brand-400 text-xs hover:opacity-80">
              View all skills <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
