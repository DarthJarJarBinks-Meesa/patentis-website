import ReactMarkdown from 'react-markdown'
import { linkifyPatents, linkifyTitles } from '../utils/linkifyPatents'
import type { Patent, Paper } from '../types'

const components = {
  a: ({ href, children, ...props }: React.ComponentPropsWithoutRef<'a'>) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-indigo-400 hover:text-indigo-300 underline"
      {...props}
    >
      {children}
    </a>
  ),
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

  return (
    <ReactMarkdown className={className} components={components}>
      {content}
    </ReactMarkdown>
  )
}
