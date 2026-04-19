import { api } from './client'

export interface SolutionTemplate {
  id: number
  name: string
  description: string | null
  content: string
  tags: string | null
  template_md_path: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SolutionTemplateCreate {
  name: string
  description?: string | null
  content: string
  tags?: string | null
}

export interface SolutionTemplateUpdate {
  name?: string | null
  description?: string | null
  content?: string | null
  tags?: string | null
}

export const templatesApi = {
  async list(keyword?: string) {
    const { data } = await api.get<SolutionTemplate[]>('/templates', {
      params: keyword ? { keyword } : undefined,
    })
    return data
  },
  async get(id: number) {
    const { data } = await api.get<SolutionTemplate>(`/templates/${id}`)
    return data
  },
  async create(payload: SolutionTemplateCreate) {
    const { data } = await api.post<SolutionTemplate>('/templates', payload)
    return data
  },
  async update(id: number, payload: SolutionTemplateUpdate) {
    const { data } = await api.patch<SolutionTemplate>(`/templates/${id}`, payload)
    return data
  },
  async delete(id: number) {
    const { data } = await api.delete<{ ok: boolean }>(`/templates/${id}`)
    return data
  },
}
