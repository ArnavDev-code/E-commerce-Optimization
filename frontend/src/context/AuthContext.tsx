import React, { createContext, useContext, useState, useEffect } from 'react';
import { Merchant, AuthResponse } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  merchant: Merchant | null;
  token: string | null;
  isAuthenticated: boolean;
  isDemo: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginDemo: () => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('funnelleak_token'));
  const [merchant, setMerchant] = useState<Merchant | null>(() => {
    const cached = localStorage.getItem('funnelleak_merchant');
    return cached ? JSON.parse(cached) : null;
  });

  useEffect(() => {
    if (token && !merchant) {
      api.get<Merchant>('/auth/me')
        .then((data) => {
          setMerchant(data);
          localStorage.setItem('funnelleak_merchant', JSON.stringify(data));
        })
        .catch(() => logout());
    }
  }, [token]);

  const handleAuthSuccess = (data: AuthResponse) => {
    setToken(data.access_token);
    setMerchant(data.merchant);
    localStorage.setItem('funnelleak_token', data.access_token);
    localStorage.setItem('funnelleak_merchant', JSON.stringify(data.merchant));
  };

  const login = async (email: string, password: string) => {
    const data = await api.post<AuthResponse>('/auth/login', { email, password });
    handleAuthSuccess(data);
  };

  const loginDemo = async () => {
    const data = await api.post<AuthResponse>('/auth/demo');
    handleAuthSuccess(data);
  };

  const register = async (email: string, password: string, name?: string) => {
    const data = await api.post<AuthResponse>('/auth/register', { email, password, name });
    handleAuthSuccess(data);
  };

  const logout = () => {
    setToken(null);
    setMerchant(null);
    localStorage.removeItem('funnelleak_token');
    localStorage.removeItem('funnelleak_merchant');
  };

  return (
    <AuthContext.Provider
      value={{
        merchant,
        token,
        isAuthenticated: !!token && !!merchant,
        isDemo: merchant?.is_demo ?? false,
        login,
        loginDemo,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
