export type ThemeId = 'bakery-v1' | 'minimal-v1';

export type PortfolioTheme = {
  id: ThemeId;
  tokens: {
    background: string;
    foreground: string;
    primary: string;
    secondary: string;
    accent: string;
    surface: string;
    borderWidth: string;
    radius: string;
    shadow: string;
    motionScale: string;
  };
};

export const themes: Record<ThemeId, PortfolioTheme> = {
  'bakery-v1': {
    id: 'bakery-v1',
    tokens: {
      background: '#0a0a0f',
      foreground: '#ffffff',
      primary: '#4169E1',
      secondary: '#8B5CF6',
      accent: '#FFD93D',
      surface: '#15151d',
      borderWidth: '3px',
      radius: '24px',
      shadow: '4px 4px 0 #111111',
      motionScale: '1',
    },
  },
  'minimal-v1': {
    id: 'minimal-v1',
    tokens: {
      background: '#f7f7f5',
      foreground: '#111111',
      primary: '#111111',
      secondary: '#555555',
      accent: '#e7e7e2',
      surface: '#ffffff',
      borderWidth: '1px',
      radius: '12px',
      shadow: '0 12px 36px rgba(0,0,0,.08)',
      motionScale: '.6',
    },
  },
};
