import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button, Input } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'

type Tab = 'login' | 'register'
type Step = 'email' | 'code'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const RESEND_COOLDOWN = 60

/**
 * melontik login ekranı: "Giriş Yap / Kayıt Ol" sekmeleri, şifresiz email-OTP akışı.
 * Davranış sözleşmesi: hive/agents/phyllis-mttzizd9/w2a-interaction-spec.md §1.
 * "Demo Hesabı İncele" BİLİNÇLİ OLARAK YOK — spec Wave2a kapsamı dışında tutuyor (backend'de demo-mode yok).
 */
export default function Login() {
  const [tab, setTab] = useState<Tab>('login')
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [debugCode, setDebugCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)

  const { isAuthenticated, requestPin, verifyPin } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'

  const cooldownTimer = useRef<number | null>(null)
  useEffect(() => {
    if (cooldown <= 0) return
    cooldownTimer.current = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => {
      if (cooldownTimer.current) window.clearTimeout(cooldownTimer.current)
    }
  }, [cooldown])

  async function sendPin(targetEmail: string) {
    setError(null)
    setLoading(true)
    try {
      const res = await requestPin(targetEmail)
      setDebugCode(res.debug_code ?? null)
      setStep('code')
      setCooldown(RESEND_COOLDOWN)
      toast({ type: 'success', message: `Kodu ${targetEmail}'e gönderdik.` })
    } catch {
      setError('Kod gönderilemedi, tekrar deneyin.')
    } finally {
      setLoading(false)
    }
  }

  function handleRequestPin(e: FormEvent) {
    e.preventDefault()
    if (!EMAIL_RE.test(email)) {
      setEmailError('Geçerli bir e-posta adresi girin.')
      return
    }
    setEmailError(null)
    sendPin(email)
  }

  async function handleVerifyPin(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      // Dönen diziyi kullan — ctx.stores state güncellemesi bu render'da henüz commit
      // edilmemiş olabilir (stale closure), stores.length burada her zaman eski değeri okur.
      const freshStores = await verifyPin(email, code)
      navigate(freshStores.length === 0 ? '/settings' : from, { replace: true })
    } catch {
      setError('Kod hatalı veya süresi dolmuş.')
      setCode('')
    } finally {
      setLoading(false)
    }
  }

  if (isAuthenticated) return <Navigate to={from} replace />

  return (
    <div className="flex min-h-screen items-center justify-center bg-app-bg px-4">
      <div className="w-full max-w-md rounded-lg border border-app-border bg-app-surface p-8 shadow-elevated">
        <div className="mb-6 flex items-center justify-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-brand text-lg font-bold text-white">%</span>
          <span className="text-lg font-semibold text-text-primary">melontik</span>
        </div>

        <div className="mb-6 flex rounded-md border border-app-border p-1">
          <button
            type="button"
            onClick={() => {
              setTab('login')
              setStep('email')
              setError(null)
            }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              tab === 'login' ? 'bg-brand text-white' : 'text-text-secondary hover:bg-app-surface-muted'
            }`}
          >
            Giriş Yap
          </button>
          <button
            type="button"
            onClick={() => {
              setTab('register')
              setStep('email')
              setError(null)
            }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              tab === 'register' ? 'bg-brand text-white' : 'text-text-secondary hover:bg-app-surface-muted'
            }`}
          >
            Kayıt Ol
          </button>
        </div>

        {step === 'email' ? (
          <form onSubmit={handleRequestPin} className="flex flex-col gap-4">
            <Input
              label="Eposta"
              type="email"
              required
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (emailError) setEmailError(null)
              }}
              error={emailError ?? undefined}
              placeholder="ornek@magaza.com"
              autoFocus
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button type="submit" disabled={loading || !email}>
              {loading ? 'Gönderiliyor…' : 'Pin Kodu Al'}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleVerifyPin} className="flex flex-col gap-4">
            <p className="text-sm text-text-secondary">
              Kodu <strong className="text-text-primary">{email}</strong>'e gönderdik.
            </p>
            {debugCode && (
              <p className="rounded-md bg-warning-soft px-3 py-2 text-xs text-warning">
                DEV modu: kod <strong className="tabular-nums">{debugCode}</strong> (gerçek email servisi henüz yok)
              </p>
            )}
            <Input
              label="Kod"
              inputMode="numeric"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              autoFocus
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button type="submit" disabled={loading || code.length !== 6}>
              {loading ? 'Doğrulanıyor…' : 'Giriş Yap'}
            </Button>
            <div className="flex items-center justify-between text-xs">
              <button
                type="button"
                onClick={() => {
                  setStep('email')
                  setCode('')
                  setError(null)
                }}
                className="text-text-secondary hover:text-text-primary"
              >
                Farklı e-posta
              </button>
              <button
                type="button"
                disabled={cooldown > 0 || loading}
                onClick={() => sendPin(email)}
                className="text-text-secondary hover:text-text-primary disabled:opacity-50"
              >
                {cooldown > 0 ? `Tekrar gönder (${cooldown}sn)` : 'Tekrar gönder'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
