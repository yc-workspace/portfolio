import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import Watchlist from './pages/Watchlist';
import Futures from './pages/Futures';
import Settings from './pages/Settings';
import { api } from './api';
import './App.css';

const IDLE_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

function App() {
  const [serverStatus, setServerStatus] = useState(null);
  const [countdown, setCountdown] = useState(IDLE_TIMEOUT_MS / 1000);
  const lastKeepaliveRef = useRef(Date.now());
  const countdownRef = useRef(null);

  // Reset countdown and send keepalive
  const resetCountdown = useCallback(async () => {
    lastKeepaliveRef.current = Date.now();
    setCountdown(IDLE_TIMEOUT_MS / 1000);
    try { await api.keepalive(); } catch (_) {}
  }, []);

  // Countdown timer
  useEffect(() => {
    countdownRef.current = setInterval(() => {
      const elapsed = (Date.now() - lastKeepaliveRef.current) / 1000;
      const remaining = Math.max(0, IDLE_TIMEOUT_MS / 1000 - elapsed);
      setCountdown(Math.floor(remaining));
    }, 1000);
    return () => clearInterval(countdownRef.current);
  }, []);

  // Check server status on load
  useEffect(() => {
    api.health().then(setServerStatus).catch(() => setServerStatus({ status: 'error' }));
    resetCountdown();
  }, [resetCountdown]);

  const formatCountdown = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <BrowserRouter>
      <div className="app">
        {/* Top Bar */}
        <header className="topbar">
          <span className="topbar-logo">📈 Portfolio</span>
          <div className="topbar-right">
            <div className={`server-dot ${serverStatus?.status === 'ok' ? 'online' : 'offline'}`} 
                 title={serverStatus?.status === 'ok' ? '伺服器運作中' : '伺服器離線'} />
            <button className="keepalive-btn" onClick={resetCountdown} title="點擊保持連線">
              ⏱ {formatCountdown(countdown)}
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/futures" element={<Futures />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>

        {/* Bottom Navigation (mobile-first) */}
        <nav className="bottom-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <span className="nav-icon">🏠</span>
            <span className="nav-label">總覽</span>
          </NavLink>
          <NavLink to="/portfolio" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <span className="nav-icon">💼</span>
            <span className="nav-label">投組</span>
          </NavLink>
          <NavLink to="/watchlist" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <span className="nav-icon">👁</span>
            <span className="nav-label">觀察</span>
          </NavLink>
          <NavLink to="/futures" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <span className="nav-icon">📊</span>
            <span className="nav-label">期貨</span>
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <span className="nav-icon">⚙️</span>
            <span className="nav-label">設定</span>
          </NavLink>
        </nav>
      </div>
    </BrowserRouter>
  );
}

export default App;
