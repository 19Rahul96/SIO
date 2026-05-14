/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#f4f6fa',
        bg2:      '#eef1f7',
        bg3:      '#ffffff',
        bg4:      '#f0f2f8',
        card:     '#ffffff',
        card2:    '#ffffff',
        dborder:  '#dde2ee',
        dborder2: '#c8d0e3',
        t1:       '#1a1d2e',
        t2:       '#5a6280',
        t3:       '#8e97b8',
        accent:   '#4f46e5',
        accent2:  '#6366f1',
        teal:     '#0d9488',
        gg:       '#16a34a',
        amber:    '#d97706',
        coral:    '#e11d48',
        purple:   '#7c3aed',
        blue:     '#2563eb',
      },
      fontFamily: {
        sora: ['Sora', 'Inter', 'sans-serif'],
        dm:   ['DM Sans', 'Inter', 'sans-serif'],
      },
      borderRadius: {
        card: '14px',
        sm:   '9px',
      },
    },
  },
  plugins: [],
}
