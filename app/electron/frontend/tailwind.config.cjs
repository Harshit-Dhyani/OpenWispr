/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        screens: {
            'sm': '640px',
            'md': '900px',
            'lg': '1024px',
            'xl': '1400px',
            '2xl': '1536px',
        },
        extend: {
            colors: {
                lawn: {
                    bg: 'var(--color-bg)',
                    panel: 'var(--color-panel)',
                    dark: 'var(--color-dark)',
                    accent: 'var(--color-accent)',
                    border: 'var(--color-border)',
                },
                theme: {
                    success: 'var(--color-success)',
                    warning: 'var(--color-warning)',
                    error: 'var(--color-error)',
                    info: 'var(--color-info)',
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', "Liberation Mono", "Courier New", 'monospace'],
                display: ['"Arial Black"', 'Impact', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            boxShadow: {
                'brutal': '2px 2px 0px 0px var(--color-border)',
                'brutal-sm': '1px 1px 0px 0px var(--color-border)',
                'brutal-lg': '4px 4px 0px 0px var(--color-border)',
            }
        },
    },
    plugins: [],
}
