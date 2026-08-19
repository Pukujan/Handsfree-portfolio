// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeProvider';

function Probe() {
  const theme = useTheme();
  return <div data-testid="theme-probe">{theme}</div>;
}

describe('ThemeProvider authority boundary', () => {
  it('changes only presentation tokens/context', () => {
    const { rerender } = render(
      <ThemeProvider theme="bakery-v1"><Probe /></ThemeProvider>,
    );
    expect(screen.getByTestId('theme-probe').textContent).toBe('bakery-v1');
    const before = document.documentElement.style.getPropertyValue('--background');

    rerender(<ThemeProvider theme="minimal-v1"><Probe /></ThemeProvider>);
    expect(screen.getByTestId('theme-probe').textContent).toBe('minimal-v1');
    const after = document.documentElement.style.getPropertyValue('--background');

    expect(document.documentElement.dataset.theme).toBe('minimal-v1');
    expect(before).not.toBe(after);
  });
});
