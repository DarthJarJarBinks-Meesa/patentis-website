// Matches patent publication numbers like US10123456B2, EP1234567B1, WO2015123456A1.
// Skips numbers already inside a markdown link label (`[US...`) or a patents.google.com URL,
// so it's safe to run even if the model happens to emit a link itself.
const PATENT_NUMBER_RE = /(?<!\[)(?<!\/patent\/)\b([A-Z]{2}-?\d{4,13}-?[A-Z]\d{0,2})\b(?![\]/)])/g

// Matches bare DOI strings like 10.1016/j.biomaterials.2021.120634
// Skips DOIs already inside a markdown link or a doi.org URL.
const DOI_RE = /(?<!\[)(?<!doi\.org\/)(?<!\()(?<!\/)(\b10\.\d{4,9}\/[^\s\])"',]+)/g

export function linkifyPatents(text: string): string {
  if (!text) return text
  return text.replace(PATENT_NUMBER_RE, (match) => {
    const normalized = match.replace(/-/g, '')
    return `[${match}](https://patents.google.com/patent/${normalized}/en)`
  })
}

export function linkifyDOIs(text: string): string {
  if (!text) return text
  return text.replace(DOI_RE, (doi) => {
    const ssUrl = `https://www.semanticscholar.org/search?q=${encodeURIComponent(doi)}`
    return `[${doi}](https://doi.org/${doi}) ([Semantic Scholar](${ssUrl}))`
  })
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

interface TitledLink {
  title: string
  url: string
}

// Wraps each occurrence of a known patent/paper title in the text with a markdown link to
// its URL. Titles are matched longest-first so a title that's a substring of another (rare,
// but possible with truncated LLM output) doesn't steal the shorter match. Skips titles
// already inside a markdown link label so this is safe to run more than once.
export function linkifyTitles(text: string, items: TitledLink[]): string {
  if (!text || !items.length) return text

  const sorted = [...items]
    .filter((item) => item.title && item.url)
    .sort((a, b) => b.title.length - a.title.length)

  let result = text
  for (const { title, url } of sorted) {
    const re = new RegExp(`(?<!\\[)${escapeRegExp(title)}(?!\\]\\(https?:\\/\\/[^)]*\\))`, 'g')
    result = result.replace(re, `[${title}](${url})`)
  }
  return result
}
