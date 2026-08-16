import React, { useState } from 'react';
import { useAuth } from './AuthContext';

export const LoginPage: React.FC<{ onSwitchToRegister: () => void }> = ({ onSwitchToRegister }) => {
  const { login, isLoading, error, clearError } = useAuth();
  const [email, setEmail] = useState('admin@acme.com');
  const [password, setPassword] = useState('AdminPass123!');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    try {
      await login(email, password);
    } catch {
      // Error handled in AuthContext
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      color: '#f8fafc',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      <div style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '420px',
        padding: '2.5rem',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ fontSize: '2.2rem', marginBottom: '0.5rem' }}>⚡</div>
          <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700, color: '#38bdf8' }}>BugPilot</h1>
          <p style={{ margin: '0.4rem 0 0', fontSize: '0.875rem', color: '#94a3b8' }}>
            AI-Powered Engineering Bug Intelligence
          </p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            borderRadius: '6px',
            padding: '0.75rem 1rem',
            marginBottom: '1.25rem',
            fontSize: '0.85rem',
            color: '#fca5a5',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span>{error}</span>
            <button onClick={clearError} style={{ background: 'none', border: 'none', color: '#fca5a5', cursor: 'pointer' }}>✕</button>
          </div>
        )}

        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Select Demo Role:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem' }}>
            <button
              type="button"
              onClick={() => { setEmail('admin@acme.com'); setPassword('AdminPass123!'); }}
              style={{
                padding: '0.5rem 0.75rem',
                background: email === 'admin@acme.com' ? 'rgba(56,189,248,0.2)' : '#0f172a',
                border: email === 'admin@acme.com' ? '1px solid #38bdf8' : '1px solid #334155',
                color: email === 'admin@acme.com' ? '#38bdf8' : '#cbd5e1',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#38bdf8', color: '#0f172a', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.65rem' }}>AA</span>
              ADMIN
            </button>
            <button
              type="button"
              onClick={() => { setEmail('manager@acme.com'); setPassword('ManagerPass123!'); }}
              style={{
                padding: '0.5rem 0.75rem',
                background: email === 'manager@acme.com' ? 'rgba(56,189,248,0.2)' : '#0f172a',
                border: email === 'manager@acme.com' ? '1px solid #38bdf8' : '1px solid #334155',
                color: email === 'manager@acme.com' ? '#38bdf8' : '#cbd5e1',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#10b981', color: '#0f172a', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.65rem' }}>AM</span>
              MANAGER
            </button>
            <button
              type="button"
              onClick={() => { setEmail('developer@acme.com'); setPassword('DeveloperPass123!'); }}
              style={{
                padding: '0.5rem 0.75rem',
                background: email === 'developer@acme.com' ? 'rgba(56,189,248,0.2)' : '#0f172a',
                border: email === 'developer@acme.com' ? '1px solid #38bdf8' : '1px solid #334155',
                color: email === 'developer@acme.com' ? '#38bdf8' : '#cbd5e1',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#8b5cf6', color: '#ffffff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.65rem' }}>AD</span>
              DEVELOPER
            </button>
            <button
              type="button"
              onClick={() => { setEmail('viewer@acme.com'); setPassword('ViewerPass123!'); }}
              style={{
                padding: '0.5rem 0.75rem',
                background: email === 'viewer@acme.com' ? 'rgba(56,189,248,0.2)' : '#0f172a',
                border: email === 'viewer@acme.com' ? '1px solid #38bdf8' : '1px solid #334155',
                color: email === 'viewer@acme.com' ? '#38bdf8' : '#cbd5e1',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#64748b', color: '#ffffff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.65rem' }}>AV</span>
              VIEWER
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '0.4rem' }}>
              Work Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@acme.com"
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '0.4rem' }}>
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              marginTop: '0.5rem',
              padding: '0.75rem',
              background: '#38bdf8',
              color: '#0f172a',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: isLoading ? 'wait' : 'pointer',
              opacity: isLoading ? 0.7 : 1,
              transition: 'all 0.2s',
            }}
          >
            {isLoading ? 'Signing in...' : 'Sign In to Dashboard'}
          </button>
        </form>

        <div style={{
          marginTop: '1.5rem',
          paddingTop: '1.25rem',
          borderTop: '1px solid #334155',
          textAlign: 'center',
          fontSize: '0.85rem',
          color: '#94a3b8',
        }}>
          Don't have an account?{' '}
          <button
            onClick={onSwitchToRegister}
            style={{
              background: 'none',
              border: 'none',
              color: '#38bdf8',
              fontWeight: 600,
              cursor: 'pointer',
              textDecoration: 'underline',
            }}
          >
            Register new user
          </button>
        </div>
      </div>
    </div>
  );
};

export const RegisterPage: React.FC<{ onSwitchToLogin: () => void }> = ({ onSwitchToLogin }) => {
  const { register, isLoading, error, clearError } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgId, setOrgId] = useState('org-acme');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !email || !password) return;
    try {
      await register(email, password, fullName, orgId);
    } catch {
      // Error handled in AuthContext
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      color: '#f8fafc',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      <div style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '440px',
        padding: '2.5rem',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.4rem' }}>🚀</div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, color: '#38bdf8' }}>Create BugPilot Account</h1>
          <p style={{ margin: '0.3rem 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
            Register access for your engineering organization
          </p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            borderRadius: '6px',
            padding: '0.75rem 1rem',
            marginBottom: '1.25rem',
            fontSize: '0.85rem',
            color: '#fca5a5',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span>{error}</span>
            <button onClick={clearError} style={{ background: 'none', border: 'none', color: '#fca5a5', cursor: 'pointer' }}>✕</button>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '0.35rem' }}>
              Full Name
            </label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Doe"
              style={{
                width: '100%',
                padding: '0.7rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '0.35rem' }}>
              Work Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@acme.com"
              style={{
                width: '100%',
                padding: '0.7rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '0.35rem' }}>
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: '100%',
                padding: '0.7rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: '0.35rem' }}>
              Organization Tenant ID
            </label>
            <input
              type="text"
              required
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="org-acme"
              style={{
                width: '100%',
                padding: '0.7rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              marginTop: '0.5rem',
              padding: '0.75rem',
              background: '#10b981',
              color: '#0f172a',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: isLoading ? 'wait' : 'pointer',
              opacity: isLoading ? 0.7 : 1,
              transition: 'all 0.2s',
            }}
          >
            {isLoading ? 'Registering...' : 'Register & Log In'}
          </button>
        </form>

        <div style={{
          marginTop: '1.5rem',
          paddingTop: '1.25rem',
          borderTop: '1px solid #334155',
          textAlign: 'center',
          fontSize: '0.85rem',
          color: '#94a3b8',
        }}>
          Already have an account?{' '}
          <button
            onClick={onSwitchToLogin}
            style={{
              background: 'none',
              border: 'none',
              color: '#38bdf8',
              fontWeight: 600,
              cursor: 'pointer',
              textDecoration: 'underline',
            }}
          >
            Sign In instead
          </button>
        </div>
      </div>
    </div>
  );
};
