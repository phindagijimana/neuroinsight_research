/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50:  '#f0f5fa',
          100: '#d6e4f0',
          200: '#adc9e1',
          300: '#84aed2',
          400: '#5b93c3',
          500: '#1a6ba0',
          600: '#003d7a',   // PRIMARY brand color
          700: '#003265',
          800: '#002750',
          900: '#001c3b',
          950: '#001228',
        },
      },
    },
  },
  plugins: [],
}
