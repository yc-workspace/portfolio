const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

async function apiFetch(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${response.status}`);
  }
  return response.json();
}

export const api = {
  // Status
  getStatus: () => apiFetch('/api/status'),
  keepalive: () => apiFetch('/api/keepalive', { method: 'POST' }),
  health: () => apiFetch('/health'),

  // Quotes
  getMarketOverview: () => apiFetch('/api/quotes/market-overview'),
  getPrice: (ticker, assetType) => apiFetch(`/api/quotes/price/${ticker}${assetType ? `?asset_type=${assetType}` : ''}`),
  getExchangeRates: () => apiFetch('/api/quotes/exchange-rates'),
  getHistory: (ticker, start, end, interval = '1day') =>
    apiFetch(`/api/quotes/history/${ticker}?start=${start}&end=${end}&interval=${interval}`),

  // Portfolio
  getHoldings: () => apiFetch('/api/portfolio/holdings'),
  addHolding: (data) => apiFetch('/api/portfolio/holdings', { method: 'POST', body: JSON.stringify(data) }),
  updateHolding: (id, data) => apiFetch(`/api/portfolio/holdings/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteHolding: (id) => apiFetch(`/api/portfolio/holdings/${id}`, { method: 'DELETE' }),
  getPortfolioSummary: () => apiFetch('/api/portfolio/summary'),
  getDividends: (ticker) => apiFetch(`/api/portfolio/dividends${ticker ? `?ticker=${ticker}` : ''}`),
  addDividend: (data) => apiFetch('/api/portfolio/dividends', { method: 'POST', body: JSON.stringify(data) }),
  deleteDividend: (id) => apiFetch(`/api/portfolio/dividends/${id}`, { method: 'DELETE' }),

  // Watchlist
  getWatchlist: () => apiFetch('/api/watchlist'),
  addToWatchlist: (data) => apiFetch('/api/watchlist', { method: 'POST', body: JSON.stringify(data) }),
  removeFromWatchlist: (ticker) => apiFetch(`/api/watchlist/${ticker}`, { method: 'DELETE' }),

  // Futures
  getTxfQuote: () => apiFetch('/api/futures/txf'),
  getInternationalFutures: () => apiFetch('/api/futures/international'),

  // Settings
  getSettings: () => apiFetch('/api/settings'),
  updateSetting: (key, value) => apiFetch(`/api/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
  getCurrencyPairs: () => apiFetch('/api/settings/currency-pairs'),
  addCurrencyPair: (data) => apiFetch('/api/settings/currency-pairs', { method: 'POST', body: JSON.stringify(data) }),
  deleteCurrencyPair: (id) => apiFetch(`/api/settings/currency-pairs/${id}`, { method: 'DELETE' }),
  connectShioaji: () => apiFetch('/api/settings/shioaji/connect', { method: 'POST' }),
};

export default api;
