import { useEffect, useState } from 'react'

/** Değeri `delayMs` boyunca değişmeden kalınca günceller — metin filtrelerinde debounce için. */
export function useDebouncedValue<T>(value: T, delayMs = 400): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
