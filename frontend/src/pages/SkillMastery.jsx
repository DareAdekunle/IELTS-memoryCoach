import { useState, useEffect } from 'react'
import { getSkillRanks } from '../api/progress'
import { Trophy, Loader2, Zap, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const RANK_NAMES = {
  1: 'Beginner', 2: 'Developing', 3: 'Intermediate',
  4: 'Proficient', 5: 'Advanced'
}

const RANK_COLORS = {
  1: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', bar: 'bg-red-500' },
  2: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', bar: 'bg-orange-500' },
  3: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', bar: 'bg-yellow-500' },
  4: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', bar: 'bg-blue-500' },
  5: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', bar: 'bg-green-500' }
}

const SECTION_CONFIG = {
  Writing:   { color: 'text-purple-400', bg: 'bg-purple-500/15', border: 'border-purple-500/30', practiceLink: '/writing' },
  Reading:   { color: 'text-blue-400',   bg: 'bg-blue-500/15',   border: 'border-blue-500/30',   practiceLink: '/reading' },
  Speaking:  { color: 'text-green-400',  bg: 'bg-green-500/15',  border: 'border-green-500/30',  practiceLink: '/speaking' },
  Listening: { color: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/30', practiceLink: '/listening' },
}

const SECTIONS = ['Writing', 'Reading', 'Speaking', 'Listening']

function RankBadge({ rank }) {
  const colors = RANK_COLORS[rank] || RANK_COLORS[1]
  return (
    <span className={'text-xs font-semibold px-2.5 py-1 rounded-lg ' + colors.bg + ' ' + colors.text}>
      {RANK_NAMES[rank]}
    </span>
  )
}

function StreakDots({ streak, threshold = 3 }) {
  return (
    <div className="flex items-center gap-1">
      {[...Array(threshold)].map((_, i) => (
        <div key={i} className={'w-2.5 h-2.5 rounded-full ' + (i < streak ? 'bg-brand-500' : 'bg-gray-700')} />
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
    <div className={'rounded-2xl p-4 border transition-all ' + (isWeakest ? 'border-brand-500/50 bg-brand-500/5' : 'border-gray-800 bg-gray-900 hover:border-gray-700')}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-white font-medium text-sm truncate">{skill.skill_name}</p>
            {isWeakest && (
              <span className="flex items-center gap-1 text-xs text-brand-400 bg-brand-500/15 px-2 py-0.5 rounded-full flex-shrink-0">
                <Zap className="w-3 h-3" />Focus
              </span>
            )}
          </div>
          <p className="text-gray-500 text-xs">{skill.category_name}</p>
        </div>
        <RankBadge rank={rank} />
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-gray-600 text-xs">Rank {rank}/5</span>
          {rank < 5 && <span className="text-gray-600 text-xs">→ {RANK_NAMES[rank + 1]}</span>}
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div className={'h-full rounded-full transition-all ' + colors.bar} style={{ width: pct + '%' }} />
        </div>
      </div>

      {hasEvidence ? (
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-500 text-xs mb-1">
              {rank < 5 ? `${toRankUp} more to rank up` : 'Maximum rank!'}
            </p>
            {rank < 5 && <StreakDots streak={streak} threshold={3} />}
          </div>
          <span className="text-gray-600 text-xs">{skill.total_evidence} assessments</span>
        </div>
      ) : (
        <p className="text-gray-600 text-xs">Not yet assessed</p>
      )}
    </div>
  )
}

export default function SkillMastery() {
  const [skillsBySection, setSkillsBySection] = useState({})
  const [summariesBySection, setSummariesBySection] = useState({})
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState('Writing')

  useEffect(() => {
    Promise.all(
      SECTIONS.map(section =>
        getSkillRanks(section).then(res => ({
          section,
          skills: res.data.skills || [],
          summary: res.data.summary || {}
        }))
      )
    ).then(results => {
      const bySection = {}
      const summaries = {}
      results.forEach(({ section, skills, summary }) => {
        bySection[section] = skills
        summaries[section] = summary
      })
      setSkillsBySection(bySection)
      setSummariesBySection(summaries)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    )
  }

  const currentSkills = skillsBySection[activeSection] || []
  const currentSummary = summariesBySection[activeSection] || {}
  const sectionConfig = SECTION_CONFIG[activeSection]

  const weakest = currentSkills.length
    ? [...currentSkills].sort((a, b) => {
        if (a.current_rank !== b.current_rank) return a.current_rank - b.current_rank
        return a.total_evidence - b.total_evidence
      })[0]
    : null

  const hasAnyData = currentSkills.some(s => s.total_evidence > 0)

  // Overall stats across all sections
  const totalSkills = Object.values(skillsBySection).reduce((sum, skills) => sum + skills.length, 0)
  const totalAdvanced = Object.values(skillsBySection).reduce(
    (sum, skills) => sum + skills.filter(s => s.current_rank === 5).length, 0
  )
  const totalAssessed = Object.values(skillsBySection).reduce(
    (sum, skills) => sum + skills.filter(s => s.total_evidence > 0).length, 0
  )
  const allRanks = Object.values(skillsBySection).flatMap(skills => skills.map(s => s.current_rank || 1))
  const overallAvg = allRanks.length
    ? (allRanks.reduce((a, b) => a + b, 0) / allRanks.length).toFixed(1)
    : '—'

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
            Your mastery level across all IELTS skills
          </p>
        </div>
        <Link
          to={sectionConfig.practiceLink}
          className={'flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-xl transition-colors ' + sectionConfig.bg + ' ' + sectionConfig.color}
        >
          Practice {activeSection}
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Overall stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total skills', value: totalSkills },
          { label: 'Overall avg rank', value: overallAvg + '/5' },
          { label: 'Advanced skills', value: totalAdvanced },
          { label: 'Skills assessed', value: totalAssessed + '/' + totalSkills },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
            <p className="text-xl font-bold text-white">{value}</p>
            <p className="text-gray-500 text-sm mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Section tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {SECTIONS.map(section => {
          const cfg = SECTION_CONFIG[section]
          const sectionSkills = skillsBySection[section] || []
          const assessed = sectionSkills.filter(s => s.total_evidence > 0).length
          const isActive = activeSection === section
          return (
            <button
              key={section}
              onClick={() => setActiveSection(section)}
              className={
                'px-4 py-2 rounded-xl text-sm font-medium transition-colors ' +
                (isActive ? cfg.bg + ' ' + cfg.color + ' ' + cfg.border + ' border' : 'bg-gray-800 text-gray-400 hover:text-white')
              }
            >
              {section}
              <span className="ml-1.5 text-xs opacity-60">
                {assessed}/{sectionSkills.length}
              </span>
            </button>
          )
        })}
      </div>

      {/* No data state */}
      {!hasAnyData && (
        <div className={'rounded-2xl p-6 mb-6 border ' + sectionConfig.bg + ' ' + sectionConfig.border}>
          <div className="flex items-start gap-4">
            <Zap className={'w-6 h-6 flex-shrink-0 mt-0.5 ' + sectionConfig.color} />
            <div>
              <p className="text-white font-medium mb-1">
                Submit {activeSection} practice to unlock your skill profile
              </p>
              <p className="text-gray-400 text-sm">
                After each {activeSection} Coach session, the AI classifies your
                performance against {currentSkills.length} skills. You need 3
                consecutive strong performances on a skill to rank up.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Section summary + coach recommendation */}
      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        {/* Section stats */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
          <p className="text-sm font-medium text-gray-400 mb-3">{activeSection} overview</p>
          <div className="space-y-2">
            {[
              { label: 'Skills', value: currentSkills.length },
              { label: 'Avg rank', value: currentSummary.average_rank ? Number(currentSummary.average_rank).toFixed(1) + '/5' : '—' },
              { label: 'Advanced', value: currentSummary.skills_at_max || 0 },
              { label: 'Not assessed', value: currentSummary.skills_untouched ?? currentSkills.length },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between">
                <span className="text-gray-500 text-sm">{label}</span>
                <span className="text-white text-sm font-medium">{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Coach recommendation */}
        {weakest && weakest.total_evidence > 0 && (
          <div className={'lg:col-span-2 rounded-2xl p-4 border ' + sectionConfig.bg + ' ' + sectionConfig.border}>
            <div className="flex items-center gap-2 mb-2">
              <Zap className={'w-4 h-4 ' + sectionConfig.color} />
              <span className={'text-sm font-medium ' + sectionConfig.color}>Coach recommendation</span>
            </div>
            <p className="text-white font-semibold mb-1">{weakest.skill_name}</p>
            <p className="text-gray-400 text-sm mb-3">
              {weakest.category_name} · Currently {RANK_NAMES[weakest.current_rank || 1]}
              {(weakest.clean_streak || 0) > 0 && (
                <span className="text-brand-400 ml-2">
                  · {3 - (weakest.clean_streak || 0)} more to rank up
                </span>
              )}
            </p>
            <Link
              to="/chat"
              className={'text-sm inline-flex items-center gap-1 hover:opacity-80 transition-opacity ' + sectionConfig.color}
            >
              Work on this with your {activeSection} Tutor →
            </Link>
          </div>
        )}
      </div>

      {/* How it works */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 mb-6">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">How the rank engine works</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl mb-1">✍️</p>
            <p className="text-white text-xs font-medium">Complete a session</p>
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
        {currentSkills.map(skill => (
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
                <span className="text-gray-400 text-xs">{rank} — {name}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
