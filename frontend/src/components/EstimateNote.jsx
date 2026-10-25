import { Info } from 'lucide-react'

const DEFAULT_TEXT =
  'AI estimate for practice — not an official IELTS score. Treat it as a guide to within about one band.'

export default function EstimateNote({ children, className = '' }) {
  return (
    <p className={'flex items-start gap-1.5 text-xs text-gray-400 ' + className}>
      <Info className="w-3.5 h-3.5 mt-px flex-shrink-0" aria-hidden="true" />
      <span>{children || DEFAULT_TEXT}</span>
    </p>
  )
}
