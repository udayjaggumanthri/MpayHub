import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AppearanceProvider } from './context/AppearanceContext';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { WalletProvider } from './context/WalletContext';
import AppRoutes from './routes/AppRoutes';

function App() {
  return (
    <BrowserRouter>
      <AppearanceProvider>
        <ThemeProvider>
          <AuthProvider>
            <WalletProvider>
              <AppRoutes />
            </WalletProvider>
          </AuthProvider>
        </ThemeProvider>
      </AppearanceProvider>
    </BrowserRouter>
  );
}

export default App;
