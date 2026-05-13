import React, { useState, useEffect, useCallback } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api';

// ─── Color Palette for Charts ─────────────────────────────────────────────────
const CHART_COLORS = [
  '#3b82f6','#06b6d4','#10b981','#f59e0b','#8b5cf6',
  '#ef4444','#ec4899','#14b8a6','#f97316','#6366f1'
];

// ─── Market Overview Card ─────────────────────────────────────────────────────
function MarketOverview({ data, loading }) {
  if (loading) return <div className="card"><div className="loading-spinner">載入市場資料...</div></div>;

  return (
    <div className="card">
      <div className="card-title">市場快訊</div>
      <div className="market-grid">
        {(data || []).map(item => {
          const isUp = item.price_change_pct > 0;
          const isDown = item.price_change_pct < 0;
          const cls = isUp ? 'up' : isDown ? 'down' : 'flat';
          const arrow = isUp ? '▲' : isDown ? '▼' : '─';
          return (
            <div key={item.symbol} className="market-item">
              <div className="market-label">{item.label}</div>
              <div className={`market-price num ${cls}`}>
                {item.price != null
                  ? item.price.toLocaleString(undefined, { maximumFractionDigits: 2 })
                  : '—'}
              </div>
              <div className={`market-change num ${cls}`}>
                {item.price_change_pct != null
                  ? `${arrow} ${Math.abs(item.price_change_pct).toFixed(2)}%`
                  : item.note || '—'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Summary Card ─────────────────────────────────────────────────────────────
function SummaryCard({ summary }) {
  if (!summary) return null;
  const isUp = summary.total_pnl_twd >= 0;
  const cls = isUp ? 'up' : 'down';

  return (
    <div className="card summary-card">
      <div className="card-title">總資產概覽</div>
      <div className="summary-value num">
        {summary.total_value_twd != null
          ? `NT$ ${Math.round(summary.total_value_twd).toLocaleString()}`
          : '—'}
      </div>
      <div className="summary-row">
        <span className="text-muted">總損益</span>
        <span className={`num ${cls}`}>
          {summary.total_pnl_twd != null
            ? `${isUp ? '+' : ''}NT$ ${Math.round(summary.total_pnl_twd).toLocaleString()}`
            : '—'}
          {summary.total_pnl_pct != null &&
            <span className="pnl-badge ml-6" style={{ marginLeft: 8 }}>
              {isUp ? '+' : ''}{summary.total_pnl_pct.toFixed(2)}%
            </span>}
        </span>
      </div>
      <div className="summary-row">
        <span className="text-muted" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          匯率 USD/TWD: {summary.usd_twd_rate?.toFixed(2) ?? '—'}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          更新 {summary.updated_at ? new Date(summary.updated_at).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' }) : '—'}
        </span>
      </div>
    </div>
  );
}

// ─── Allocation Pie Charts ─────────────────────────────────────────────────────
const CURRENCY_LABELS = { TWD: '台幣', USD: '美元', JPY: '日圓', HKD: '港幣', EUR: '歐元' };

function AllocationCharts({ currencyAlloc, tickerAlloc }) {
  const [activeTab, setActiveTab] = useState('currency');

  const currencyData = Object.entries(currencyAlloc || {}).map(([key, v]) => ({
    name: CURRENCY_LABELS[key] || key,
    value: Math.round(v.value_twd),
    pct: v.pct
  }));

  // Collapse small tickers into "其他"
  const tickerEntries = Object.entries(tickerAlloc || {});
  const significant = tickerEntries.filter(([, v]) => v.pct >= 3);
  const others = tickerEntries.filter(([, v]) => v.pct < 3);
  const tickerData = [
    ...significant.map(([k, v]) => ({ name: k, value: Math.round(v.value_twd), pct: v.pct })),
    ...(others.length ? [{ name: '其他', value: Math.round(others.reduce((a, [, v]) => a + v.value_twd, 0)), pct: others.reduce((a, [, v]) => a + v.pct, 0) }] : [])
  ];

  const data = activeTab === 'currency' ? currencyData : tickerData;

  const renderLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, pct }) => {
    if (pct < 5) return null;
    const RADIAN = Math.PI / 180;
    const r = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + r * Math.cos(-midAngle * RADIAN);
    const y = cy + r * Math.sin(-midAngle * RADIAN);
    return <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={10} fontWeight={600}>{pct.toFixed(1)}%</text>;
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title" style={{ marginBottom: 0 }}>資產配置</div>
        <div className="tab-toggle">
          <button className={activeTab === 'currency' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('currency')}>幣別</button>
          <button className={activeTab === 'ticker' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('ticker')}>標的</button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        <ResponsiveContainer width="50%" height={160}>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={40} outerRadius={72}
              dataKey="value" labelLine={false} label={renderLabel}>
              {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
            </Pie>
            <Tooltip formatter={(v) => `NT$ ${v.toLocaleString()}`} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pie-legend">
          {data.map((item, i) => (
            <div key={item.name} className="legend-row">
              <span className="legend-dot" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
              <span className="legend-name">{item.name}</span>
              <span className="legend-pct num">{item.pct.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Exchange Rate Card ───────────────────────────────────────────────────────
function ExchangeRates({ data }) {
  return (
    <div className="card">
      <div className="card-title">匯率看板</div>
      <div className="rates-list">
        {(data || []).map(pair => (
          <div key={`${pair.from_currency}${pair.to_currency}`} className="rate-row">
            <span className="rate-label">{pair.display_name || `${pair.from_currency}/${pair.to_currency}`}</span>
            <span className="num rate-value">
              {pair.rate != null ? pair.rate.toFixed(4) : '—'}
            </span>
          </div>
        ))}
        {(!data || data.length === 0) && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>前往設定新增匯率</div>}
      </div>
    </div>
  );
}

// ─── Top Movers ───────────────────────────────────────────────────────────────
function TopMovers({ holdings }) {
  if (!holdings || holdings.length === 0) return null;

  const withChange = holdings.filter(h => h.price_change_pct != null);
  const sorted = [...withChange].sort((a, b) => (b.price_change_pct || 0) - (a.price_change_pct || 0));
  const top3 = sorted.slice(0, 3);
  const bot3 = sorted.slice(-3).reverse();

  const MoverItem = ({ h }) => {
    const isUp = h.price_change_pct >= 0;
    return (
      <div className="mover-item">
        <span className="mover-ticker">{h.ticker}</span>
        <span className={`num mover-pct ${isUp ? 'up' : 'down'}`}>
          {isUp ? '+' : ''}{h.price_change_pct?.toFixed(2)}%
        </span>
      </div>
    );
  };

  return (
    <div className="card">
      <div className="card-title">今日持倉表現</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--up-color)', marginBottom: 8, fontWeight: 600 }}>▲ 漲幅前三</div>
          {top3.map(h => <MoverItem key={h.id} h={h} />)}
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--down-color)', marginBottom: 8, fontWeight: 600 }}>▼ 跌幅前三</div>
          {bot3.map(h => <MoverItem key={h.id} h={h} />)}
        </div>
      </div>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [market, setMarket] = useState(null);
  const [marketLoading, setMarketLoading] = useState(true);
  const [portfolioData, setPortfolioData] = useState(null);
  const [rates, setRates] = useState(null);

  const loadMarket = useCallback(async () => {
    try {
      const data = await api.getMarketOverview();
      setMarket(data);
    } catch (e) {
      console.error('Market overview error:', e);
    } finally {
      setMarketLoading(false);
    }
  }, []);

  const loadPortfolio = useCallback(async () => {
    try {
      const data = await api.getPortfolioSummary();
      setPortfolioData(data);
    } catch (e) {
      console.error('Portfolio error:', e);
    }
  }, []);

  const loadRates = useCallback(async () => {
    try {
      const data = await api.getExchangeRates();
      setRates(data);
    } catch (e) {
      console.error('Rates error:', e);
    }
  }, []);

  useEffect(() => {
    loadMarket();
    loadPortfolio();
    loadRates();
  }, [loadMarket, loadPortfolio, loadRates]);

  return (
    <div>
      <div className="page-header">
        <div className="page-title">投資總覽</div>
        <div className="page-subtitle">
          {new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })}
        </div>
      </div>

      <SummaryCard summary={portfolioData?.summary} />
      <MarketOverview data={market} loading={marketLoading} />

      {portfolioData && (
        <>
          <AllocationCharts
            currencyAlloc={portfolioData.currency_allocation}
            tickerAlloc={portfolioData.ticker_allocation}
          />
          <TopMovers holdings={portfolioData.holdings} />
        </>
      )}

      <ExchangeRates data={rates} />

      <div style={{ height: 8 }} />
    </div>
  );
}
