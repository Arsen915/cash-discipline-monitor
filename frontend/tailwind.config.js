/** @type {import('tailwindcss').Config} */

// Дизайн-система Fintruism: нейтральная «графитовая» шкала, сдержанный фирменный зелёный
// и приглушённые семантические цвета. Компоненты используют только эти шкалы.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Нейтральные: фон, текст, границы
        ink: {
          50: '#F6F7F6',
          100: '#EEF0EF',
          200: '#E2E5E3',
          300: '#CBD0CD',
          400: '#9CA39F',
          500: '#727A76',
          600: '#555D59',
          700: '#3B423F',
          800: '#262C29',
          900: '#171C1A',
          950: '#0E1211',
        },
        // Фирменный зелёный Fintruism
        brand: {
          50: '#EEF6F1',
          100: '#D7EBDF',
          200: '#B0D7C0',
          300: '#7FBE99',
          400: '#45A16D',
          500: '#1F8A52',
          600: '#147545',
          700: '#0F6039',
          800: '#0C4C2E',
          900: '#093822',
        },
        success: {
          50: '#EEF6F1',
          100: '#D7EBDF',
          200: '#B0D7C0',
          500: '#1F8A52',
          600: '#147545',
          700: '#0F6039',
        },
        warning: {
          50: '#FBF6EA',
          100: '#F5E9C8',
          200: '#EBD49A',
          300: '#DDB95F',
          500: '#C08A1E',
          600: '#A06F12',
          700: '#7E560E',
          800: '#5F410C',
          900: '#45300A',
          950: '#2E2006',
        },
        danger: {
          50: '#FBEFEE',
          100: '#F5D9D6',
          200: '#EBB7B2',
          500: '#C8423A',
          600: '#B0352E',
          700: '#8F2A25',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', '-apple-system', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Mono', 'Consolas', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Шкала типографики: подписи → основной текст → заголовки
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        // Единые радиусы: контролы 6px, карточки 10px
        control: '6px',
        panel: '10px',
      },
      boxShadow: {
        panel: '0 1px 2px rgba(14, 18, 17, 0.04)',
        overlay: '0 12px 32px rgba(14, 18, 17, 0.18)',
      },
      maxWidth: {
        content: '72rem',
      },
      keyframes: {
        'stripe-move': { from: { backgroundPosition: '0 0' }, to: { backgroundPosition: '40px 0' } },
      },
      animation: {
        stripes: 'stripe-move 1s linear infinite',
      },
    },
  },
  plugins: [],
};
