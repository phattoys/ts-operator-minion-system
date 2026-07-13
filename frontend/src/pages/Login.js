import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Lock, AlertCircle } from 'lucide-react';

export default function Login() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(password);
    
    if (result.success) {
      navigate('/');
    } else {
      setError(result.error);
    }
    
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Logo/Title */}
        <div className="text-center mb-12">
          <h1 
            className="font-['Outfit'] text-4xl font-light tracking-tight text-white mb-2"
            data-testid="login-title"
          >
            TS Operator
          </h1>
          <p className="text-zinc-500 text-sm tracking-[0.2em] uppercase">
            Page Ops Minion v1
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-xs tracking-[0.2em] uppercase text-zinc-500 mb-2">
              Founder Access
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full bg-transparent border border-zinc-800 text-white pl-10 pr-4 py-3 text-sm focus:border-zinc-500 focus:outline-none transition-colors duration-150"
                data-testid="login-password-input"
                autoFocus
              />
            </div>
          </div>

          {error && (
            <div 
              className="flex items-center gap-2 text-[#FF3B30] text-sm p-3 border border-[#FF3B30]/30 bg-[#FF3B30]/10"
              data-testid="login-error"
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full bg-white text-black py-3 text-sm font-medium hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150"
            data-testid="login-submit-btn"
          >
            {loading ? 'Authenticating...' : 'Enter Ops Center'}
          </button>
        </form>

        <p className="text-center text-zinc-600 text-xs mt-8">
          Internal founder-side operations system
        </p>
      </div>
    </div>
  );
}
