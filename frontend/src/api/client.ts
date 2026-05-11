import axios from 'axios'

let accessToken = ''

export const setAccessToken = (token: string) => {
  accessToken = token
}

export const getAccessToken = () => accessToken

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api'
})

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})
