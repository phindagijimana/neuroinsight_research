import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { FeatureFlagsProvider } from './contexts/FeatureFlagsContext';
import { NotificationProvider } from './contexts/NotificationContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <NotificationProvider>
        <FeatureFlagsProvider>
          <App />
        </FeatureFlagsProvider>
      </NotificationProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
