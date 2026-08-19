import { describe, expect, it } from 'vitest';
import { themes } from './themes';

const VISUAL_TOKEN_KEYS = [
  'background', 'foreground', 'primary', 'secondary', 'accent', 'surface',
  'borderWidth', 'radius', 'shadow', 'motionScale',
].sort();

describe('theme authority boundary', () => {
  it('exposes visual tokens only', () => {
    for (const theme of Object.values(themes)) {
      expect(Object.keys(theme.tokens).sort()).toEqual(VISUAL_TOKEN_KEYS);
      expect(JSON.stringify(theme).toLowerCase()).not.toMatch(/packid|retrieval|evidenceid|authority|endpoint/);
    }
  });
});
