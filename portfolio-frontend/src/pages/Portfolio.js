import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

const ASSET_TYPES = [
  { value: 'tw_stock', label: '台股', currency: 'TWD', exchange: 'TSE' },
  { value: 'us_stock', label: '美股', currency: 'USD', exchange: 'NASDAQ' },
  { value: 'etf_tw',   label: '台灣ETF', currency: 'TWD', exchange: 'TSE' },
  { value: 'etf_us',   label: '美國ETF', currency: 'USD', exchange: 'NASDAQ' },
  { value: 'crypto',   label: '加密貨幣', currency: 'USD', exchange: 'CRYPTO' },
  { value: 'gold',     label: '黃金', currency: 'USD', exchange: 'COMEX' },
];

const fmt = (n, digits = 2) =>
  n != null ? Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '—';

// ─── Add Holding Modal ────────────────────────────────────────────────────────
function AddHoldingModal({ onClose, onSaved }) {
  const [form, setForm] = useState({
    ticker: '', name: '', asset_type: 'tw_stock', currency: 'TWD',
    exchange: 'TSE', shares: '', cost_price: '', buy_date: ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => {
    setForm(f => {
      const next = { ...f, [k]: v };
      if (k === 'asset_type') {
        const preset = ASSET_TYPES.find(t => t.value === v);
        if (preset) { next.currency = preset.currency; next.exchange = preset.exchange; }
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!form.ticker || !form.shares || !form.cost_price) {
      setError('請填寫 Ticker、股數、成本價'); return;
    }
    setSaving(true); setError('');
    try {
      await api.addHolding({
        ...form,
        ticker: form.ticker.toUpperCase().trim(),
        shares: parseFloat(form.shares),
        cost_price: parseFloat(form.cost_price),
        buy_date: form.buy_date || undefined
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-sheet">
        <div className="modal-handle" />
        <div className="modal-title">新增持倉</div>
        {error && <div className="error-msg">{error}</div>}

        <div className="form-group">
          <label className="form-label">資產類型</label>
          <select className="form-select" value={form.asset_type} onChange={e => set('asset_type', e.target.value)}>
            {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="form-group">
            <label className="form-label">Ticker 代號</label>
            <input className="form-input" placeholder={form.asset_type === 'tw_stock' ? '如: 2330' : '如: AAPL'} value={form.ticker} onChange={e => set('ticker', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">名稱（選填）</label>
            <input className="form-input" placeholder="如: 台積電" value={form.name} onChange={e => set('name', e.target.value)} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="form-group">
            <label className="form-label">股數 / 數量</label>
            <input className="form-input" type="number" placeholder="0" value={form.shares} onChange={e => set('shares', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">成本價 ({form.currency})</label>
            <input className="form-input" type="number" placeholder="0.00" value={form.cost_price} onChange={e => set('cost_price', e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">買入日期（選填）</label>
          <input className="form-input" type="date" value={form.buy_date} onChange={e => set('buy_date', e.target.value)} />
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>取消</button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleSave} disabled={saving}>
            {saving ? '儲存中...' : '新增'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Holding Row ──────────────────────────────────────────────────────────────
function HoldingRow({ h, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const isUp = h.pnl != null && h.pnl >= 0;
  const cls = h.pnl != null ? (isUp ? 'up' : 'down') : 'flat';

  return (
    <>
      <tr onClick={() => setExpanded(e => !e)} style={{ cursor: 'pointer' }}>
        <td>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{h.ticker}</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{h.name || h.asset_type}</div>
        </td>
        <td className={cls}>
          {h.current_price != null ? fmt(h.current_price) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
        </td>
        <td className={cls}>
          {h.pnl_pct != null
            ? <span className={`pnl-badge ${isUp ? 'up' : 'down'}`}>{isUp ? '+' : ''}{h.pnl_pct.toFixed(2)}%</span>
            : '—'}
        </td>
        <td className={cls}>
          {h.pnl_twd != null ? `${isUp ? '+' : ''}${Math.round(h.pnl_twd).toLocaleString()}` : '—'}
        </td>
      </tr>
      {expanded && (
        <tr className="expanded-row">
          <td colSpan={4} style={{ padding: 0 }}>
            <div className="holding-detail">
              <div className="detail-grid">
                <DetailItem label="持有股數" value={fmt(h.shares, 4)} />
                <DetailItem label="成本價" value={`${h.currency} ${fmt(h.cost_price)}`} />
                <DetailItem label="市值(原幣)" value={h.current_value != null ? `${h.currency} ${fmt(h.current_value)}` : '—'} />
                <DetailItem label="市值(台幣)" value={h.current_value_twd != null ? `NT$ ${Math.round(h.current_value_twd).toLocaleString()}` : '—'} />
                <DetailItem label="損益(台幣)" value={h.pnl_twd != null ? `${isUp ? '+' : ''}NT$ ${Math.round(h.pnl_twd).toLocaleString()}` : '—'} cls={cls} />
                <DetailItem label="配息累積(台幣)" value={h.dividend_total_twd ? `NT$ ${Math.round(h.dividend_total_twd).toLocaleString()}` : 'NT$ 0'} />
                <DetailItem label="含息總報酬" value={h.total_return_pct != null ? `${h.total_return_pct >= 0 ? '+' : ''}${h.total_return_pct.toFixed(2)}%` : '—'} cls={h.total_return_pct >= 0 ? 'up' : 'down'} />
                <DetailItem label="報價來源" value={h.quote_source || '—'} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                <button className="btn btn-danger" style={{ fontSize: 11, padding: '4px 12px' }} onClick={() => onDelete(h.id)}>
                  移除持倉
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

const DetailItem = ({ label, value, cls }) => (
  <div className="detail-item">
    <span className="detail-label">{label}</span>
    <span className={`detail-value num ${cls || ''}`}>{value}</span>
  </div>
);

// ─── Main Portfolio Page ──────────────────────────────────────────────────────
export default function Portfolio() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const d = await api.getPortfolioSummary();
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id) => {
    if (!window.confirm('確認移除此持倉？')) return;
    try {
      await api.deleteHolding(id);
      load();
    } catch (e) {
      alert('刪除失敗: ' + e.message);
    }
  };

  const summary = data?.summary;
  const holdings = data?.holdings || [];
  const isUp = summary?.total_pnl_twd >= 0;

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="page-title">投資組合</div>
            <div className="page-subtitle">{holdings.length} 個持倉</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAdd(true)}>＋ 新增</button>
        </div>
      </div>

      {/* Summary Strip */}
      {summary && (
        <div className="card" style={{ marginBottom: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>總市值(台幣)</div>
              <div className="num" style={{ fontSize: 15, fontWeight: 600 }}>
                {summary.total_value_twd != null ? `${Math.round(summary.total_value_twd / 1000).toLocaleString()}K` : '—'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>未實現損益</div>
              <div className={`num ${isUp ? 'up' : 'down'}`} style={{ fontSize: 15, fontWeight: 600 }}>
                {summary.total_pnl_twd != null ? `${isUp ? '+' : ''}${(summary.total_pnl_pct || 0).toFixed(2)}%` : '—'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>USD/TWD</div>
              <div className="num" style={{ fontSize: 15, fontWeight: 600 }}>
                {summary.usd_twd_rate?.toFixed(2) ?? '—'}
              </div>
            </div>
          </div>
        </div>
      )}

      {error && <div className="error-msg" style={{ margin: '0 12px 12px' }}>{error}</div>}

      {loading ? (
        <div className="loading-spinner">載入投組資料...</div>
      ) : holdings.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>💼</div>
          <div>尚無持倉，點擊「新增」開始建立投資組合</div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left', paddingLeft: 16 }}>標的</th>
                <th>現價</th>
                <th>報酬%</th>
                <th>損益(台幣)</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map(h => <HoldingRow key={h.id} h={h} onDelete={handleDelete} />)}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddHoldingModal onClose={() => setShowAdd(false)} onSaved={load} />}
    </div>
  );
}
