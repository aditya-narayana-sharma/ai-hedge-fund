import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { CatalogProvider } from './contexts/catalog-context';
import { NodeProvider } from './contexts/node-context';
import { ThemeProvider } from './providers/theme-provider';

import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <CatalogProvider>
        <NodeProvider>
          <App />
        </NodeProvider>
      </CatalogProvider>
    </ThemeProvider>
  </React.StrictMode>
);
