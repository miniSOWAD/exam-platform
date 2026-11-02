import type { Config } from 'tailwindcss';
const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17243B',
        brand: '#365BD7',
        mint: '#E8F7F4',
        teal: '#5C929D',
        paper: '#FBFAF7',
      },
      boxShadow: { soft: '0 12px 36px rgba(29,55,70,.06)' },
      fontFamily: { editorial: ['Georgia', 'Times New Roman', 'serif'] },
    },
  },
  plugins: [],
};
export default config;
