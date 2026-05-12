const BASE = '/api'

let _groqApiKey = ''

export function setGroqApiKey(key: string) {
  _groqApiKey = key
}

function groqHeaders(): Record<string, string> {
  return _groqApiKey ? { 'X-Groq-Api-Key': _groqApiKey } : {}
}

export async function searchPatents(query: string) {
  const res = await fetch(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...groqHeaders() },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function updateSelection(
  sessionId: string,
  patentIds: string[],
  paperIds: string[],
) {
  const res = await fetch(`${BASE}/session/${sessionId}/selection`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...groqHeaders() },
    body: JSON.stringify({ patent_ids: patentIds, paper_ids: paperIds }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function generateIdeas(sessionId: string) {
  const res = await fetch(`${BASE}/session/${sessionId}/generate-ideas`, {
    method: 'POST',
    headers: { ...groqHeaders() },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function* streamSSE(
  url: string,
  options?: RequestInit,
): AsyncGenerator<{ content?: string; done?: boolean; error?: string }> {
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options?.headers ?? {}),
      ...groqHeaders(),
      Accept: 'text/event-stream',
    },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  if (!res.body) throw new Error('No response body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            yield JSON.parse(raw)
          } catch {
            // skip malformed lines
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export function streamAnalysis(sessionId: string) {
  return streamSSE(`${BASE}/session/${sessionId}/analyze`, { method: 'POST' })
}

export function streamSelectIdea(sessionId: string, ideaIndex: number) {
  return streamSSE(`${BASE}/session/${sessionId}/select-idea`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idea_index: ideaIndex }),
  })
}

export function streamChat(sessionId: string, message: string) {
  return streamSSE(`${BASE}/session/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
}
