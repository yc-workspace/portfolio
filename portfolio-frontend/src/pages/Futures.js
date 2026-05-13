// ============================================================
// Futures.js - 期貨看板
// ============================================================
import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

export function Futures() {
  const [txf, setTxf] = useState(null);
  const [intl, setIntl] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const load = useCallback(async () => {
    try {
      const [txfData, intlData] = await Promise.all([
        api.getTxfQuote(),
        api.getInternationalFutures()
      ]);
      setTxf(txfData);
      setIntl(intlData);
      setLastUpdate(new Date());
    } catch (e) {
      console.error('Futures load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(timer);
  }, [load]);

  const fmt = (n, d = 2) => n != null ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—';

  const QuoteCard = ({ title, item, big = false }) => {
    if (!item) return null;
    const isUp = item.price_change_pct > 0;
    const isDown = item.price_change_pct < 0;
    const cls = isUp ? 'up' : isDown ? 'down' : 'flat';
    return (
      <div className="card" style={{ marginBottom: 8 }}>
        <div className="card-title">{title}</div>
        {item.note && <div style={{ fontSize: 11, color: 'var(--accent-yellow)', marginBottom: 8 }}>⚠ {item.note}</div>}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <div className={`num ${cls}`} style={{ fontSize: big ? 28 : 22, fontWeight: 700, lineHeight: 1 }}>
              {fmt(item.price, item.price > 1000 ? 0 : 2)}
            </div>
            <div className={`num ${cls}`} style={{ fontSize: 13, marginTop: 6 }}>
              {isUp ? '▲' : isDown ? '▼' : '─'}{' '}
              {item.price_change != null ? `${fmt(Math.abs(item.price_change), 0)}` : ''}
              {item.price_change_pct != null ? ` (${Math.abs(item.price_change_pct).toFixed(2)}%)` : ''}
            </div>
          </div>
          {item.volume != null && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>成交量</div>
              <div className="num" style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{item.volume?.toLocaleString()}</div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="page-title">期貨看板</div>
            <div className="page-subtitle">
              {lastUpdate ? `更新 ${lastUpdate.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}` : '—'}
            </div>
          </div>
          <button className="btn btn-ghost" onClick={load} style={{ fontSize: 12 }}>↻ 刷新</button>
        </div>
      </div>

      {loading ? <div className="loading-spinner">載入期貨資料...</div> : (
        <>
          {txf && <QuoteCard title={`台指期 ${txf.contract || ''}`} item={txf} big />}
          <div className="card-title" style={{ padding: '4px 24px', color: 'var(--text-muted)' }}>國際期貨</div>
          {intl.map(item => (
            <QuoteCard key={item.symbol} title={item.label} item={item} />
          ))}
        </>
      )}
    </div>
  );
}

export default Futures;
