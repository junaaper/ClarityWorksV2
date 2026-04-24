/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['"Public Sans"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif:   ['"Source Serif 4"', '"Iowan Old Style"', 'Georgia', 'serif'],
        mono:    ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // institutional neutrals (cool)
        ink: {
          0:   '#ffffff',
          50:  '#f6faff',
          100: '#eff4fb',
          150: '#e9eef5',
          200: '#dde3ea',
          300: '#c3c6d1',
          400: '#737780',
          500: '#43474f',
          600: '#2f343a',
          700: '#1f242a',
          800: '#161c21',
          900: '#0d1217',
        },
        // primary — institutional blue
        primary: {
          50:  '#dbe3f5',
          100: '#bfd1ef',
          200: '#a3c9ff',
          300: '#6c9edf',
          400: '#4a80c5',
          500: '#28609d',
          600: '#1a4d88',
          700: '#003461',
          800: '#002a51',
          900: '#001f3d',
        },
        // secondary — teal
        secondary: {
          50:  '#eaf5f3',
          100: '#d6eee9',
          200: '#bfebe6',
          300: '#a4cfca',
          500: '#3d6562',
          600: '#315653',
          700: '#244d4a',
          900: '#00201e',
        },
        // amber accent
        amber2: {
          50:  '#fdf2da',
          100: '#fbe4b4',
          300: '#f6c36f',
          500: '#d08a22',
          700: '#8c5f10',
        },
        ok:   { 50: '#e6f4ec', 500: '#2f8a58', 700: '#1d5c3a' },
        warn: { 50: '#fbf0db', 500: '#b87808', 700: '#7c4f02' },
        err:  { 50: '#ffe1dd', 500: '#ba1a1a', 700: '#7a1f15' },
        info: { 50: '#e3eefb', 500: '#28609d', 700: '#003461' },
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        's1': '0 1px 2px rgba(22,28,33,.04)',
        's2': '0 2px 6px rgba(22,28,33,.06), 0 1px 2px rgba(22,28,33,.04)',
        's3': '0 8px 22px rgba(22,28,33,.08), 0 2px 4px rgba(22,28,33,.04)',
        's4': '0 12px 32px rgba(22,28,33,.10)',
      },
      letterSpacing: {
        'tight-1': '-0.005em',
        'tight-2': '-0.01em',
        'tight-3': '-0.015em',
        'tight-4': '-0.02em',
        'overline': '0.14em',
      },
      maxWidth: {
        'canvas': '1180px',
      },
    },
  },
  plugins: [],
}
