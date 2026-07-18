import { Link } from 'react-router-dom'
import {
  Target, Brain, Zap, TrendingUp, BookOpen, Mic, PenLine,
  Headphones, MessageSquare, ChevronRight, Check, Star,
} from 'lucide-react'

const STATS = [
  { value: '40,000+', label: 'Active learners' },
  { value: '+0.9',    label: 'Avg band gain' },
  { value: '24/7',    label: 'Always available' },
  { value: '4.8★',   label: 'User rating' },
]

const FEATURES = [
  {
    icon: Brain,
    color: 'text-brand-600',
    bg: 'bg-brand-50',
    title: 'Memory-aware coaching',
    desc: 'Your AI coach remembers every essay, every mistake, every pattern — and uses that context to make every session smarter.',
  },
  {
    icon: TrendingUp,
    color: 'text-violet-600',
    bg: 'bg-violet-50',
    title: 'Tracks your weak spots',
    desc: 'Highlights any line in a passage or essay and gets an answer tied to that exact spot — so practice is targeted, not random.',
  },
  {
    icon: Zap,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    title: 'Adapts in real-time',
    desc: 'Remembers patterns across sessions and adjusts your next drill automatically based on your skill ranks.',
  },
]

const SECTIONS = [
  { icon: PenLine,    label: 'Writing',   color: 'text-violet-600', bg: 'bg-violet-50',  desc: 'AI scoring on all 4 rubrics + skill classification' },
  { icon: BookOpen,   label: 'Reading',   color: 'text-blue-600',   bg: 'bg-blue-50',    desc: 'Passages matched to your current band level' },
  { icon: Mic,        label: 'Speaking',  color: 'text-emerald-600',bg: 'bg-emerald-50', desc: '3-part AI examiner session with ASR + scoring' },
  { icon: Headphones, label: 'Listening', color: 'text-amber-600',  bg: 'bg-amber-50',   desc: 'Listen once, answer questions, instant feedback' },
]

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    features: ['5 practice sessions/month', 'Writing & Reading coach', 'Basic memory tracking'],
    cta: 'Get started free',
    highlight: false,
  },
  {
    name: 'Pro',
    price: '$12',
    period: 'per month',
    features: ['Unlimited sessions', 'All 4 IELTS sections', 'Full memory timeline', 'Skill mastery tracking', 'Priority support'],
    cta: 'Start free trial',
    highlight: true,
  },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">

      {/* Nav */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <Target className="w-[18px] h-[18px] text-white" />
            </div>
            <span className="font-bold text-gray-900 text-sm">Qonda IELTS</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#sections" className="hover:text-gray-900 transition-colors">Sections</a>
            <a href="#pricing" className="hover:text-gray-900 transition-colors">Pricing</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900 font-medium transition-colors">
              Sign in
            </Link>
            <Link
              to="/register"
              className="text-sm bg-brand-600 text-white font-semibold px-4 py-2 rounded-xl hover:bg-brand-700 transition-colors"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-brand-50 border border-brand-100 text-brand-700 text-xs font-semibold px-4 py-2 rounded-full mb-8">
            <Star className="w-3.5 h-3.5 fill-brand-500 text-brand-500" />
            AI-powered IELTS coaching
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold text-gray-900 leading-tight mb-6">
            Grasp English.<br />
            <span className="text-brand-600">Retain for life.</span>
          </h1>
          <p className="text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Qonda IELTS pairs adaptive lessons across all four skills with an AI tutor that truly comprehends your weaknesses — building a richer picture of you with every session.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/register"
              className="inline-flex items-center gap-2 bg-brand-600 text-white font-semibold px-7 py-3.5 rounded-2xl hover:bg-brand-700 transition-colors text-base"
            >
              Start for free <ChevronRight className="w-4 h-4" />
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 bg-gray-100 text-gray-700 font-semibold px-7 py-3.5 rounded-2xl hover:bg-gray-200 transition-colors text-base"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {STATS.map(({ value, label }) => (
              <div key={label} className="text-center">
                <p className="text-3xl font-extrabold text-gray-900 mb-1">{value}</p>
                <p className="text-gray-500 text-sm">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 px-6 bg-slate-50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">How the tutor helps</h2>
            <p className="text-gray-500 text-lg max-w-xl mx-auto">
              Unlike a generic app, Qonda builds a long-term picture of your abilities.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map(({ icon: Icon, color, bg, title, desc }) => (
              <div key={title} className="bg-white rounded-2xl border border-gray-200 p-6">
                <div className={'w-11 h-11 rounded-2xl flex items-center justify-center mb-4 ' + bg}>
                  <Icon className={'w-5 h-5 ' + color} />
                </div>
                <h3 className="text-gray-900 font-semibold text-base mb-2">{title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Sections */}
      <section id="sections" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">All four IELTS skills, one platform</h2>
            <p className="text-gray-500 text-lg max-w-xl mx-auto">
              Every section has its own AI coach, scoring model, and memory layer.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {SECTIONS.map(({ icon: Icon, label, color, bg, desc }) => (
              <div key={label} className="flex items-start gap-4 p-5 bg-white rounded-2xl border border-gray-200">
                <div className={'w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0 ' + bg}>
                  <Icon className={'w-5 h-5 ' + color} />
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">{label}</h3>
                  <p className="text-gray-500 text-sm">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 px-6 bg-slate-50">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Simple pricing</h2>
            <p className="text-gray-500 text-lg">Start free. Upgrade when you're ready.</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-6">
            {PLANS.map(plan => (
              <div
                key={plan.name}
                className={'rounded-2xl border p-7 ' + (plan.highlight
                  ? 'bg-brand-600 border-brand-600 text-white'
                  : 'bg-white border-gray-200')}
              >
                <p className={'text-sm font-semibold mb-1 ' + (plan.highlight ? 'text-brand-200' : 'text-gray-500')}>
                  {plan.name}
                </p>
                <div className="flex items-end gap-1 mb-6">
                  <span className={'text-4xl font-extrabold ' + (plan.highlight ? 'text-white' : 'text-gray-900')}>
                    {plan.price}
                  </span>
                  <span className={'text-sm mb-1.5 ' + (plan.highlight ? 'text-brand-200' : 'text-gray-400')}>
                    /{plan.period}
                  </span>
                </div>
                <ul className="space-y-2.5 mb-8">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-center gap-2.5 text-sm">
                      <Check className={'w-4 h-4 flex-shrink-0 ' + (plan.highlight ? 'text-brand-200' : 'text-brand-600')} />
                      <span className={plan.highlight ? 'text-white' : 'text-gray-700'}>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  to="/register"
                  className={'block text-center font-semibold py-3 rounded-xl text-sm transition-colors ' + (plan.highlight
                    ? 'bg-white text-brand-700 hover:bg-brand-50'
                    : 'bg-brand-600 text-white hover:bg-brand-700')}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <div className="w-14 h-14 bg-brand-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Target className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Ready to hit your band target?</h2>
          <p className="text-gray-500 text-lg mb-8">
            Join thousands of learners who've improved their IELTS band with a coach that actually remembers them.
          </p>
          <Link
            to="/register"
            className="inline-flex items-center gap-2 bg-brand-600 text-white font-semibold px-8 py-4 rounded-2xl hover:bg-brand-700 transition-colors text-base"
          >
            Start coaching for free <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-brand-600 rounded-md flex items-center justify-center">
              <Target className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-gray-600 text-sm font-semibold">Qonda IELTS</span>
          </div>
          <p className="text-gray-400 text-sm">© {new Date().getFullYear()} Qonda IELTS. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
