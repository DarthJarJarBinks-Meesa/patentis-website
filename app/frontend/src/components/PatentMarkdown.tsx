import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { linkifyPatents, linkifyDOIs, linkifyTitles } from '../utils/linkifyPatents'
import type { Patent, Paper } from '../types'

const REMARK_PLUGINS = [remarkGfm]

// Domains we trust to have real, stable URLs. Everything else gets replaced
// with a Google Scholar search so hallucinated URLs don't silently 404.
const TRUSTED_DOMAINS = [
  'patents.google.com',
  'doi.org',
  'pubmed.ncbi.nlm.nih.gov',
  'www.ncbi.nlm.nih.gov',
  'semanticscholar.org',
  'epo.org',
  'espacenet.com',
  'scholar.google.com',
  'lens.org',
]

function isTrusted(href: string): boolean {
  try {
    const host = new URL(href).hostname.replace(/^www\./, '')
    return TRUSTED_DOMAINS.some((d) => d.replace(/^www\./, '') === host || host.endsWith('.' + d.replace(/^www\./, '')))
  } catch {
    return false
  }
}

function safeHref(href: string | undefined, linkText: string): string {
  if (!href) return `https://scholar.google.com/scholar?q=${encodeURIComponent(linkText)}`
  if (isTrusted(href)) return href
  return `https://scholar.google.com/scholar?q=${encodeURIComponent(linkText)}`
}

const components = {
  a: ({ href, children, ...props }: React.ComponentPropsWithoutRef<'a'>) => {
    const text = typeof children === 'string' ? children : String(children ?? '')
    const resolvedHref = safeHref(href, text)
    return (
      <a
        href={resolvedHref}
        target="_blank"
        rel="noopener noreferrer"
        className="text-indigo-400 hover:text-indigo-300 underline break-all"
        {...props}
      >
        {children}
      </a>
    )
  },
}

export default function PatentMarkdown({
  text,
  className,
  patents,
  papers,
}: {
  text: string
  className?: string
  patents?: Patent[]
  papers?: Paper[]
}) {
  let content = text
  if (patents?.length) content = linkifyTitles(content, patents)
  if (papers?.length) content = linkifyTitles(content, papers)
  content = linkifyPatents(content)
  content = linkifyDOIs(content)

  return (
    <ReactMarkdown className={className} remarkPlugins={REMARK_PLUGINS} components={components}>
      {content}
    </ReactMarkdown>
  )
}
