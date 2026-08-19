import { createContext, useContext, useEffect, type PropsWithChildren } from 'react';
import { themes, type ThemeId } from './themes';

const ThemeContext = createContext<ThemeId>('bakery-v1');

export function ThemeProvider({ theme, children }: PropsWithChildren<{ theme: ThemeId }>) {
  const selected = themes[theme];

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = selected.id;
    for (const [key, value] of Object.entries(selected.tokens)) {
      root.style.setProperty(`--${key}`, value);
    }
  }, [selected]);

  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
