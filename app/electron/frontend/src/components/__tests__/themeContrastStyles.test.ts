import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('theme contrast style guards', () => {
  it('keeps centralized semantic utility guards for legacy classes and filled badges', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8');

    expect(css).toContain('.text-lawn-muted');
    expect(css).toContain('.text-lawn-muted-strong');
    expect(css).toContain('.bg-lawn-soft');
    expect(css).toContain('.border-lawn-soft');

    expect(css).toContain('[data-theme="dark"] .text-lawn-bg');
    expect(css).toContain('[data-theme="cyber"] .text-lawn-bg');
    expect(css).toContain('[data-theme="dracula"] .text-lawn-bg');

    expect(css).toContain('.text-stone-500');
    expect(css).toContain('.bg-stone-100');
    expect(css).toContain('.border-stone-300');

    expect(css).toContain('.bg-lawn-accent.text-lawn-bg');
    expect(css).toContain('.bg-lawn-accent.text-lawn-border');
    expect(css).toContain('.bg-lawn-dark.text-lawn-bg');
    expect(css).toContain('.bg-theme-success.text-lawn-bg');
    expect(css).toContain('.bg-theme-warning.text-lawn-bg');
    expect(css).toContain('.bg-theme-error.text-lawn-bg');
    expect(css).toContain('.bg-theme-info.text-lawn-bg');
    expect(css).toContain('.hover\\:bg-lawn-accent.hover\\:text-lawn-border:hover');
  });

  it('keeps per-theme semantic contrast tokens', () => {
    const themeTokens = readFileSync(resolve(process.cwd(), '../shared/theme-tokens.css'), 'utf-8');

    expect(themeTokens).toContain('--color-muted:');
    expect(themeTokens).toContain('--color-muted-strong:');
    expect(themeTokens).toContain('--color-on-solid:');
    expect(themeTokens).toContain('--color-soft-bg:');
    expect(themeTokens).toContain('--color-soft-border:');

    expect(themeTokens).toContain('[data-theme="ocean"]');
    expect(themeTokens).toContain('[data-theme="sunset"]');
    expect(themeTokens).toContain('[data-theme="forest"]');
  });
});
