import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './ui/App';
import { ThemeProvider } from './design-system/ThemeProvider';
import { fakeConversationClient } from './adapters/fakeConversationClient';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme="bakery-v1">
      <App conversation={fakeConversationClient} />
    </ThemeProvider>
  </React.StrictMode>,
);
