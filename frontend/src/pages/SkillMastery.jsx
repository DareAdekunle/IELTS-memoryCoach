import { useState, useEffect } from 'react'
import { getSkillRanks } from '../api/progress'
import { Trophy, Loader2, Zap, ChevronRight, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'

// Band → colour mapping (replaces rank-based colours)
// Anchored to IELTS band ranges learners actually recognise
const BAND_COLORS = {
  4.0: { bg: 'bg-red-500/10',    border: 'border-red-500/30',    text: 'text-red-400',    bar: 'bg-red-500' },
  4.5: { bg: 'bg-red-500/10',    border: 'border-red-500/30',    text: 'text-red-400',    bar: 'bg-red-500' },
  5.0: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', bar: 'bg-orange-500' },
  5.5: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', bar: 'bg-orange-500' },
  6.0: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', bar: 'bg-yellow-500' },
  6.5: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', bar: 'bg-yellow-500' },
  7.0: { bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   text: 'text-blue-400',   bar: 'bg-blue-500' },
  7.5: { bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   text: 'text-blue-400',   bar: 'bg-blue-500' },
  8.0: { bg: 'bg-green-500/10',  border: 'border-green-500/30',  text: 'text-green-400',  bar: 'bg-green-500' },
  8.5: { bg: 'bg-green-500/10',  border: 'border-green-500/30',  text: 'text-green-400',  bar: 'bg-green-500' },
}

function getBandColors(band) {
  if (band === null || band === undefined) {
    return { bg: 'bg-gray-100', border: 'border-gray-200', text: 'text-gray-500', bar: 'bg-gray-200' }
  }
  return BAND_COLORS[band] || BAND_COLORS[4.0]
}

// Progress bar fills from 4.0 (min shown) to 9.0 (IELTS max)
function bandToPercent(band) {
  if (band === null || band === undefined) return 0
  return Math.min(100, Math.max(0, ((band - 4.0) / 5.0) * 100))
}

const SECTION_CONFIG = {
  Writing:   { color: 'text-purple-400', bg: 'bg-purple-500/15', border: 'border-purple-500/30', practiceLink: '/writing' },
  Reading:   { color: 'text-blue-400',   bg: 'bg-blue-500/15',   border: 'border-blue-500/30',   practiceLink: '/reading' },
  Speaking:  { color: 'text-green-400',  bg: 'bg-green-500/15',  border: 'border-green-500/30',  practiceLink: '/speaking' },
  Listening: { color: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/30', practiceLink: '/listening' },
}

const SECTIONS = ['Writing', 'Reading', 'Speaking', 'Listening']

function BandBadge({ band, bandLabel }) {
  const colors = getBandColors(band)
  return (
    <span className={
      'text-xs font-semibold px-2.5 py-1 rounded-lg whitespace-nowrap ' +
      colors.bg + ' ' + colors.text
    }>
      {band !== null && band !== undefined ? `Band ${band.toFixed(1)}` : 'No band yet'}
    </span>
  )
}

function StreakDots({ streak, threshold = 3 }) {
  return (
    <div className="flex items-center gap-1">
      {[...Array(threshold)].map((_, i) => (
        <div
          key={i}
          className={'w-2.5 h-2.5 rounded-full ' + (i < streak ? 'bg-brand-500' : 'bg-gray-200')}
        />
      ))}
    </div>
  )
}

function SkillCard({ skill, isWeakest }) {
  const band = skill.band ?? null
  const bandLabel = skill.band_label || ''
  const colors = getBandColors(band)
  const pct = bandToPercent(band)
  const hasEvidence = skill.total_evidence > 0
  const streak = skill.clean_streak || 0
  const toNextBand = Math.max(0, 3 - streak)

  // Next band display
  const nextBand = band !== null ? Math.min(8.5, band + (streak >= 1 ? 0.5 : 0.5)) : null
  const nextBandDisplay = nextBand !== null ? `Band ${nextBand.toFixed(1)}` : null

  return (
    <div className={
      'rounded-2xl p-4 border transition-all ' +
      (isWeakest
        ? 'border-brand-500/50 bg-brand-500/5'
        : 'border-gray-200 bg-white hover:border-gray-200')
    }>
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-gray-900 font-medium text-sm truncate">{skill.skill_name}</p>
            {isWeakest && (
              <span className="flex items-center gap-1 text-xs text-brand-600 bg-brand-500/15 px-2 py-0.5 rounded-full flex-shrink-0">
                <Zap className="w-3 h-3" />Focus
              </span>
            )}
          </div>
          <p className="text-gray-500 text-xs">{skill.category_name}</p>
        </div>
        <BandBadge band={band} bandLabel={bandLabel} />
      </div>

      {/* Band progress bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-gray-600 text-xs">
            {hasEvidence ? (bandLabel || 'Assessed') : 'Not assessed'}
          </span>
          {hasEvidence && band !== null && band < 8.5 && nextBandDisplay && (
            <span className="text-gray-600 text-xs">→ {nextBandDisplay}</span>
          )}
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={'h-full rounded-full transition-all ' + colors.bar}
            style={{ width: pct + '%' }}
          />
        </div>
        {/* Band scale labels */}
        <div className="flex justify-between mt-1">
          <span className="text-gray-700 text-xs">4.0</span>
          <span className="text-gray-700 text-xs">6.5</span>
          <span className="text-gray-700 text-xs">9.0</span>
        </div>
      </div>

      {/* Footer */}
      {hasEvidence ? (
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-500 text-xs mb-1">
              {band !== null && band < 8.5
                ? `${toNextBand} more to Band ${(band + 0.5).toFixed(1)}`
                : band !== null
                ? 'Peak band reached!'
                : ''}
            </p>
            {band !== null && band < 8.5 && (
              <StreakDots streak={streak} threshold={3} />
            )}
          </div>
          <span className="text-gray-600 text-xs">{skill.total_evidence} assessments</span>
        </div>
      ) : (
        <p className="text-gray-600 text-xs">Submit a practice session to get your band</p>
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

  // Weakest = lowest band among assessed skills, then least evidence
  const assessedSkills = currentSkills.filter(s => s.total_evidence > 0)
  const weakest = assessedSkills.length
    ? [...assessedSkills].sort((a, b) => {
        const bandA = a.band ?? 0
        const bandB = b.band ?? 0
        if (bandA !== bandB) return bandA - bandB
        return a.total_evidence - b.total_evidence
      })[0]
    : null

  const hasAnyData = assessedSkills.length > 0

  // Overall stats across all sections
  const totalSkills = Object.values(skillsBySection).reduce((sum, skills) => sum + skills.length, 0)
  const totalAssessed = Object.values(skillsBySection).reduce(
    (sum, skills) => sum + skills.filter(s => s.total_evidence > 0).length, 0
  )

  // Overall band across all assessed skills
  const allBands = Object.values(skillsBySection)
    .flatMap(skills => skills.map(s => s.band))
    .filter(b => b !== null && b !== undefined)

  const overallBand = allBands.length
    ? Math.round((allBands.reduce((a, b) => a + b, 0) / allBands.length) * 2) / 2
    : null

  const overallBandDisplay = overallBand !== null ? `Band ${overallBand.toFixed(1)}` : '—'

  const totalAdvanced = Object.values(skillsBySection).reduce(
    (sum, skills) => sum + skills.filter(s => s.band !== null && s.band >= 8.0).length, 0
  )

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Trophy className="w-6 h-6 text-yellow-400" />
            Skill Mastery
          </h1>
          <p className="text-gray-500 mt-1">
            Your IELTS band estimates across all skills
          </p>
        </div>
        <Link
          to={sectionConfig.practiceLink}
          className={
            'flex items-center gap-2 px-4 py-2 text-gray-900 text-sm font-medium rounded-xl transition-colors ' +
            sectionConfig.bg + ' ' + sectionConfig.color
          }
        >
          Practice {activeSection}
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Overall stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Overall band', value: overallBandDisplay },
          { label: 'Skills assessed', value: `${totalAssessed}/${totalSkills}` },
          { label: 'Band 8.0+ skills', value: totalAdvanced },
          { label: 'Active section', value: activeSection },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-2xl p-4">
            <p className="text-xl font-bold text-gray-900">{value}</p>
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
          // Section band
          const sectionBands = sectionSkills.map(s => s.band).filter(b => b !== null && b !== undefined)
          const sectionBand = sectionBands.length
            ? (Math.round((sectionBands.reduce((a, b) => a + b, 0) / sectionBands.length) * 2) / 2).toFixed(1)
            : null
          return (
            <button
              key={section}
              onClick={() => setActiveSection(section)}
              className={
                'px-4 py-2 rounded-xl text-sm font-medium transition-colors ' +
                (isActive
                  ? cfg.bg + ' ' + cfg.color + ' ' + cfg.border + ' border'
                  : 'bg-gray-100 text-gray-500 hover:text-gray-900')
              }
            >
              {section}
              <span className="ml-1.5 text-xs opacity-60">
                {sectionBand ? `B${sectionBand}` : `${assessed}/${sectionSkills.length}`}
              </span>
            </button>
          )
        })}
      </div>

      {/* No data nudge */}
      {!hasAnyData && (
        <div className={'rounded-2xl p-6 mb-6 border ' + sectionConfig.bg + ' ' + sectionConfig.border}>
          <div className="flex items-start gap-4">
            <TrendingUp className={'w-6 h-6 flex-shrink-0 mt-0.5 ' + sectionConfig.color} />
            <div>
              <p className="text-gray-900 font-medium mb-1">
                Submit a {activeSection} practice session to unlock your band estimates
              </p>
              <p className="text-gray-500 text-sm">
                After each session, the Coach classifies your performance across{' '}
                {currentSkills.length} {activeSection} skills and assigns an estimated
                IELTS band (4.0–8.5) per skill. Three consecutive strong performances
                lift a skill's band by 0.5.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Section summary + coach recommendation */}
      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        {/* Section stats */}
        <div className="bg-white border border-gray-200 rounded-2xl p-4">
          <p className="text-sm font-medium text-gray-500 mb-3">{activeSection} overview</p>
          <div className="space-y-2">
            {[
              {
                label: 'Section band',
                value: currentSummary.section_band_display || 'No band yet'
              },
              {
                label: 'Band label',
                value: currentSummary.section_band_label || '—'
              },
              {
                label: 'Skills assessed',
                value: `${assessedSkills.length}/${currentSkills.length}`
              },
              {
                label: 'Band 8.0+',
                value: currentSkills.filter(s => s.band !== null && s.band >= 8.0).length
              },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between">
                <span className="text-gray-500 text-sm">{label}</span>
                <span className="text-gray-900 text-sm font-medium">{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Coach recommendation */}
        {weakest && (
          <div className={'lg:col-span-2 rounded-2xl p-4 border ' + sectionConfig.bg + ' ' + sectionConfig.border}>
            <div className="flex items-center gap-2 mb-2">
              <Zap className={'w-4 h-4 ' + sectionConfig.color} />
              <span className={'text-sm font-medium ' + sectionConfig.color}>Coach recommendation</span>
            </div>
            <p className="text-gray-900 font-semibold mb-1">{weakest.skill_name}</p>
            <p className="text-gray-500 text-sm mb-3">
              {weakest.category_name}
              {weakest.band !== null && (
                <span className="ml-2">· Currently {weakest.band_display}</span>
              )}
              {(weakest.clean_streak || 0) > 0 && (
                <span className="text-brand-600 ml-2">
                  · {3 - (weakest.clean_streak || 0)} more to {weakest.band !== null ? `Band ${(weakest.band + 0.5).toFixed(1)}` : 'next band'}
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

      {/* How bands work */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-6">
        <h3 className="text-sm font-semibold text-gray-600 mb-3">How band estimates work</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl mb-1">✍️</p>
            <p className="text-gray-900 text-xs font-medium">Complete a session</p>
            <p className="text-gray-500 text-xs mt-1">
              The Coach classifies each skill as strength, weakness, or not applicable
            </p>
          </div>
          <div>
            <p className="text-2xl mb-1">🔥</p>
            <p className="text-gray-900 text-xs font-medium">Build a streak</p>
            <p className="text-gray-500 text-xs mt-1">
              3 consecutive strengths lifts your band by 0.5. Any weakness resets streak to 0
            </p>
          </div>
          <div>
            <p className="text-2xl mb-1">🏆</p>
            <p className="text-gray-900 text-xs font-medium">Reach Band 8.5</p>
            <p className="text-gray-500 text-xs mt-1">
              Bands range 4.0–8.5 per skill. Your overall band is the average across all assessed skills
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

      {/* Band legend */}
      <div className="mt-6 bg-white border border-gray-200 rounded-2xl p-4">
        <p className="text-gray-500 text-xs mb-3 font-medium">Band scale</p>
        <div className="flex flex-wrap gap-3">
          {[
            { band: 4.0, label: 'Emerging' },
            { band: 5.0, label: 'Developing' },
            { band: 6.0, label: 'Competent' },
            { band: 7.0, label: 'Proficient' },
            { band: 8.0, label: 'Advanced' },
          ].map(({ band, label }) => {
            const colors = getBandColors(band)
            return (
              <div key={band} className="flex items-center gap-2">
                <div className={'w-3 h-3 rounded-full ' + colors.bar} />
                <span className="text-gray-500 text-xs">
                  {band.toFixed(1)}–{(band + 0.5).toFixed(1)} — {label}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
