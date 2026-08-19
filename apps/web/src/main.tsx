import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './ui/App';
import { ThemeProvider } from './design-system/ThemeProvider';
import { FetchSseConversationClient } from './adapters/fetchSseConversationClient';
import { BrowserSpeechRecognitionAdapter, BrowserSpeechSynthesisAdapter } from './adapters/browserSpeech';
import { HandsFreeController } from './application/HandsFreeController';
import './styles.css';

const conversationId = globalThis.crypto?.randomUUID?.() ?? `portfolio-${Date.now()}`;
const controller = new HandsFreeController(
  conversationId,
  new FetchSseConversationClient(),
  new BrowserSpeechRecognitionAdapter(),
  new BrowserSpeechSynthesisAdapter(),
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme="bakery-v1">
      <App controller={controller} />
    </ThemeProvider>
  </React.StrictMode>,
);
