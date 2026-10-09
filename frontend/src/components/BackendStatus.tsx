import { useEffect, useState } from 'react'
import apiClient from '../config/api'

/** Vite proxy: GET /api/health → backend (main.py api_health_check). */
export default function BackendStatus() {
  const [ok, setOk] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false
    const ping = () => {
      apiClient
        .get<{ status?: string }>('health')
        .then((res) => {
          if (!cancelled) setOk(res.data?.status === 'healthy')
        })
        .catch(() => {
          if (!cancelled) setOk(false)
        })
    }
    ping()
    const id = window.setInterval(ping, 30000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  if (ok === null) {
    return (
      <span className="hidden text-[11px] text-slate-400 lg:inline" aria-hidden>
        API…
      </span>
    )
  }

  return (
    <span
      className={`hidden items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium lg:inline-flex ${
        ok ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'
      }`}
      title={ok ? 'Backend erişilebilir' : 'Backend yanıt vermiyor (uvicorn :8000?)'}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`} aria-hidden />
      {ok ? 'API' : 'API kapalı'}
    </span>
  )
}
