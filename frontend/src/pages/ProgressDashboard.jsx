import { useState, useEffect } from 'react'
import {
  getWritingProgress, getReadingProgress,
  getSummary, getSkillRanks
} from '../api/progress'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { TrendingUp, Loader2 } from 'lucide-react'

const RANK_NAMES = {
  1: 'Beginner', 2: 'Developing', 3: 'Intermediate',
  4: 'Proficient', 5: 'Advanced'
}
const RANK_COLORS = {
  1: 'bg-red-500/15 text-red-400',
  2: 'bg-orange-500/15 text-orange-400',
  3: 'bg-yellow-500/15 text-yellow-400',
  4: 'bg-blue-500/15 text-blue-400',
  5: 'bg-green-500/15 text-green-400',
}

export default function ProgressDashboard() {
  const [tab, setTab] = useState('writing')
  const [summary, setSummary] = useState(null)
  const [writingData, setWritingData] = useState(null)
  const [readingData, setReadingData] = useState(null)
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getSummary(),
      getWritingProgress(),
      getReadingProgress(),
      getSkillRanks()
    ]).then(([sumRes, wRes, rRes, skRes]) => {
      setSummary(sumRes.data)
      setWritingData(wRes.data)
      setReadingData(rRes.data)
      setSkills(skRes.data.skills || [])
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
    </div>
  )

  // Build chart data for writing
  const writingChartData = (writingData?.attempts || []).map((a, i) => ({
    attempt: `#${i + 1}`,
    'Thesis': a.scores?.thesis_clarity || 0,
    'Organization': a.scores?.organization || 0,
    'Grammar': a.scores?.grammar || 0,
    'Vocabulary': a.scores?.vocabulary || 0,
    'Ideas': a.scores?.idea_development || 0,
  }))

  // Build chart data for reading
  const readingChartData = (readingData?.attempts || []).map((a, i) => ({
    attempt: `#${i + 1}`,
    'Score %': a.percentage || 0
  }))

  return (
    <div className="p-6 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-green-400" />
          Progress Dashboard
        </h1>
        <p className="text-gray-500 mt-1">
          Track your improvement across all IELTS skills
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Writing attempts', value: summary?.writing_attempts ?? 0 },
          { label: 'Reading attempts', value: summary?.reading_attempts ?? 0 },
          { label: 'Active memories', value: summary?.active_memories ?? 0 },
          {
            label: 'Avg skill rank',
            value: summary?.average_skill_rank
              ? `${Number(summary.average_skill_rank).toFixed(1)}/5`
              : '—'
          },
        ].map(({ label, value }) => (
          <div key={label}
               className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            <p className="text-gray-500 text-sm mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'writing', label: '✍️ Writing' },
          { id: 'reading', label: '📖 Reading' },
          { id: 'skills',  label: '🎯 Skill Ranks' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-xl text-sm font-medium
                        transition-colors ${
              tab === t.id
                ? 'bg-brand-500 text-gray-900'
                : 'bg-gray-100 text-gray-500 hover:text-gray-900'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Writing tab */}
      {tab === 'writing' && (
        <div className="space-y-6">
          {writingChartData.length < 2 ? (
            <div className="bg-white border border-gray-200 rounded-2xl
                            p-12 text-center">
              <p className="text-gray-500">
                Submit at least 2 essays to see your score trends
              </p>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">
                Writing Score Trends
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={writingChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="attempt" stroke="#6b7280" fontSize={12} />
                  <YAxis domain={[0, 5]} stroke="#6b7280" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#111827',
                      border: '1px solid #374151',
                      borderRadius: '12px'
                    }}
                  />
                  <Legend />
                  {['Thesis','Organization','Grammar','Vocabulary','Ideas']
                    .map((key, i) => (
                    <Line
                      key={key}
                      type="monotone"
                      dataKey={key}
                      stroke={['#8b5cf6','#3b82f6','#10b981','#f59e0b','#ef4444'][i]}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Writing attempt history */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4">
              Attempt History
            </h2>
            {(writingData?.attempts || []).length === 0 ? (
              <p className="text-gray-500 text-sm">No writing attempts yet</p>
            ) : (
              <div className="space-y-3">
                {[...(writingData?.attempts || [])].reverse().map((a, i) => (
                  <div key={a.attempt_id}
                       className="flex items-center justify-between
                                  py-3 border-b border-gray-200 last:border-0">
                    <div>
                      <p className="text-gray-600 text-sm font-medium">
                        Attempt #{writingData.attempts.length - i}
                      </p>
                      <p className="text-gray-500 text-xs mt-0.5">
                        {a.created_at?.slice(0, 16).replace('T', ' at ')}
                      </p>
                    </div>
                    <div className="flex gap-3">
                      {Object.entries(a.scores || {}).map(([k, v]) => (
                        <div key={k} className="text-center">
                          <p className={`text-sm font-bold ${
                            v >= 4 ? 'text-green-400' :
                            v >= 3 ? 'text-yellow-400' : 'text-red-400'
                          }`}>{v}</p>
                          <p className="text-gray-600 text-xs">
                            {k.split('_')[0]}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reading tab */}
      {tab === 'reading' && (
        <div className="space-y-6">
          {readingChartData.length < 2 ? (
            <div className="bg-white border border-gray-200 rounded-2xl
                            p-12 text-center">
              <p className="text-gray-500">
                Complete at least 2 passages to see your score trends
              </p>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">
                Reading Score Trends
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={readingChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="attempt" stroke="#6b7280" fontSize={12} />
                  <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#111827',
                      border: '1px solid #374151',
                      borderRadius: '12px'
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="Score %"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Reading attempt history */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4">
              Attempt History
            </h2>
            {(readingData?.attempts || []).length === 0 ? (
              <p className="text-gray-500 text-sm">No reading attempts yet</p>
            ) : (
              <div className="space-y-3">
                {[...(readingData?.attempts || [])].reverse().map((a, i) => (
                  <div key={a.attempt_id}
                       className="flex items-center justify-between
                                  py-3 border-b border-gray-200 last:border-0">
                    <div>
                      <p className="text-gray-600 text-sm font-medium">
                        {a.passage_title || `Attempt #${i + 1}`}
                      </p>
                      <p className="text-gray-500 text-xs mt-0.5">
                        {a.created_at?.slice(0, 16).replace('T', ' at ')}
                      </p>
                    </div>
                    <div className={`text-lg font-bold ${
                      (a.percentage || 0) >= 80 ? 'text-green-400' :
                      (a.percentage || 0) >= 60 ? 'text-yellow-400' :
                      'text-red-400'
                    }`}>
                      {a.percentage || 0}%
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Skills tab */}
      {tab === 'skills' && (
        <div className="space-y-4">
          <p className="text-gray-500 text-sm">
            Your mastery level on each of the 13 IELTS Writing sub-skills,
            based on your essay submissions.
          </p>
          {skills.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-2xl
                            p-12 text-center">
              <p className="text-gray-500">
                Submit a writing essay to see your skill profile
              </p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {skills.map(skill => (
                <div key={skill.skill_id}
                     className="bg-white border border-gray-200
                                rounded-2xl p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-900 text-sm font-medium truncate">
                        {skill.skill_name}
                      </p>
                      <p className="text-gray-500 text-xs mt-0.5">
                        {skill.category_name}
                      </p>
                    </div>
                    <span className={`text-xs font-medium px-2.5 py-1
                                      rounded-lg ml-3 flex-shrink-0
                                      ${RANK_COLORS[skill.current_rank]}`}>
                      {RANK_NAMES[skill.current_rank]}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-gray-100 rounded-full
                                    overflow-hidden">
                      <div
                        className="h-full bg-brand-500 rounded-full"
                        style={{
                          width: `${(skill.current_rank / 5) * 100}%`
                        }}
                      />
                    </div>
                    <span className="text-gray-500 text-xs flex-shrink-0">
                      {skill.current_rank}/5
                    </span>
                  </div>
                  {skill.total_evidence > 0 && (
                    <p className="text-gray-600 text-xs mt-2">
                      {skill.total_evidence} assessment(s) ·{' '}
                      streak: {skill.clean_streak}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
