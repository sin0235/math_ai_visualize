import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { installGlobalErrorReporting } from './utils/telemetry';

installGlobalErrorReporting();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
