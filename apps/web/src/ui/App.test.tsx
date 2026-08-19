import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import type { ConversationStreamClient, ServerConversationState, TurnEvent } from '../application/conversation';
import { HandsFreeController } from '../application/HandsFreeController';
import type { SpeechInputCallbacks, SpeechInputPort, SpeechOutputCallbacks, SpeechOutputPort } from '../application/voice';
import { ThemeProvider } from '../design-system/ThemeProvider';
import { App } from './App';

class UnusedClient implements ConversationStreamClient {
  async *streamTurn(): AsyncIterable<TurnEvent> { return; }
  async getState(): Promise<ServerConversationState> {
    return { contractVersion: '1.0.0', activeGeneration: 0, state: 'idle', activeSubject: null, referents: {} };
  }
}

class UnsupportedInput implements SpeechInputPort {
  isSupported() { return false; }
  start(callbacks: SpeechInputCallbacks) { callbacks.onError('unsupported'); }
  stop() {}
}

class UnsupportedOutput implements SpeechOutputPort {
  isSupported() { return false; }
  speak(_text: string, callbacks: SpeechOutputCallbacks) { callbacks.onError('unsupported'); }
  stop() {}
}

test('renders the portfolio and text fallback without requiring voice', () => {
  const controller = new HandsFreeController(
    'ui-test',
    new UnusedClient(),
    new UnsupportedInput(),
    new UnsupportedOutput(),
  );

  render(
    <ThemeProvider initialTheme="bakery-v1">
      <App controller={controller} />
    </ThemeProvider>,
  );

  expect(screen.getByText(/Pujan Bajracharya · AI Systems Engineer/i)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /Talk to my work/i })).toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: /Ask about Pujan/i })).toBeInTheDocument();
  expect(screen.getByText(/Voice recognition isn’t available/i)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /The portfolio still works without the assistant/i })).toBeInTheDocument();
  expect(screen.getByText('FOSSIL')).toBeInTheDocument();
  expect(screen.getByText('Cortex Ascend')).toBeInTheDocument();
});
