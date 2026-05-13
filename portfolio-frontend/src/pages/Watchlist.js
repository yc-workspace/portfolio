import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';

const ASSET_TYPES = [
  { value: 'tw_stock', label: '台股' },
  { value: 'us_stock', label: '美股' },
  { value: 'etf_tw',   label: '台灣ETF' },
  { value: 'etf_us',   label: '美國ETF' },
  { value: 'crypto',   label: '加密貨幣' },
  { value: 'gold',     label: '黃金' },
];

const INTERVALS = [
  { label: '日線', value: '1day' },
  { label: '週線', value: '1week' },
  { label: '月線', value: '1month' },
];

const PERIODS = [
  { label: '1個月', months: 1 },
  { label: '3個月', months: 3 },
  { label: '6個月', months: 6 },
  { label: '1年', months: 12 },
  { label: '3年', months: 36 },
  { label: '5年', months: 60 },
  { label: '10年', months: 120 },
];

// ─── Simple SVG Candlestick Chart ─────────────────────────────────────────────
function CandlestickChart({ data, width = 340, height = 200 }) {
  if (!data || data.length === 0) return (
    <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
      無資料
    </div>
  );

  const pad = { top: 12, right: 8, bottom: 28, left: 52 };
  const W = width - pad.left - pad.right;
  const H = height - pad.top - pad.bottom;

  const prices = data.flatMap(d => [d.high, d.low]);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const toY = v => H - ((v - minP) / range) * H;
  const barW = Math.max(2, Math.floor(W / data.length) - 1);

  const xLabels = [];
  const step = Math.max(1, Math.floor(data.length / 5));
  for (let i = 0; i < data.length; i += step) {
    const d = data[i];
    const x = pad.left + (i / (data.length - 1)) * W;
    const label = typeof d.ts === 'string' ? d.ts.slice(0, 10) : new Date(d.ts).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' });
    xLabels.push({ x, label });
  }

  const yTicks = 4;
  const yLabels = Array.from({ length: yTicks + 1 }, (_, i) => {
    const v = minP + (range / yTicks) * i;
    return { y: pad.top + H - ((v - minP) / range) * H, label: v >= 1000 ? v.toFixed(0) : v.toFixed(2) };
  });

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {/* Grid lines */}
      {yLabels.map((t, i) => (
        <g key={i}>
          <line x1={pad.left} x2={pad.left + W} y1={t.y} y2={t.y} stroke="rgba(30,45,69,0.8)" strokeWidth={1} />
          <text x={pad.left - 4} y={t.y + 4} textAnchor="end" fill="#4a5a75" fontSize={9}>{t.label}</text>
        </g>
      ))}

      {/* Candles */}
      {data.map((d, i) => {
        const x = pad.left + (i / Math.max(data.length - 1, 1)) * W;
        const isUp = d.close >= d.open;
        const color = isUp ? '#10b981' : '#ef4444';
        const bodyTop = pad.top + toY(Math.max(d.open, d.close));
        const bodyBot = pad.top + toY(Math.min(d.open, d.close));
        const bodyH = Math.max(1, bodyBot - bodyTop);
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={pad.top + toY(d.high)} y2={pad.top + toY(d.low)} stroke={color} strokeWidth={1} />
            <rect x={x - barW / 2} y={bodyTop} width={barW} height={bodyH} fill={color} fillOpacity={0.85} />
          </g>
        );
      })}

      {/* X labels */}
      {xLabels.map((t, i) => (
        <text key={i} x={t.x} y={height - 6} textAnchor="middle" fill="#4a5a75" fontSize={9}>{t.label}</text>
      ))}
    </svg>
  );
}

// ─── Chart Panel ──────────────────────────────────────────────────────────────
function ChartPanel({ ticker, assetType }) {
  const [interval, setInterval] = useState('1day');
  const [period, setPeriod] = useState(12);
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadChart = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    try {
      const end = new Date().toISOString().slice(0, 10);
      const start = new Date(Date.now() - period * 30 * 24 * 3600 * 1000).toISOString().slice(0, 10);
      const data = await api.getHistory(ticker, start, end, interval);
      setChartData(data);
    } catch (e) {
      console.error('Chart load error:', e);
    } finally {
      setLoading(false);
    }
  }, [ticker, interval, period]);

  useEffect(() => { loadChart(); }, [loadChart]);

  const last = chartData[chartData.length - 1];
  const first = chartData[0];
  const totalReturn = (last && first) ? ((last.close - first.open) / first.open * 100) : null;

  return (
    <div style={{ marginTop: 12 }}>
      {/* Period selector */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
        {PERIODS.map(p => (
          <button key={p.months}
            className={period === p.months ? 'chip-btn active' : 'chip-btn'}
            onClick={() => setPeriod(p.months)}>
            {p.label}
          </button>
        ))}
      </div>

      {/* Interval selector */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {INTERVALS.map(iv => (
          <button key={iv.value}
            className={interval === iv.value ? 'chip-btn active' : 'chip-btn'}
            onClick={() => setInterval(iv.value)}>
            {iv.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      {loading ? (
        <div className="loading-spinner">載入圖表...</div>
      ) : (
        <>
          <CandlestickChart data={chartData} />
          {totalReturn != null && (
            <div style={{ textAlign: 'right', fontSize: 11, marginTop: 6, color: totalReturn >= 0 ? 'var(--up-color)' : 'var(--down-color)' }}>
              區間報酬 {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Add Watchlist Modal ──────────────────────────────────────────────────────
function AddModal({ onClose, onSaved }) {
  const [form, setForm] = useState({ ticker: '', name: '', asset_type: 'tw_stock', currency: 'TWD' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!form.ticker) { setError('請填寫 Ticker'); return; }
    setSaving(true); setError('');
    try {
      const currencyMap = { tw_stock: 'TWD', etf_tw: 'TWD', us_stock: 'USD', etf_us: 'USD', crypto: 'USD', gold: 'USD' };
      await api.addToWatchlist({ ...form, ticker: form.ticker.toUpperCase().trim(), currency: currencyMap[form.asset_type] || 'TWD' });
      onSaved(); onClose();
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-sheet">
        <div className="modal-handle" />
        <div className="modal-title">加入觀察清單</div>
        {error && <div className="error-msg">{error}</div>}
        <div className="form-group">
          <label className="form-label">類型</label>
          <select className="form-select" value={form.asset_type} onChange={e => setForm(f => ({ ...f, asset_type: e.target.value }))}>
            {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="form-group">
            <label className="form-label">Ticker</label>
            <input className="form-input" value={form.ticker} onChange={e => setForm(f => ({ ...f, ticker: e.target.value }))} placeholder="如: 2330" />
          </div>
          <div className="form-group">
            <label className="form-label">名稱（選填）</label>
            <input className="form-input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如: 台積電" />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>取消</button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleSave} disabled={saving}>{saving ? '儲存中...' : '加入'}</button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Watchlist Page ──────────────────────────────────────────────────────
export default function Watchlist() {
  const [list, setList] = useState([]);
  const [prices, setPrices] = useState({});
  const [selected, setSelected] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const items = await api.getWatchlist();
      setList(items);
      // Fetch prices concurrently
      const pricePromises = items.map(item => api.getPrice(item.ticker, item.asset_type).catch(() => null));
      const priceResults = await Promise.all(pricePromises);
      const priceMap = {};
      items.forEach((item, i) => { if (priceResults[i]) priceMap[item.ticker] = priceResults[i]; });
      setPrices(priceMap);
    } catch (e) {
      console.error('Watchlist error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRemove = async (ticker) => {
    if (!window.confirm(`確認移除 ${ticker}？`)) return;
    await api.removeFromWatchlist(ticker);
    if (selected?.ticker === ticker) setSelected(null);
    load();
  };

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="page-title">觀察清單</div>
            <div className="page-subtitle">{list.length} 個標的</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAdd(true)}>＋ 新增</button>
        </div>
      </div>

      {loading ? <div className="loading-spinner">載入中...</div> : (
        <>
          {/* Watchlist items */}
          {list.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>👁</div>
              <div>尚無觀察標的</div>
            </div>
          ) : (
            <div style={{ margin: '0 12px 12px' }}>
              {list.map(item => {
                const p = prices[item.ticker];
                const isUp = p?.price_change_pct > 0;
                const isSelected = selected?.ticker === item.ticker;
                return (
                  <div key={item.ticker} className={`watchlist-item ${isSelected ? 'selected' : ''}`} onClick={() => setSelected(isSelected ? null : item)}>
                    <div className="wl-left">
                      <div className="wl-ticker">{item.ticker}</div>
                      <div className="wl-name">{item.name || item.asset_type}</div>
                    </div>
                    <div className="wl-right">
                      <div className={`num wl-price ${p ? (isUp ? 'up' : 'down') : 'flat'}`}>
                        {p?.price != null ? p.price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}
                      </div>
                      <div className={`num wl-change ${p ? (isUp ? 'up' : 'down') : 'flat'}`}>
                        {p?.price_change_pct != null ? `${isUp ? '+' : ''}${p.price_change_pct.toFixed(2)}%` : '—'}
                      </div>
                    </div>
                    <button className="wl-remove" onClick={e => { e.stopPropagation(); handleRemove(item.ticker); }}>✕</button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Chart Panel for selected item */}
          {selected && (
            <div className="card">
              <div className="card-header">
                <div>
                  <div style={{ fontWeight: 600 }}>{selected.ticker}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selected.name}</div>
                </div>
              </div>
              <ChartPanel ticker={selected.ticker} assetType={selected.asset_type} />
            </div>
          )}
        </>
      )}

      {showAdd && <AddModal onClose={() => setShowAdd(false)} onSaved={load} />}
    </div>
  );
}
