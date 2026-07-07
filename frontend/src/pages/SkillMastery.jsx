import { useState, useEffect } from 'react'
import { getSkillRanks } from '../api/progress'
import { Trophy, Loader2, Zap, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const RANK_NAMES = {
  1: 'Beginner',
  2: 'Developing',
  3: 'Intermediate',
  4: 'Proficient',
  5: 'Advanced'
}

const RANK_COLORS = {
  1: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', bar: 'bg-red-500' },
  2: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', bar: 'bg-orange-500' },
  3: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', bar: 'bg-yellow-500' },
  4: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', bar: 'bg-blue-500' },
  5: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', bar: 'bg-green-500' }
}

const CATEGORY_ICONS = {
  'Task Response': '🎯',
  'Coherence & Cohesion': '🔗',
  'Lexical Resource': '📚',
  'Grammatical Range & Accuracy': '✏️'
}

function RankBadge({ rank }) {
  const colors = RANK_COLORS[rank] || RANK_COLORS[1]
  return (
    <span className={
      'text-xs font-semibold px-2.5 py-1 rounded-lg ' +
      colors.bg + ' ' + colors.text
    }>
      {RANK_NAMES[rank]}
    </span>
  )
}

function StreakDots({ streak, threshold = 3 }) {
  return (
    <div className="flex items-center gap-1">
      {[...Array(threshold)].map((_, i) => (
        <div
          key={i}
          className={
            'w-2.5 h-2.5 rounded-full ' +
            (i < streak ? 'bg-brand-500' : 'bg-gray-700')
          }
        />
      ))}
    </div>
  )
}

function SkillCard({ skill, isWeakest }) {
  const rank = skill.current_rank || 1
  const colors = RANK_COLORS[rank] || RANK_COLORS[1]
  const pct = (rank / 5) * 100
  const hasEvidence = skill.total_evidence > 0
  const streak = skill.clean_streak || 0
  const toRankUp = Math.max(0, 3 - streak)

  return (
    <div className={
      'rounded-2xl p-5 border transition-all ' +
      (isWeakest
        ? 'border-brand-500/50 bg-brand-500/5'
        : 'border-gray-800 bg-gray-900 hover:border-gray-700')
    }>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-white font-medium text-sm truncate">
              {skill.skill_name}
            </p>
            {isWeakest && (
              <span className="flex items-center gap-1 text-xs text-brand-400 bg-brand-500/15 px-2 py-0.5 rounded-full flex-shrink-0">
                <Zap className="w-3 h-3" />
                Focus
              </span>
            )}
          </div>
          <p className="text-gray-500 text-xs">{skill.category_name}</p>
        </div>
        <RankBadge rank={rank} />
      </div>

      {/* Rank progress bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-gray-600 text-xs">Rank {rank}/5</span>
          {rank < 5 && (
            <span className="text-gray-600 text-xs">→ {RANK_NAMES[rank + 1]}</span>
          )}
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={'h-full rounded-full transition-all ' + colors.bar}
            style={{ width: pct + '%' }}
          />
        </div>
      </div>

      {/* Evidence and streak */}
      {hasEvidence ? (
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-500 text-xs mb-1">
              {rank < 5
                ? `${toRankUp} more to rank up`
                : 'Maximum rank achieved!'}
            </p>
            {rank < 5 && <StreakDots streak={streak} threshold={3} />}
          </div>
          <span className="text-gray-600 text-xs">
            {skill.total_evidence} assessment{skill.total_evidence !== 1 ? 's' : ''}
          </span>
        </div>
      ) : (
        <p className="text-gray-600 text-xs">Not yet assessed</p>
      )}
    </div>
  )
}

export default function SkillMastery() {
  const [skills, setSkills] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState('All')

  useEffect(() => {
    getSkillRanks()
      .then(res => {
        setSkills(res.data.skills || [])
        setSummary(res.data.summary || null)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    )
  }

  // Get unique categories
  const categories = ['All', ...new Set(skills.map(s => s.category_name))]

  const filteredSkills = categoryFilter === 'All'
    ? skills
    : skills.filter(s => s.category_name === categoryFilter)

  // Find weakest skill
  const weakest = skills.length
    ? [...skills].sort((a, b) => {
        if (a.current_rank !== b.current_rank) return a.current_rank - b.current_rank
        return a.total_evidence - b.total_evidence
      })[0]
    : null

  // Group skills by category for the category view
  const byCategory = categories.slice(1).map(cat => ({
    name: cat,
    icon: CATEGORY_ICONS[cat] || '📋',
    skills: skills.filter(s => s.category_name === cat),
    avgRank: skills.filter(s => s.category_name === cat).length
      ? (skills.filter(s => s.category_name === cat)
          .reduce((sum, s) => sum + (s.current_rank || 1), 0) /
         skills.filter(s => s.category_name === cat).length).toFixed(1)
      : 0
  }))

  const hasAnyData = skills.some(s => s.total_evidence > 0)

  return (
    <div className="p-6 max-w-6xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Trophy className="w-6 h-6 text-yellow-400" />
            Skill Mastery
          </h1>
          <p className="text-gray-400 mt-1">
            Your mastery level on all 13 IELTS Writing sub-skills
          </p>
        </div>
        <Link
          to="/writing"
          className="flex items-center gap-2 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-xl transition-colors"
        >
          Practice Writing
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {/* No data state */}
      {!hasAnyData && (
        <div className="bg-brand-500/10 border border-brand-500/30 rounded-2xl p-6 mb-6">
          <div className="flex items-start gap-4">
            <Zap className="w-6 h-6 text-brand-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-white font-medium mb-1">
                Submit essays to unlock your skill profile
              </p>
              <p className="text-gray-400 text-sm">
                After each Writing Coach submission, the AI classifies your
                essay against these 13 skills. You need 3 consecutive strong
                performances on a skill to rank up.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Summary stats */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total skills', value: summary.total_skills || 13 },
            {
              label: 'Average rank',
              value: summary.average_rank
                ? Number(summary.average_rank).toFixed(1) + '/5'
                : '1.0/5'
            },
            { label: 'Advanced skills', value: summary.skills_at_max || 0 },
            {
              label: 'Not yet assessed',
              value: summary.skills_untouched ?? 13
            }
          ].map(({ label, value }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
              <p className="text-xl font-bold text-white">{value}</p>
              <p className="text-gray-500 text-sm mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Coach recommendation */}
      {weakest && weakest.total_evidence > 0 && (
        <div className="bg-brand-500/10 border border-brand-500/30 rounded-2xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-brand-400" />
            <span className="text-brand-400 text-sm font-medium">
              Coach recommendation
            </span>
          </div>
          <p className="text-white font-semibold mb-1">{weakest.skill_name}</p>
          <p className="text-gray-400 text-sm mb-3">
            {weakest.category_name} · Currently {RANK_NAMES[weakest.current_rank || 1]}
            {(weakest.clean_streak || 0) > 0 && (
              <span className="text-brand-400 ml-2">
                · {3 - (weakest.clean_streak || 0)} more strong essays to rank up
              </span>
            )}
          </p>
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 text-sm text-brand-400 hover:text-brand-300 transition-colors"
          >
            Work on this with your Chat Coach →
          </Link>
        </div>
      )}

      {/* Category overview */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {byCategory.map(({ name, icon, skills: catSkills, avgRank }) => (
          <button
            key={name}
            onClick={() => setCategoryFilter(
              categoryFilter === name ? 'All' : name
            )}
            className={
              'text-left rounded-xl p-3 border transition-colors ' +
              (categoryFilter === name
                ? 'border-brand-500/50 bg-brand-500/10'
                : 'border-gray-800 bg-gray-900 hover:border-gray-700')
            }
          >
            <p className="text-lg mb-1">{icon}</p>
            <p className="text-white text-xs font-medium leading-tight mb-1">
              {name}
            </p>
            <p className="text-gray-500 text-xs">
              Avg rank: {avgRank}/5
            </p>
            <p className="text-gray-600 text-xs">
              {catSkills.length} skills
            </p>
          </button>
        ))}
      </div>

      {/* Category filter pills */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ' +
              (categoryFilter === cat
                ? 'bg-brand-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white')
            }
          >
            {cat === 'All' ? 'All Skills' : cat}
            {cat !== 'All' && (
              <span className="ml-1 text-gray-500">
                ({skills.filter(s => s.category_name === cat).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* How it works explainer */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 mb-6">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">
          How the rank engine works
        </h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl mb-1">✍️</p>
            <p className="text-white text-xs font-medium">Submit an essay</p>
            <p className="text-gray-500 text-xs mt-1">
              AI classifies each skill as strength, weakness, or not applicable
            </p>
          </div>
          <div>
            <p className="text-2xl mb-1">🔥</p>
            <p className="text-white text-xs font-medium">Build a streak</p>
            <p className="text-gray-500 text-xs mt-1">
              3 consecutive strengths = rank up. Any weakness resets streak to 0
            </p>
          </div>
          <div>
            <p className="text-2xl mb-1">🏆</p>
            <p className="text-white text-xs font-medium">Reach Advanced</p>
            <p className="text-gray-500 text-xs mt-1">
              Rank 5 is the ceiling. Ranks never decrease — only forward
            </p>
          </div>
        </div>
      </div>

      {/* Skills grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredSkills.map(skill => (
          <SkillCard
            key={skill.skill_id}
            skill={skill}
            isWeakest={weakest && skill.skill_id === weakest.skill_id}
          />
        ))}
      </div>

      {/* Rank legend */}
      <div className="mt-6 bg-gray-900 border border-gray-800 rounded-2xl p-4">
        <p className="text-gray-500 text-xs mb-3 font-medium">Rank levels</p>
        <div className="flex flex-wrap gap-3">
          {Object.entries(RANK_NAMES).map(([rank, name]) => {
            const colors = RANK_COLORS[Number(rank)]
            return (
              <div key={rank} className="flex items-center gap-2">
                <div className={'w-3 h-3 rounded-full ' + colors.bar} />
                <span className="text-gray-400 text-xs">
                  {rank} — {name}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
