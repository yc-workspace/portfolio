import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

export default function Settings() {
  const [settings, setSettings] = useState({});
  const [pairs, setPairs] = useState([]);
  const [shioajiStatus, setShioajiStatus] = useState(null);
  const [newPair, setNewPair] = useState({ from: '', to: '' });
  const [saving, setSaving] = useState({});
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    try {
      const [s, p, status] = await Promise.all([
        api.getSettings(),
        api.getCurrencyPairs(),
        api.health()
      ]);
      setSettings(s);
      setPairs(p);
      setShioajiStatus(status);
    } catch (e) {
      console.error('Settings load error:', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateSetting = async (key, value) => {
    setSaving(s => ({ ...s, [key]: true }));
    try {
      await api.updateSetting(key, String(value));
      setSettings(s => ({ ...s, [key]: String(value) }));
      flash('已儲存');
    } catch (e) {
      flash('儲存失敗: ' + e.message, true);
    } finally {
      setSaving(s => ({ ...s, [key]: false }));
    }
  };

  const flash = (text, isError = false) => {
    setMsg(isError ? `❌ ${text}` : `✅ ${text}`);
    setTimeout(() => setMsg(''), 3000);
  };

  const addPair = async () => {
    if (!newPair.from || !newPair.to) return;
    try {
      await api.addCurrencyPair({
        from_currency: newPair.from.toUpperCase(),
        to_currency: newPair.to.toUpperCase(),
      });
      setNewPair({ from: '', to: '' });
      load();
      flash('匯率對已新增');
    } catch (e) { flash('新增失敗: ' + e.message, true); }
  };

  const removePair = async (id) => {
    await api.deleteCurrencyPair(id);
    load();
  };

  const connectShioaji = async () => {
    try {
      const result = await api.connectShioaji();
      flash(result.message, !result.connected);
      load();
    } catch (e) { flash('連線失敗', true); }
  };

  const SettingRow = ({ label, settingKey, type = 'number', suffix = '' }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          className="form-input"
          type={type}
          style={{ width: 80, textAlign: 'right', padding: '4px 8px' }}
          defaultValue={settings[settingKey] || ''}
          onBlur={e => updateSetting(settingKey, e.target.value)}
        />
        {suffix && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{suffix}</span>}
        {saving[settingKey] && <span style={{ fontSize: 11, color: 'var(--accent-cyan)' }}>儲存中</span>}
      </div>
    </div>
  );

  return (
    <div>
      <div className="page-header">
        <div className="page-title">設定</div>
      </div>

      {msg && (
        <div style={{ margin: '0 12px 8px', padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13 }}>
          {msg}
        </div>
      )}

      {/* API Status */}
      <div className="card">
        <div className="card-title">連線狀態</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 13 }}>後端伺服器 (Render)</span>
          <span className={shioajiStatus?.status === 'ok' ? 'up' : 'down'} style={{ fontSize: 12 }}>
            {shioajiStatus?.status === 'ok' ? '● 運作中' : '● 離線'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 13 }}>永豐 Shioaji</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className={shioajiStatus?.shioaji_connected ? 'up' : 'flat'} style={{ fontSize: 12 }}>
              {shioajiStatus?.shioaji_connected ? '● 已連線' : '● 未連線'}
            </span>
            <button className="btn btn-ghost" style={{ fontSize: 11, padding: '3px 10px' }} onClick={connectShioaji}>
              連線
            </button>
          </div>
        </div>
      </div>

      {/* Poll Settings */}
      <div className="card">
        <div className="card-title">報價更新頻率</div>
        <SettingRow label="台股輪詢間隔（開盤時）" settingKey="poll_interval_open" suffix="分鐘" />
        <SettingRow label="收盤後輪詢間隔" settingKey="poll_interval_closed" suffix="分鐘" />
        <SettingRow label="加密貨幣輪詢間隔" settingKey="crypto_poll_interval" suffix="分鐘" />
        <SettingRow label="閒置逾時（Render保活）" settingKey="idle_timeout_minutes" suffix="分鐘" />
      </div>

      {/* Market Hours */}
      <div className="card">
        <div className="card-title">開盤時段設定</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>台股開盤</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="form-input" type="time" style={{ width: 100 }}
              defaultValue={settings['tw_stock_open'] || '09:00'}
              onBlur={e => updateSetting('tw_stock_open', e.target.value)} />
            <span style={{ alignSelf: 'center', color: 'var(--text-muted)' }}>—</span>
            <input className="form-input" type="time" style={{ width: 100 }}
              defaultValue={settings['tw_stock_close'] || '13:30'}
              onBlur={e => updateSetting('tw_stock_close', e.target.value)} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>美股開盤（台灣時間）</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="form-input" type="time" style={{ width: 100 }}
              defaultValue={settings['us_stock_open'] || '22:30'}
              onBlur={e => updateSetting('us_stock_open', e.target.value)} />
            <span style={{ alignSelf: 'center', color: 'var(--text-muted)' }}>—</span>
            <input className="form-input" type="time" style={{ width: 100 }}
              defaultValue={settings['us_stock_close'] || '05:00'}
              onBlur={e => updateSetting('us_stock_close', e.target.value)} />
          </div>
        </div>
      </div>

      {/* Currency Pairs */}
      <div className="card">
        <div className="card-title">匯率看板設定</div>
        {pairs.map(pair => (
          <div key={pair.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13 }}>{pair.display_name || `${pair.from_currency}/${pair.to_currency}`}</span>
            {!pair.is_default && (
              <button className="btn btn-danger" style={{ fontSize: 11, padding: '3px 10px' }} onClick={() => removePair(pair.id)}>移除</button>
            )}
            {pair.is_default && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>預設</span>}
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <input className="form-input" placeholder="USD" style={{ flex: 1 }}
            value={newPair.from} onChange={e => setNewPair(p => ({ ...p, from: e.target.value }))} />
          <span style={{ alignSelf: 'center', color: 'var(--text-muted)' }}>/</span>
          <input className="form-input" placeholder="TWD" style={{ flex: 1 }}
            value={newPair.to} onChange={e => setNewPair(p => ({ ...p, to: e.target.value }))} />
          <button className="btn btn-primary" onClick={addPair} style={{ whiteSpace: 'nowrap' }}>新增</button>
        </div>
      </div>

      {/* App Info */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">關於</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <div>版本: 1.0.0 (Phase 1)</div>
          <div>報價來源: Twelve Data · CoinGecko · ExchangeRate-API · 永豐Shioaji</div>
          <div>資料庫: Supabase</div>
          <div>後端: Render · 前端: Vercel</div>
        </div>
      </div>
    </div>
  );
}
