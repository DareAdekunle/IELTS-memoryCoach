import { useState, useEffect } from 'react'
import { getAllMemories, getMemoryTimeline } from '../api/memory'
import { Brain, Loader2, Archive, TrendingUp, TrendingDown, Minus } from 'lucide-react'

const TYPE_COLORS = {
  weakness: 'border-yellow-500/30 bg-yellow-500/5',
  strength: 'border-green-500/30 bg-green-500/5',
  preference: 'border-blue-500/30 bg-blue-500/5'
}

const TYPE_ICONS = {
  weakness: '⚠️',
  strength: '✅',
  preference: '💡'
}

const SECTION_COLORS = {
  Writing: 'bg-purple-500/20 text-purple-400',
  Reading: 'bg-blue-500/20 text-blue-400',
  Speaking: 'bg-green-500/20 text-green-400',
  Listening: 'bg-yellow-500/20 text-yellow-400'
}

function ConfidenceBar({ value, max = 1 }) {
  const pct = Math.round((value / max) * 100)
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: pct + '%' }} />
      </div>
      <span className="text-gray-500 text-xs w-8 text-right">{pct}%</span>
    </div>
  )
}

function TimelineCard({ memory }) {
  const isArchived = memory.status === 'archived'
  const conf = memory.confidence

  const statusIcon = isArchived
    ? '🏆'
    : memory.memory_type === 'weakness'
    ? conf >= 0.7 ? '⚠️' : '📉'
    : conf >= 0.7 ? '✅' : '📈'

  return (
    <div className={
      'relative pl-8 pb-6 ' +
      (isArchived ? 'opacity-60' : '')
    }>
      {/* Timeline line */}
      <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-100" />

      {/* Timeline dot */}
      <div className={
        'absolute left-0 top-1 w-6 h-6 rounded-full flex items-center ' +
        'justify-center text-xs border-2 ' +
        (isArchived
          ? 'bg-gray-100 border-gray-300'
          : memory.memory_type === 'weakness'
          ? 'bg-yellow-500/20 border-yellow-500/50'
          : 'bg-green-500/20 border-green-500/50')
      }>
        {statusIcon}
      </div>

      {/* Card */}
      <div className={
        'rounded-xl p-4 border ' +
        (isArchived
          ? 'border-gray-200 bg-white/50'
          : TYPE_COLORS[memory.memory_type] || 'border-gray-200 bg-white')
      }>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-gray-900 text-sm font-medium">{memory.skill}</span>
            <span className={
              'text-xs px-2 py-0.5 rounded-full ' +
              (SECTION_COLORS[memory.section] || 'bg-gray-200 text-gray-500')
            }>
              {memory.section}
            </span>
            {isArchived && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-200 text-gray-500">
                Mastered
              </span>
            )}
          </div>
          <span className="text-gray-500 text-xs flex-shrink-0">
            {memory.evidence_count} evidence
          </span>
        </div>

        <p className="text-gray-600 text-sm leading-relaxed mb-3">
          {memory.memory_text}
        </p>

        <ConfidenceBar value={memory.confidence} />
      </div>
    </div>
  )
}

export default function MemoryDashboard() {
  const [memories, setMemories] = useState({ active: [], archived: [] })
  const [timeline, setTimeline] = useState([])
  const [stats, setStats] = useState(null)
  const [tab, setTab] = useState('timeline')
  const [sectionFilter, setSectionFilter] = useState('All')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getAllMemories(), getMemoryTimeline()])
      .then(([memRes, tlRes]) => {
        setMemories({
          active: memRes.data.active || [],
          archived: memRes.data.archived || []
        })
        setStats(memRes.data.stats || null)
        setTimeline(tlRes.data.timeline || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const sections = ['All', 'Writing', 'Reading', 'Speaking', 'Listening']

  const filteredTimeline = sectionFilter === 'All'
    ? timeline
    : timeline.filter(m => m.section === sectionFilter)

  // Group timeline by section for the overview
  const sectionCounts = sections.slice(1).map(s => ({
    section: s,
    active: memories.active.filter(m => m.section === s).length,
    archived: memories.archived.filter(m => m.section === s).length,
    weaknesses: memories.active.filter(
      m => m.section === s && m.memory_type === 'weakness'
    ).length,
    strengths: memories.active.filter(
      m => m.section === s && m.memory_type === 'strength'
    ).length
  })).filter(s => s.active + s.archived > 0)

  const renderMemory = (mem) => (
    <div
      key={mem.memory_id}
      className={
        'rounded-xl p-4 border ' +
        (TYPE_COLORS[mem.memory_type] || 'border-gray-200 bg-white')
      }
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span>{TYPE_ICONS[mem.memory_type] || '📝'}</span>
          <span className="text-gray-900 text-sm font-medium">{mem.skill}</span>
          <span className={
            'text-xs px-2 py-0.5 rounded-full ' +
            (SECTION_COLORS[mem.section] || 'bg-gray-200 text-gray-500')
          }>
            {mem.section}
          </span>
        </div>
        <div className="flex-shrink-0 text-right">
          <div className="flex items-center gap-1 justify-end">
            <div className="h-1.5 w-16 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full"
                style={{ width: Math.round((mem.confidence || 0) * 100) + '%' }}
              />
            </div>
            <span className="text-gray-500 text-xs">
              {Math.round((mem.confidence || 0) * 100)}%
            </span>
          </div>
          <p className="text-gray-600 text-xs mt-0.5">{mem.evidence_count} evidence</p>
        </div>
      </div>
      <p className="text-gray-600 text-sm leading-relaxed">{mem.memory_text}</p>
    </div>
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Brain className="w-6 h-6 text-green-400" />
          Memory Dashboard
        </h1>
        <p className="text-gray-500 mt-1">
          Everything your coach has learned about you — and how it evolved
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total memories', value: stats.total_memories ?? 0 },
            { label: 'Active', value: stats.active_count ?? 0 },
            { label: 'Mastered', value: stats.archived_count ?? 0 },
            {
              label: 'Avg confidence',
              value: stats.avg_confidence
                ? Math.round(stats.avg_confidence * 100) + '%'
                : '—'
            }
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border border-gray-200 rounded-2xl p-4">
              <p className="text-xl font-bold text-gray-900">{value}</p>
              <p className="text-gray-500 text-sm mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Section overview */}
      {sectionCounts.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {sectionCounts.map(({ section, active, archived, weaknesses, strengths }) => (
            <button
              key={section}
              onClick={() => { setSectionFilter(section); setTab('timeline') }}
              className="bg-white border border-gray-200 hover:border-gray-200 rounded-xl p-3 text-left transition-colors"
            >
              <span className={
                'text-xs font-medium px-2 py-0.5 rounded-full ' +
                (SECTION_COLORS[section] || 'bg-gray-200 text-gray-500')
              }>
                {section}
              </span>
              <div className="mt-2 space-y-1">
                <p className="text-gray-500 text-xs">
                  ⚠️ {weaknesses} weakness{weaknesses !== 1 ? 'es' : ''}
                </p>
                <p className="text-gray-500 text-xs">
                  ✅ {strengths} strength{strengths !== 1 ? 's' : ''}
                </p>
                {archived > 0 && (
                  <p className="text-gray-500 text-xs">🏆 {archived} mastered</p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {[
          { id: 'timeline', label: '📈 Memory Timeline' },
          { id: 'active', label: `🟢 Active (${memories.active.length})` },
          { id: 'archived', label: `🏆 Mastered (${memories.archived.length})` }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={
              'px-4 py-2 rounded-xl text-sm font-medium transition-colors ' +
              (tab === t.id
                ? 'bg-brand-500 text-gray-900'
                : 'bg-gray-100 text-gray-500 hover:text-gray-900')
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Timeline tab */}
      {tab === 'timeline' && (
        <div>
          {/* Section filter */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {sections.map(s => (
              <button
                key={s}
                onClick={() => setSectionFilter(s)}
                className={
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ' +
                  (sectionFilter === s
                    ? 'bg-gray-600 text-gray-900'
                    : 'bg-gray-100 text-gray-500 hover:text-gray-600')
                }
              >
                {s}
              </button>
            ))}
          </div>

          {filteredTimeline.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center">
              <Brain className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500">
                No memories yet for this section. Complete some practice sessions
                and your coach will start building your memory profile.
              </p>
            </div>
          ) : (
            <div>
              {/* Legend */}
              <div className="flex items-center gap-4 mb-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" />
                  Weakness
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                  Strength
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-gray-600 inline-block" />
                  Mastered
                </span>
                <span className="ml-auto">
                  {filteredTimeline.length} memories
                  {sectionFilter !== 'All' ? ` in ${sectionFilter}` : ''}
                </span>
              </div>

              {/* Timeline */}
              <div className="space-y-0">
                {filteredTimeline.map(memory => (
                  <TimelineCard key={memory.memory_id} memory={memory} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Active memories tab */}
      {tab === 'active' && (
        <div className="space-y-3">
          {memories.active.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center">
              <Brain className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500">
                No active memories yet. Complete some practice sessions
                and your coach will start building your memory profile.
              </p>
            </div>
          ) : (
            memories.active.map(renderMemory)
          )}
        </div>
      )}

      {/* Archived/Mastered tab */}
      {tab === 'archived' && (
        <div className="space-y-3">
          {memories.archived.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center">
              <Archive className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500">
                No mastered skills yet. Memories are archived when your
                coach considers a skill fully conquered.
              </p>
            </div>
          ) : (
            memories.archived.map(renderMemory)
          )}
        </div>
      )}
    </div>
  )
}
