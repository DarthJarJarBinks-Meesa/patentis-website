import type { Idea, FtoClearance } from '../types'

interface Props {
  idea: Idea
  index: number
  selected: boolean
  onSelect: () => void
}

export default function IdeaCard({ idea, index, selected, onSelect }: Props) {
  return (
    <div
      onClick={onSelect}
      className={`cursor-pointer rounded-xl border p-5 transition-all ${
        selected
          ? 'border-indigo-400 bg-indigo-950/50 shadow-lg shadow-indigo-950/50'
          : 'border-gray-700 bg-gray-900 hover:border-gray-500 hover:bg-gray-800/50'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold transition-colors ${
            selected ? 'bg-indigo-500 text-white' : 'bg-gray-700 text-gray-300'
          }`}
        >
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 mb-1">
            <h3 className="text-base font-bold text-gray-100">{idea.title}</h3>
            {idea.fto_clearance && <ClearanceBadge clearance={idea.fto_clearance} />}
          </div>
          <p className="text-sm text-indigo-300 mb-3 italic">{idea.tagline}</p>

          <div className="space-y-3 text-sm">
            <Section label="Description" text={idea.description} />
            <Section label="Key Innovation" text={idea.key_innovation} highlight />
            <Section label="Target Market" text={idea.target_market} />
            <Section label="Technical Approach" text={idea.technical_approach} />
            <Section label="Why Not Yet Patented" text={idea.why_unpatented} />
            {idea.scientific_feasibility && (
              <Section label="Scientific Feasibility" text={idea.scientific_feasibility} feasibility />
            )}
            {idea.supporting_research && (
              <Section label="Supporting Research" text={idea.supporting_research} />
            )}
          </div>

          {selected && (
            <div className="mt-4 flex items-center gap-2 text-indigo-300 text-sm font-medium">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Selected — proceeding with infringement check
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ClearanceBadge({ clearance }: { clearance: FtoClearance }) {
  const colors = clearance.mostly_clear
    ? 'bg-emerald-950/60 border-emerald-700 text-emerald-300'
    : clearance.blocked > 0
      ? 'bg-red-950/60 border-red-700 text-red-300'
      : 'bg-amber-950/60 border-amber-700 text-amber-300'

  return (
    <span
      className={`flex-shrink-0 text-xs font-medium px-2 py-1 rounded-full border whitespace-nowrap ${colors}`}
      title={`FTO: ${clearance.clear} clear, ${clearance.review} worth reviewing, ${clearance.blocked} likely blocked`}
    >
      FTO: {clearance.label}
    </span>
  )
}

function Section({
  label,
  text,
  highlight,
  feasibility,
}: {
  label: string
  text: string
  highlight?: boolean
  feasibility?: boolean
}) {
  return (
    <div>
      <span
        className={`text-xs font-semibold uppercase tracking-wide ${
          highlight ? 'text-indigo-400' : feasibility ? 'text-emerald-400' : 'text-gray-400'
        }`}
      >
        {label}
      </span>
      <p
        className={`mt-0.5 leading-relaxed ${
          highlight ? 'text-gray-200' : feasibility ? 'text-emerald-200' : 'text-gray-400'
        }`}
      >
        {text}
      </p>
    </div>
  )
}
