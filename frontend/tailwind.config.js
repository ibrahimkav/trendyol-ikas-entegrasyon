/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Poppins', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // mevcut trendyol.* korunur (geriye dönük uyumluluk / marka rozetleri için)
        trendyol: {
          primary: '#F27A1A',
          secondary: '#FF6000',
          dark: '#1A1A1A',
          light: '#FFF4ED',
        },
        // melontik-benzeri sistem (kaynak: hive/agents/ryan-mttzjxj7/design-system.md, doğrulandı hive/research/melontik-screens.md)
        app: {
          bg: '#F9F9F9',
          surface: '#FFFFFF',
          'surface-muted': '#F3F4F6',
          border: '#E7E7EA',
        },
        text: {
          primary: '#1A1D23',
          secondary: '#6B7280',
          muted: '#9CA3AF',
        },
        brand: {
          DEFAULT: '#FF6B4A',
          hover: '#E85A3B',
          soft: '#FFE9E2',
        },
        secondary: {
          DEFAULT: '#7A2E1E',
          hover: '#5F2216',
        },
        success: { DEFAULT: '#16A34A', soft: '#DCFCE7' },
        danger: { DEFAULT: '#DC2626', soft: '#FEE2E2' },
        warning: { DEFAULT: '#D97706', soft: '#FEF3C7' },
        info: { DEFAULT: '#2563EB', soft: '#DBEAFE' },
        chart: {
          1: '#FF6B4A', 2: '#16A34A', 3: '#F59E0B',
          4: '#2563EB', 5: '#7A2E1E', 6: '#06B6D4', 7: '#A855F7',
        },
      },
      borderRadius: {
        sm: '8px', md: '12px', lg: '16px', xl: '20px',
      },
      fontSize: {
        caption: ['12px', { lineHeight: '16px', fontWeight: '500' }],
        'kpi-value': ['28px', { lineHeight: '32px', fontWeight: '700' }],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
        'glow': '0 0 20px rgba(242, 122, 26, 0.3)',
        card: '0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)',
        elevated: '0 8px 24px rgba(16,24,40,.12)',
      },
    },
  },
  plugins: [],
}



