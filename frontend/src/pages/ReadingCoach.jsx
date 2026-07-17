import { useState, useEffect, useCallback } from 'react'
import {
  getRandomPassage, getPassageById,
  getReadingMemories, submitReading
} from '../api/reading'
import { BookOpen, Loader2, ChevronRight, Brain, RefreshCw } from 'lucide-react'

const TYPE_LABELS = {
  multiple_choice: 'Multiple Choice',
  true_false_ng: 'True / False / Not Given',
  short_answer: 'Short Answer'
}

const DIFF_COLORS = {
  beginner:     'bg-green-500/15 text-green-400',
  intermediate: 'bg-yellow-500/15 text-yellow-400',
  advanced:     'bg-red-500/15 text-red-400',
}

export default function ReadingCoach() {
  const [phase, setPhase]         = useState('loading')  // loading | reading | results
  const [passage, setPassage]     = useState(null)
  const [memories, setMemories]   = useState([])
  const [answers, setAnswers]     = useState({})
  const [results, setResults]     = useState(null)
  const [loading, setLoading]     = useState(true)
  const [fetching, setFetching]   = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]         = useState('')

  // Load adapted passage + memories on mount
  const loadPassage = useCallback(async () => {
    setFetching(true)
    setError('')
    setAnswers({})
    setResults(null)
    try {
      const [passRes, memRes] = await Promise.all([
        getRandomPassage(),       // backend now returns adaptive unseen passage
        getReadingMemories()
      ])
      setPassage(passRes.data.passage)
      setMemories(memRes.data.memories || [])
      setPhase('reading')
    } catch {
      setError('Could not load passage. Please refresh.')
    } finally {
      setFetching(false)
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadPassage() }, [loadPassage])

  const handleAnswer = (qid, value) =>
    setAnswers(prev => ({ ...prev, [qid]: value }))

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const res = await submitReading({ passage_id: passage.passage_id, answers })
      setResults(res.data)
      setPhase('results')
    } catch (err) {
      setError(err.response?.data?.detail || 'Submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const totalQuestions  = passage?.questions?.length || 0
  const answeredCount   = Object.keys(answers).length

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto mb-3" />
        <p className="text-gray-400">Loading your reading session...</p>
      </div>
    </div>
  )

  return (
    <div className="p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-blue-400" />
            Reading Coach
          </h1>
          <p className="text-gray-400 mt-1">
            Passage adapted to your current band level
          </p>
        </div>
        <button
          onClick={loadPassage}
          disabled={fetching}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 rounded-xl text-sm transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${fetching ? 'animate-spin' : ''}`} />
          New passage
        </button>
      </div>

      {/* Memory panel */}
      {memories.length > 0 && phase !== 'results' && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">What your coach remembers</span>
          </div>
          {memories.map((mem, i) => (
            <p key={i} className="text-gray-400 text-sm mb-1">
              {mem.memory_type === 'weakness' ? '⚠️' : '✅'}{' '}
              <span className="text-gray-300">{mem.skill}:</span>{' '}
              {mem.memory_text}
            </p>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* READING + ANSWERING */}
      {phase === 'reading' && passage && (
        <div className="grid lg:grid-cols-2 gap-6">

          {/* Passage */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-base font-semibold text-white flex-1">{passage.title}</h2>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-lg flex-shrink-0 ${DIFF_COLORS[passage.difficulty]}`}>
                {passage.difficulty}
              </span>
            </div>
            <p className="text-gray-500 text-xs mb-3">{passage.topic}</p>
            <div className="h-[480px] overflow-y-auto pr-2">
              <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">
                {passage.passage}
              </p>
            </div>
          </div>

          {/* Questions */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-white">Questions</h2>
              <span className="text-sm text-gray-500">{answeredCount} / {totalQuestions} answered</span>
            </div>

            <div className="space-y-4 max-h-[480px] overflow-y-auto pr-1">
              {passage.questions.map((q, i) => (
                <div key={q.question_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <p className="text-gray-300 text-sm mb-1">
                    <span className="text-gray-500 mr-1">Q{i + 1}.</span>{q.question}
                  </p>
                  <span className="text-xs text-gray-600 mb-3 block">{TYPE_LABELS[q.question_type]}</span>

                  {q.question_type === 'multiple_choice' && (
                    <div className="space-y-2">
                      {Object.entries(q.options || {}).map(([k, v]) => (
                        <label key={k} className="flex items-center gap-3 cursor-pointer group">
                          <input
                            type="radio"
                            name={q.question_id}
                            value={k}
                            checked={answers[q.question_id] === k}
                            onChange={() => handleAnswer(q.question_id, k)}
                            className="accent-brand-500"
                          />
                          <span className="text-gray-400 text-sm group-hover:text-gray-300">{k}: {v}</span>
                        </label>
                      ))}
                    </div>
                  )}

                  {q.question_type === 'true_false_ng' && (
                    <div className="flex gap-2">
                      {['True', 'False', 'Not Given'].map(opt => (
                        <button
                          key={opt}
                          onClick={() => handleAnswer(q.question_id, opt)}
                          className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                            answers[q.question_id] === opt
                              ? 'bg-brand-500 text-white'
                              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                          }`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  )}

                  {q.question_type === 'short_answer' && (
                    <input
                      type="text"
                      value={answers[q.question_id] || ''}
                      onChange={e => handleAnswer(q.question_id, e.target.value)}
                      placeholder="Your answer..."
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-brand-500 transition-colors"
                    />
                  )}
                </div>
              ))}
            </div>

            <button
              onClick={handleSubmit}
              disabled={submitting || answeredCount < totalQuestions}
              className="w-full flex items-center justify-center gap-2 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
            >
              {submitting
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Checking answers...</>
                : <>Submit answers <ChevronRight className="w-4 h-4" /></>
              }
            </button>
          </div>
        </div>
      )}

      {/* RESULTS */}
      {phase === 'results' && results && (
        <div className="space-y-6">

          <div className={`rounded-2xl p-6 border ${
            results.percentage >= 80 ? 'bg-green-500/10 border-green-500/30' :
            results.percentage >= 60 ? 'bg-yellow-500/10 border-yellow-500/30' :
            'bg-red-500/10 border-red-500/30'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white font-bold text-2xl">{results.total_score} / {results.max_score}</p>
                <p className="text-gray-400 mt-1">{results.passage_title}</p>
              </div>
              <div className={`text-4xl font-bold ${
                results.percentage >= 80 ? 'text-green-400' :
                results.percentage >= 60 ? 'text-yellow-400' : 'text-red-400'
              }`}>
                {results.percentage}%
              </div>
            </div>
          </div>

          {Object.keys(results.skill_accuracy || {}).length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-white mb-4">Skill Breakdown</h2>
              <div className="space-y-3">
                {Object.entries(results.skill_accuracy).map(([skill, acc]) => (
                  <div key={skill}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400 capitalize">{skill.replace(/_/g, ' ')}</span>
                      <span className={acc >= 80 ? 'text-green-400' : acc >= 50 ? 'text-yellow-400' : 'text-red-400'}>{acc}%</span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${acc >= 80 ? 'bg-green-500' : acc >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${acc}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-3">
            <h2 className="text-base font-semibold text-white">Question Review</h2>
            {(results.question_results || []).map((q, i) => (
              <div key={q.question_id} className={`rounded-xl p-4 border ${q.is_correct ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
                <div className="flex items-start gap-3">
                  <span className="text-lg flex-shrink-0">{q.is_correct ? '✅' : '❌'}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-300 text-sm font-medium">Q{i + 1}: {q.question}</p>
                    <p className="text-gray-500 text-xs mt-1">Your answer: <span className="text-gray-400">{q.learner_answer || 'No answer'}</span></p>
                    {!q.is_correct && (
                      <>
                        <p className="text-gray-500 text-xs">Correct: <span className="text-green-400">{q.correct_answer}</span></p>
                        <p className="text-gray-500 text-xs mt-1 italic">{q.feedback}</p>
                      </>
                    )}
                  </div>
                  <span className="text-xs text-gray-600 flex-shrink-0">{q.score}/{q.max_score}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-4">
            <button
              onClick={loadPassage}
              className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
            >
              Next passage →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
