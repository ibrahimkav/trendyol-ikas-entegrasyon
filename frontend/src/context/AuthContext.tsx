import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  clearToken,
  fetchMe,
  isAuthenticated as checkIsAuthenticated,
  requestPin as requestPinApi,
  verifyPin as verifyPinApi,
  type AuthStore,
  type AuthUser,
} from '../lib/auth'

type AuthContextValue = {
  isAuthenticated: boolean
  user: AuthUser | null
  stores: AuthStore[]
  loading: boolean
  requestPin: (email: string) => Promise<{ debug_code?: string }>
  /** Dönen stores dizisini KULLAN, ctx.stores'u değil — state güncellemesi henüz commit edilmemiş
      olabilir (React state async), çağıran taraf stale/eski değeri okuyabilir. */
  verifyPin: (email: string, code: string) => Promise<AuthStore[]>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(checkIsAuthenticated())
  const [user, setUser] = useState<AuthUser | null>(null)
  const [stores, setStores] = useState<AuthStore[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function bootstrap() {
      if (!checkIsAuthenticated()) {
        if (!cancelled) setLoading(false)
        return
      }
      try {
        const me = await fetchMe()
        if (!cancelled) {
          setUser({ id: me.id, email: me.email })
          setStores(me.stores ?? [])
          setAuthed(true)
        }
      } catch {
        if (!cancelled) {
          clearToken()
          setAuthed(false)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const onUnauthorized = () => {
      setAuthed(false)
      setUser(null)
      setStores([])
    }
    window.addEventListener('auth:unauthorized', onUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized)
  }, [])

  const requestPin = useCallback((email: string) => requestPinApi(email), [])

  const verifyPin = useCallback(async (email: string, code: string) => {
    const data = await verifyPinApi(email, code)
    const stores = data.stores ?? []
    setUser(data.user)
    setStores(stores)
    setAuthed(true)
    return stores
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setAuthed(false)
    setUser(null)
    setStores([])
  }, [])

  const value = useMemo(
    () => ({ isAuthenticated: authed, user, stores, loading, requestPin, verifyPin, logout }),
    [authed, user, stores, loading, requestPin, verifyPin, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
