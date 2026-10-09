/**
 * ESLint config — Vite + React + TypeScript (Oscar, w2c).
 * Wave1'den beri eksikti; 'npm run lint' bu dosyayla çalışır hale geldi.
 *
 * Yaklaşım (god w2c #3: "kritik hataları düzelt, uyarıları makul eşikte bırak"):
 * - Gerçek hata sınıfları AÇIK (rules-of-hooks, no-undef→TS, kullanılmayan değişken, vb.).
 * - Büyük legacy kod tabanını (~30 trendyol bileşeni) gürültüye boğan ama korelasyonu
 *   düşük stil kuralları kapatıldı/yumuşatıldı (no-explicit-any, react-refresh export kuralı),
 *   yoksa --max-warnings 0 ile hiç geçmez ve lint pratikte kullanılamaz olurdu.
 */
module.exports = {
  root: true,
  env: { browser: true, es2020: true, node: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', '.eslintrc.cjs', 'vite.config.ts', 'tailwind.config.js', 'postcss.config.js'],
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  plugins: ['@typescript-eslint', 'react-refresh'],
  rules: {
    // Kullanılmayan değişken = hata; _ önekli olanlar bilinçli yok sayılır.
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    // Legacy kod any'yi yoğun kullanıyor; correctness bug'ı değil, gürültü → kapalı.
    '@typescript-eslint/no-explicit-any': 'off',
    // Context dosyaları bilinçli olarak hook + provider export ediyor → kapalı.
    'react-refresh/only-export-components': 'off',
    // Bilinçli boş catch bloklarına izin (fallback/log-yut desenleri).
    'no-empty': ['error', { allowEmptyCatch: true }],
    // @ts-expect-error yerine @ts-ignore kullanımına legacy'de izin.
    '@typescript-eslint/ban-ts-comment': 'off',
  },
}
