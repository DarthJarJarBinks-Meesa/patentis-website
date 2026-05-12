import type { Paper } from '../types'

interface Props {
  paper: Paper
  selected: boolean
  onToggle: () => void
}

const SOURCE_BADGE: Record<string, string> = {
  pubmed: 'bg-blue-900/60 text-blue-300 border-blue-700',
}

const SOURCE_LABEL: Record<string, string> = {
  pubmed: 'PubMed',
}

export default function PaperCard({ paper, selected, onToggle }: Props) {
  return (
    <div
      onClick={onToggle}
      className={`relative cursor-pointer rounded-xl border p-4 transition-all ${
        selected
          ? 'border-indigo-500 bg-indigo-950/40'
          : 'border-gray-700 bg-gray-900 hover:border-gray-500'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`mt-0.5 w-4 h-4 rounded flex-shrink-0 flex items-center justify-center border-2 transition-colors ${
            selected ? 'bg-indigo-500 border-indigo-500' : 'border-gray-500'
          }`}
        >
          {selected && (
            <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full border ${SOURCE_BADGE[paper.source] ?? 'bg-gray-700 text-gray-300'}`}
            >
              {SOURCE_LABEL[paper.source] ?? paper.source}
            </span>
            {paper.published && (
              <span className="text-xs text-gray-500">{paper.published}</span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-gray-100 leading-snug mb-1 line-clamp-2">
            {paper.title}
          </h3>
          {paper.authors.length > 0 && (
            <p className="text-xs text-gray-400 mb-1">{paper.authors.slice(0, 3).join(', ')}{paper.authors.length > 3 ? ' et al.' : ''}</p>
          )}
          {paper.abstract && (
            <p className="text-xs text-gray-500 line-clamp-3 leading-relaxed">{paper.abstract}</p>
          )}
          <a
            href={paper.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="mt-2 inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
          >
            View paper
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  )
}
