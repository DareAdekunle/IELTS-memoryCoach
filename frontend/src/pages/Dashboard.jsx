import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getSummary, getSkillRanks } from '../api/progress'
import {
  PenLine, BookOpen, TrendingUp, Brain,
  Target, Zap, Trophy, ChevronRight
} from 'lucide-react'

const RANK_NAMES = {
  1: 'Beginner', 2: 'Developing', 3: 'Intermediate',
  4: 'Proficient', 5: 'Advanced'
}

const RANK_COLORS = {
  1: 'text-red-400 bg-red-500/10',
  2: 'text-orange-400 bg-orange-500/10',
  3: 'text-yellow-400 bg-yellow-500/10',
  4: 'text-blue-400 bg-blue-500/10',
  5: 'text-green-400 bg-green-500/10',
}

export default function Dashboard() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getSummary(), getSkillRanks()])
      .then(([sumRes, skillRes]) => {
        setSummary(sumRes.data)
        setSkills(skillRes.data.skills || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const firstName = user?.full_name?.split(' ')[0] ||
                    user?.username || 'there'

  // Find weakest skill for the coach recommendation
  const weakest = skills.length
    ? [...skills].sort((a, b) => a.current_rank - b.current_rank)[0]
    : null

  return (
    <div className="p-6 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-1">
          Welcome back, {firstName} 👋
        </h1>
        <p className="text-gray-400">
          Your coach is ready — let's keep improving.
        </p>
      </div>

      {/* Stats row */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-900 rounded-2xl p-5 border
                                    border-gray-800 animate-pulse h-24" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            {
              label: 'Writing attempts',
              value: summary?.writing_attempts ?? 0,
              icon: PenLine,
              color: 'text-purple-400'
            },
            {
              label: 'Reading attempts',
              value: summary?.reading_attempts ?? 0,
              icon: BookOpen,
              color: 'text-blue-400'
            },
            {
              label: 'Active memories',
              value: summary?.active_memories ?? 0,
              icon: Brain,
              color: 'text-green-400'
            },
            {
              label: 'Avg skill rank',
              value: summary?.average_skill_rank
                ? `${summary.average_skill_rank}/5`
                : '—',
              icon: Trophy,
              color: 'text-yellow-400'
            },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label}
                 className="bg-gray-900 rounded-2xl p-5 border border-gray-800">
              <Icon className={`w-5 h-5 ${color} mb-3`} />
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-gray-500 text-sm mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">

        {/* Quick start */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-semibold text-white">Quick start</h2>

          {[
            {
              to: '/writing',
              icon: PenLine,
              title: 'Writing Coach',
              desc: 'Submit an essay and get personalised AI feedback',
              color: 'bg-purple-500/15 text-purple-400',
            },
            {
              to: '/reading',
              icon: BookOpen,
              title: 'Reading Coach',
              desc: 'Practice with IELTS passages and comprehension questions',
              color: 'bg-blue-500/15 text-blue-400',
            },
            {
              to: '/progress',
              icon: TrendingUp,
              title: 'Progress Dashboard',
              desc: 'See your score trends and skill improvements over time',
              color: 'bg-green-500/15 text-green-400',
            },
            {
              to: '/memory',
              icon: Brain,
              title: 'Memory Dashboard',
              desc: 'See everything your coach has learned about you',
              color: 'bg-yellow-500/15 text-yellow-400',
            },
          ].map(({ to, icon: Icon, title, desc, color }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-4 p-4 bg-gray-900 rounded-2xl
                         border border-gray-800 hover:border-gray-700
                         transition-colors group"
            >
              <div className={`w-10 h-10 rounded-xl flex items-center
                               justify-center flex-shrink-0 ${color}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium">{title}</p>
                <p className="text-gray-500 text-sm truncate">{desc}</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-600
                                       group-hover:text-gray-400 flex-shrink-0" />
            </Link>
          ))}
        </div>

        {/* Skill focus panel */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">
            Skill focus
          </h2>

          {/* Coach recommendation */}
          {weakest && (
            <div className="bg-brand-500/10 border border-brand-500/30
                            rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-brand-400" />
                <span className="text-brand-400 text-sm font-medium">
                  Coach recommends
                </span>
              </div>
              <p className="text-white font-semibold mb-1">
                {weakest.skill_name}
              </p>
              <p className="text-gray-400 text-sm mb-3">
                {weakest.category_name}
              </p>
              <span className={`inline-flex px-2.5 py-1 rounded-lg text-xs
                                font-medium ${RANK_COLORS[weakest.current_rank]}`}>
                {RANK_NAMES[weakest.current_rank]}
              </span>
            </div>
          )}

          {/* Top 5 skills */}
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
            <p className="text-sm font-medium text-gray-400 mb-3">
              Writing skills
            </p>
            {skills.length === 0 ? (
              <p className="text-gray-600 text-sm">
                Submit a writing essay to see your skill profile
              </p>
            ) : (
              <div className="space-y-3">
                {skills.slice(0, 6).map(skill => (
                  <div key={skill.skill_id}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-gray-300 text-xs truncate flex-1">
                        {skill.skill_name}
                      </span>
                      <span className="text-gray-500 text-xs ml-2 flex-shrink-0">
                        {skill.current_rank}/5
                      </span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-brand-500 rounded-full transition-all"
                        style={{ width: `${(skill.current_rank / 5) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
