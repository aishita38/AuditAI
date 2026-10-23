import React, { createContext, useContext, useEffect, useState } from 'react';
import { authApi } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener('auditai:unauthorized', onUnauthorized);
    if (sessionStorage.getItem(authApi.tokenKey)) {
      authApi.me().then(response => setUser(response.data)).catch(() => setUser(null)).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    return () => window.removeEventListener('auditai:unauthorized', onUnauthorized);
  }, []);

  const login = async (email, password) => {
    const response = await authApi.login(email, password);
    sessionStorage.setItem(authApi.tokenKey, response.data.access_token);
    setUser(response.data.user);
    return response.data.user;
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* A stale session is already signed out. */ }
    sessionStorage.removeItem(authApi.tokenKey);
    setUser(null);
  };

  const developerLogin = async (challenge, otp) => {
    const response=await authApi.devVerify(challenge,otp);
    sessionStorage.setItem(authApi.tokenKey,response.data.access_token);
    setUser(response.data.user);
    return response.data.user;
  };

  return <AuthContext.Provider value={{ user, loading, login, developerLogin, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth requires AuthProvider');
  return context;
}

export function isReviewer(user) {
  return Boolean(user?.roles?.some(role => role === 'maker' || role === 'checker' || role === 'admin'));
}
