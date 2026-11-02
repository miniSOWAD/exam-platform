import type { Config } from 'tailwindcss';
const config: Config = { content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'], theme: { extend: { colors: { ink: '#10213A', brand: '#3157D5', mint: '#DDF7EC' }, boxShadow: { soft: '0 12px 40px rgba(16,33,58,.08)' } } }, plugins: [] };
export default config;
