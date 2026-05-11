import { defineStore } from 'pinia'
import { api, setAccessToken } from '../api/client'

type UserProfile = {
  id: number
  username: string
  display_name: string
  status: string
  roles: string[]
  permissions: string[]
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: '',
    user: null as UserProfile | null,
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isSuperAdmin: (state) => Boolean(state.user?.roles?.includes('SUPER_ADMIN')),
    can: (state) => (permission: string) =>
      Boolean(state.user?.permissions?.includes('*') || state.user?.permissions?.includes(permission)),
  },
  actions: {
    setToken(token: string) {
      this.token = token
      setAccessToken(token)
    },
    async login(username: string, password: string) {
      const { data } = await api.post('/auth/login', { username, password })
      this.setToken(data.access_token)
      this.user = data.user
      this.initialized = true
    },
    async loadMe() {
      if (!this.token) {
        this.user = null
        this.initialized = true
        return
      }
      try {
        const { data } = await api.get('/auth/me')
        this.user = data
      } catch {
        this.setToken('')
        this.user = null
      } finally {
        this.initialized = true
      }
    },
    logout() {
      this.setToken('')
      this.user = null
      this.initialized = true
    },
  },
})
