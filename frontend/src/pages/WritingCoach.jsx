import { useState, useEffect } from 'react'
import { getPrompt, getWritingMemories, submitEssay } from '../api/writing'
import { PenLine, RefreshCw, Brain, ChevronRight, Loader2 } from 'lucide-react'

const SKILL_LABELS = {
  thesis_clarity: 'Thesis Clarity',
  organization: 'Organization',
  grammar: 'Grammar',
  vocabulary: 'Vocabulary',
  idea_development: 'Idea Development'
}

export default function WritingCoach() {
  const [prompt, setPrompt] = useState(null)
  const [memories, setMemories] = useState([])
  const [essay, setEssay] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    loadPromptAndMemories()
  }, [])

  const loadPromptAndMemories = async () => {
    setLoading(true)
    setFeedback(null)
    setEssay('')
    setError('')
    try {
      const [promptRes, memRes] = await Promise.all([
        getPrompt(),
        getWritingMemories()
      ])
      setPrompt(promptRes.data)
      setMemories(memRes.data.memories || [])
    } catch (err) {
      setError('Could not load writing prompt. Please refresh.')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!prompt || essay.trim().length < 50) return
    setSubmitting(true)
    setError('')
    try {
      const res = await submitEssay({
        prompt: prompt.prompt,
        task_type: prompt.task_type,
        essay: essay.trim()
      })
      setFeedback(res.data)
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Something went wrong. Please try again.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  const wordCount = essay.trim()
    ? essay.trim().split(/\s+/).length
    : 0

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto mb-3" />
          <p className="text-gray-400">Loading your writing session...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <PenLine className="w-6 h-6 text-purple-400" />
            Writing Coach
          </h1>
          <p className="text-gray-400 mt-1">
            Practice IELTS writing and get personalised AI feedback
          </p>
        </div>
        <button
          onClick={loadPromptAndMemories}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800
                     hover:bg-gray-700 text-gray-300 rounded-xl text-sm
                     transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          New prompt
        </button>
      </div>

      {/* Memory panel */}
      {memories.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">
              What your coach remembers
            </span>
          </div>
          <div className="space-y-2">
            {memories.map((mem, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-sm mt-0.5">
                  {mem.memory_type === 'weakness' ? '⚠️' : '✅'}
                </span>
                <p className="text-gray-400 text-sm">
                  <span className="text-gray-300 font-medium">
                    {mem.skill}:
                  </span>{' '}
                  {mem.memory_text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!feedback ? (
        <>
          {/* Prompt card */}
          {prompt && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl
                            p-6 mb-6">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-medium px-2.5 py-1 rounded-lg
                                 bg-purple-500/15 text-purple-400">
                  {prompt.task_type}
                </span>
                <span className="text-xs font-medium px-2.5 py-1 rounded-lg
                                 bg-gray-800 text-gray-400 capitalize">
                  {prompt.difficulty}
                </span>
              </div>
              <p className="text-white leading-relaxed">{prompt.prompt}</p>
              {prompt.target_skills?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-4">
                  {prompt.target_skills.map(skill => (
                    <span key={skill}
                          className="text-xs px-2 py-1 rounded-lg
                                     bg-gray-800 text-gray-500">
                      {skill.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Essay input */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-gray-300">
                Your response
              </label>
              <span className={`text-sm ${
                wordCount >= 250
                  ? 'text-green-400'
                  : wordCount > 0
                  ? 'text-yellow-400'
                  : 'text-gray-500'
              }`}>
                {wordCount} / 250 words minimum
              </span>
            </div>

            <textarea
              value={essay}
              onChange={e => setEssay(e.target.value)}
              placeholder="Write your essay here. Aim for at least 250 words..."
              className="w-full h-72 bg-gray-800 border border-gray-700
                         rounded-xl px-4 py-3 text-white placeholder-gray-600
                         focus:outline-none focus:border-brand-500
                         transition-colors resize-none text-sm leading-relaxed"
            />

            {error && (
              <div className="mt-3 bg-red-500/10 border border-red-500/30
                              rounded-lg p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <div className="flex items-center justify-between mt-4">
              <div>
                {wordCount > 0 && wordCount < 250 && (
                  <p className="text-yellow-400 text-sm">
                    {250 - wordCount} more words needed
                  </p>
                )}
                {wordCount >= 250 && (
                  <p className="text-green-400 text-sm">
                    ✓ Word count looks good!
                  </p>
                )}
              </div>
              <button
                onClick={handleSubmit}
                disabled={submitting || wordCount < 50}
                className="flex items-center gap-2 px-6 py-3 bg-brand-500
                           hover:bg-brand-600 disabled:opacity-50
                           disabled:cursor-not-allowed text-white font-semibold
                           rounded-xl transition-colors"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Evaluating...
                  </>
                ) : (
                  <>
                    Submit for feedback
                    <ChevronRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      ) : (
        /* Feedback display */
        <div className="space-y-6">

          {/* Overall feedback */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-3">
              📊 Overall Feedback
            </h2>
            <p className="text-gray-300 leading-relaxed">
              {feedback.overall_feedback}
            </p>
          </div>

          {/* Scores */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Skill Scores
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              {Object.entries(feedback.scores || {}).map(([key, score]) => (
                <div key={key} className="text-center">
                  <div className={`text-3xl font-bold mb-1 ${
                    score >= 4 ? 'text-green-400' :
                    score >= 3 ? 'text-yellow-400' : 'text-red-400'
                  }`}>
                    {score}
                    <span className="text-gray-600 text-lg">/5</span>
                  </div>
                  <p className="text-gray-500 text-xs">
                    {SKILL_LABELS[key] || key}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Strengths and weaknesses */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-green-400 mb-3">
                ✅ Strengths
              </h2>
              <ul className="space-y-2">
                {(feedback.strengths || []).map((s, i) => (
                  <li key={i} className="text-gray-300 text-sm
                                         flex items-start gap-2">
                    <span className="text-green-500 mt-0.5 flex-shrink-0">•</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-yellow-400 mb-3">
                ⚠️ Areas to Improve
              </h2>
              <ul className="space-y-2">
                {(feedback.weaknesses || []).map((w, i) => (
                  <li key={i} className="text-gray-300 text-sm
                                         flex items-start gap-2">
                    <span className="text-yellow-500 mt-0.5 flex-shrink-0">•</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Recommended next step */}
          {feedback.recommended_next_step && (
            <div className="bg-brand-500/10 border border-brand-500/30
                            rounded-2xl p-6">
              <h2 className="text-base font-semibold text-brand-400 mb-2">
                🎯 Recommended Next Step
              </h2>
              <p className="text-gray-300 text-sm leading-relaxed">
                {feedback.recommended_next_step}
              </p>
            </div>
          )}

          {/* Try again */}
          <div className="flex gap-4">
            <button
              onClick={() => setFeedback(null)}
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700
                         text-white rounded-xl transition-colors"
            >
              Try same prompt again
            </button>
            <button
              onClick={loadPromptAndMemories}
              className="px-6 py-3 bg-brand-500 hover:bg-brand-600
                         text-white font-semibold rounded-xl transition-colors"
            >
              New prompt →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
