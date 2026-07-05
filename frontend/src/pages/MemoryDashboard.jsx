import { useState, useEffect } from 'react'
import { getAllMemories } from '../api/memory'
import { Brain, Loader2, Archive } from 'lucide-react'

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

export default function MemoryDashboard() {
  const [memories, setMemories] = useState({ active: [], archived: [] })
  const [stats, setStats] = useState(null)
  const [tab, setTab] = useState('active')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAllMemories()
      .then(res => {
        setMemories({
          active: res.data.active || [],
          archived: res.data.archived || []
        })
        setStats(res.data.stats || null)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
    </div>
  )

  const renderMemory = (mem) => (
    <div key={mem.memory_id}
         className={`rounded-xl p-4 border ${TYPE_COLORS[mem.memory_type]
                      || 'border-gray-800 bg-gray-900'}`}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span>{TYPE_ICONS[mem.memory_type] || '📝'}</span>
          <div className="min-w-0">
            <span className="text-white text-sm font-medium">
              {mem.skill}
            </span>
            <span className="text-gray-600 text-xs ml-2">
              {mem.section}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="text-right">
            <div className="flex items-center gap-1">
              <div className="h-1.5 w-16 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-brand-500 rounded-full"
                  style={{ width: `${(mem.confidence || 0) * 100}%` }}
                />
              </div>
              <span className="text-gray-500 text-xs">
                {Math.round((mem.confidence || 0) * 100)}%
              </span>
            </div>
            <p className="text-gray-600 text-xs mt-0.5 text-right">
              {mem.evidence_count} evidence
            </p>
          </div>
        </div>
      </div>
      <p className="text-gray-300 text-sm leading-relaxed">
        {mem.memory_text}
      </p>
    </div>
  )

  return (
    <div className="p-6 max-w-4xl mx-auto">

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Brain className="w-6 h-6 text-green-400" />
          Memory Dashboard
        </h1>
        <p className="text-gray-400 mt-1">
          Everything your coach has learned about you
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total memories', value: stats.total_memories ?? 0 },
            { label: 'Active', value: stats.active_count ?? 0 },
            { label: 'Archived', value: stats.archived_count ?? 0 },
            {
              label: 'Avg confidence',
              value: stats.avg_confidence
                ? `${Math.round(stats.avg_confidence * 100)}%`
                : '—'
            },
          ].map(({ label, value }) => (
            <div key={label}
                 className="bg-gray-900 border border-gray-800
                            rounded-2xl p-4">
              <p className="text-xl font-bold text-white">{value}</p>
              <p className="text-gray-500 text-sm mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setTab('active')}
          className={`px-4 py-2 rounded-xl text-sm font-medium
                      transition-colors ${
            tab === 'active'
              ? 'bg-brand-500 text-white'
              : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          🟢 Active ({memories.active.length})
        </button>
        <button
          onClick={() => setTab('archived')}
          className={`px-4 py-2 rounded-xl text-sm font-medium
                      transition-colors ${
            tab === 'archived'
              ? 'bg-brand-500 text-white'
              : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          📦 Archived ({memories.archived.length})
        </button>
      </div>

      {/* Active memories */}
      {tab === 'active' && (
        <div className="space-y-3">
          {memories.active.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl
                            p-12 text-center">
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

      {/* Archived memories */}
      {tab === 'archived' && (
        <div className="space-y-3">
          {memories.archived.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl
                            p-12 text-center">
              <Archive className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500">
                No archived memories yet. Archived memories appear when
                your coach considers a skill fully mastered.
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
