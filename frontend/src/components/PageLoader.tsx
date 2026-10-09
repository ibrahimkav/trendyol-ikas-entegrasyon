export default function PageLoader() {
  return (
    <div
      className="flex min-h-[42vh] flex-col items-center justify-center gap-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div
        className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-trendyol-primary"
        aria-hidden
      />
      <span className="sr-only">Sayfa yükleniyor</span>
    </div>
  )
}
