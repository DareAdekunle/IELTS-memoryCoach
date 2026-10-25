const LIMIT_TEXT = { 1: 'ONE WORD', 2: 'NO MORE THAN TWO WORDS', 3: 'NO MORE THAN THREE WORDS' }

// Mirrors app/services/answer_matching.count_words: tokens containing a digit are numbers and don't count.
function countWords(text) {
  return (text || '').trim().split(/\s+/).filter(t => t && !/\d/.test(t)).length
}

export default function WordLimitHint({ limit, value }) {
  if (!limit) return null
  const words = countWords(value)
  const over = words > limit
  const label = LIMIT_TEXT[limit] || 'NO MORE THAN ' + limit + ' WORDS'
  return (
    <p className={'mt-1.5 text-xs ' + (over ? 'text-red-600' : 'text-gray-400')}>
      Write {label} and/or a number.
      {over ? ' Your answer is too long — it will be marked wrong.' : ''}
    </p>
  )
}
