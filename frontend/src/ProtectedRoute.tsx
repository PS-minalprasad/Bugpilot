import React, { useState, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { LoginPage, RegisterPage } from './AuthPages';

export const ProtectedRoute: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');

  if (isLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0f172a',
        color: '#38bdf8',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid rgba(56, 189, 248, 0.2)',
          borderTopColor: '#38bdf8',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
          marginBottom: '1rem',
        }} />
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#94a3b8' }}>
          Authenticating BugPilot Session...
        </span>
      </div>
    );
  }

  if (!isAuthenticated) {
    if (authMode === 'register') {
      return <RegisterPage onSwitchToLogin={() => setAuthMode('login')} />;
    }
    return <LoginPage onSwitchToRegister={() => setAuthMode('register')} />;
  }

  return <>{children}</>;
};
