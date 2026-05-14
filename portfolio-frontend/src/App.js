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

// ─── Global Quote Store (lifted state) ───────────────────────────────────────
// All pages read from here instead of fetching themselves.
// Timer lives here — page switching does NOT reset it.

export const QuoteContext = React.createContext(null);

function App() {
  // ── Server / keepalive ──
  const [serverOnline, setServerOnline]   = useState(false);
  const [countdown, setCountdown]         = useState(IDLE_TIMEOUT_MS / 1000);
  const lastActivityRef                   = useRef(Date.now());
  const countdownIntervalRef              = useRef(null);

  // ── Shared quote state ──
  const [marketData,    setMarketData]    = useState(null);
  const [portfolioData, setPortfolioData] = useState(null);
  const [ratesData,     setRatesData]     = useState(null);
  const [settings,      setSettings]      = useState({});
  const [lastFetchedAt, setLastFetchedAt] = useState(null);
  const [fetching,      setFetching]      = useState(false);
  const pollTimerRef                      = useRef(null);

  // ── Fetch all quotes (called on open + by timer) ──────────────────────────
  const fetchAllQuotes = useCallback(async ({ force = false } = {}) => {
    if (fetching && !force) return;
    setFetching(true);
    try {
      const [market, portfolio, rates] = await Promise.allSettled([
        api.getMarketOverview(),
        api.getPortfolioSummary(),
        api.getExchangeRates(),
      ]);
      if (market.status    === 'fulfilled') setMarketData(market.value);
      if (portfolio.status === 'fulfilled') setPortfolioData(portfolio.value);
      if (rates.status     === 'fulfilled') setRatesData(rates.value);
      setLastFetchedAt(new Date());
    } catch (e) {
      console.error('fetchAllQuotes error:', e);
    } finally {
      setFetching(false);
    }
  }, [fetching]);

  // ── Load settings, then fetch quotes on mount ─────────────────────────────
  useEffect(() => {
    api.health()
      .then(s => setServerOnline(s.status === 'ok'))
      .catch(() => setServerOnline(false));

    api.getSettings()
      .then(s => setSettings(s))
      .catch(() => {});

    // Immediate fetch on open (simulates wakeup refresh)
    fetchAllQuotes({ force: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Polling timer — respects settings ────────────────────────────────────
  const startPollTimer = useCallback(() => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    const getIntervalMs = () => {
      const nowTW = new Date(
        new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei' })
      );
      const hhmm = nowTW.getHours() * 100 + nowTW.getMinutes();

      const twOpen  = timeToHHMM(settings.tw_stock_open  || '09:00');
      const twClose = timeToHHMM(settings.tw_stock_close || '13:30');
      const usOpen  = timeToHHMM(settings.us_stock_open  || '22:30');
      const usClose = timeToHHMM(settings.us_stock_close || '05:00');

      const twSession = hhmm >= twOpen && hhmm < twClose;
      // US open spans midnight: 22:30–05:00
      const usSession = hhmm >= usOpen || hhmm < usClose;
      const inSession = twSession || usSession;

      const openMins   = parseInt(settings.poll_interval_open   || '5',  10);
      const closedMins = parseInt(settings.poll_interval_closed || '60', 10);
      return (inSession ? openMins : closedMins) * 60 * 1000;
    };

    // Re-evaluate interval every minute so it switches when session opens/closes
    pollTimerRef.current = setInterval(() => {
      fetchAllQuotes();
    }, getIntervalMs());

    return () => clearInterval(pollTimerRef.current);
  }, [settings, fetchAllQuotes]);

  useEffect(() => {
    const cleanup = startPollTimer();
    return cleanup;
  }, [startPollTimer]);

  // ── Keepalive / countdown ─────────────────────────────────────────────────
  const resetKeepalive = useCallback(async () => {
    lastActivityRef.current = Date.now();
    setCountdown(IDLE_TIMEOUT_MS / 1000);
    try { await api.keepalive(); } catch (_) {}
  }, []);

  useEffect(() => {
    countdownIntervalRef.current = setInterval(() => {
      const elapsed  = (Date.now() - lastActivityRef.current) / 1000;
      const remaining = Math.max(0, IDLE_TIMEOUT_MS / 1000 - elapsed);
      setCountdown(Math.floor(remaining));
    }, 1000);
    return () => clearInterval(countdownIntervalRef.current);
  }, []);

  const formatCountdown = s => {
    const m = Math.floor(s / 60);
    return `${m}:${(s % 60).toString().padStart(2, '0')}`;
  };

  // ── Context value passed to all pages ─────────────────────────────────────
  const quoteCtx = {
    marketData, portfolioData, ratesData, settings,
    lastFetchedAt, fetching,
    refresh: () => fetchAllQuotes({ force: true }),
    reloadSettings: () => api.getSettings().then(setSettings).catch(() => {}),
  };

  return (
    <QuoteContext.Provider value={quoteCtx}>
      <BrowserRouter>
        <div className="app">
          {/* Top Bar */}
          <header className="topbar">
            <span className="topbar-logo">📈 Portfolio</span>
            <div className="topbar-right">
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {lastFetchedAt
                  ? lastFetchedAt.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })
                  : '—'}
              </span>
              {fetching && <span className="fetch-spinner" title="更新中" />}
              <div className={`server-dot ${serverOnline ? 'online' : 'offline'}`}
                   title={serverOnline ? '伺服器運作中' : '伺服器離線'} />
              <button className="keepalive-btn" onClick={resetKeepalive}
                      title="點擊保持連線，避免伺服器睡眠">
                ⏱ {formatCountdown(countdown)}
              </button>
            </div>
          </header>

          <main className="main-content">
            <Routes>
              <Route path="/"          element={<Dashboard />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/watchlist" element={<Watchlist />} />
              <Route path="/futures"   element={<Futures />} />
              <Route path="/settings"  element={<Settings />} />
            </Routes>
          </main>

          {/* Bottom Nav */}
          <nav className="bottom-nav">
            {[
              { to: '/',          end: true,  icon: '🏠', label: '總覽' },
              { to: '/portfolio',             icon: '💼', label: '投組' },
              { to: '/watchlist',             icon: '👁',  label: '觀察' },
              { to: '/futures',               icon: '📊', label: '期貨' },
              { to: '/settings',              icon: '⚙️', label: '設定' },
            ].map(({ to, end, icon, label }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
                <span className="nav-icon">{icon}</span>
                <span className="nav-label">{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </BrowserRouter>
    </QuoteContext.Provider>
  );
}

function timeToHHMM(timeStr) {
  const [h, m] = (timeStr || '00:00').split(':').map(Number);
  return h * 100 + m;
}

export default App;
