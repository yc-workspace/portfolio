import React, { useContext } from 'react';
import { QuoteContext } from '../App';

export default function Futures() {
  const { marketData, fetching, lastFetchedAt, refresh } = useContext(QuoteContext);

  // Extract TXF and TWII from shared market data
  const txf  = marketData?.find(d => d.symbol === 'TXFR1');
  const twii = marketData?.find(d => d.symbol === 'TWII');

  const fmt = (n, d = 0) =>
    n != null ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—';

  const QuoteCard = ({ item, big = false }) => {
    if (!item) return null;
    const chg = item.price_change_pct;
    const cls   = chg > 0 ? 'up' : chg < 0 ? 'down' : 'flat';
    const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '─';
    return (
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-header">
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{item.label}</div>
            {item.note && (
              <div style={{ fontSize: 11, color: 'var(--accent-yellow)', marginTop: 3 }}>
                ⚠ {item.note}
              </div>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {item.source === 'shioaji' ? '永豐即時' : item.source || ''}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <div className={`num ${cls}`} style={{ fontSize: big ? 30 : 22, fontWeight: 700 }}>
              {fmt(item.price)}
            </div>
            <div className={`num ${cls}`} style={{ fontSize: 13, marginTop: 4 }}>
              {arrow} {item.price_change != null ? fmt(Math.abs(item.price_change)) : ''}
              {chg != null ? ` (${Math.abs(chg).toFixed(2)}%)` : ''}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            {item.high > 0 && (
              <>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>高 / 低</div>
                <div className="num" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {fmt(item.high)} / {fmt(item.low)}
                </div>
              </>
            )}
            {item.volume > 0 && (
              <>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>成交量</div>
                <div className="num" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {item.volume?.toLocaleString()}
                </div>
              </>
            )}
          </div>
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
              {lastFetchedAt
                ? `更新 ${lastFetchedAt.toLocaleTimeString('zh-TW',
                    { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
                : '—'}
            </div>
          </div>
          <button className="btn btn-ghost" style={{ fontSize: 12 }}
                  onClick={refresh} disabled={fetching}>
            {fetching ? '更新中…' : '↻ 刷新'}
          </button>
        </div>
      </div>

      {!marketData ? (
        <div className="loading-spinner">載入期貨資料...</div>
      ) : (
        <>
          <div className="card-title" style={{ padding: '4px 24px 0', color: 'var(--text-muted)' }}>
            台灣期貨
          </div>
          <QuoteCard item={txf}  big />
          <QuoteCard item={twii} />

          <div className="card-title" style={{ padding: '12px 24px 0', color: 'var(--text-muted)' }}>
            國際指數（參考）
          </div>
          {['SPX', 'NDX', 'SOX'].map(sym => (
            <QuoteCard key={sym} item={marketData.find(d => d.symbol === sym)} />
          ))}

          <div style={{ margin: '12px 12px 0', padding: 12,
                        background: 'var(--bg-card)', borderRadius: 8,
                        border: '1px solid var(--border)', fontSize: 11,
                        color: 'var(--text-muted)', lineHeight: 1.8 }}>
            💡 台指期日盤 09:00–13:45 · 夜盤 15:00–05:00<br />
            連線永豐API後可取得即時台指期報價
          </div>
        </>
      )}
    </div>
  );
}
