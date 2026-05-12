export interface Patent {
  id: string
  title: string
  abstract: string
  claims?: string
  filing_date?: string
  assignee?: string
  inventors: string[]
  url: string
  source: 'uspto' | 'epo'
}

export interface Paper {
  id: string
  title: string
  abstract: string
  authors: string[]
  published?: string
  url: string
  source: 'pubmed'
}

export interface Idea {
  title: string
  tagline: string
  description: string
  key_innovation: string
  target_market: string
  technical_approach: string
  why_unpatented: string
  scientific_feasibility?: string
  supporting_research?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export type Step = 1 | 2 | 3 | 4 | 5
