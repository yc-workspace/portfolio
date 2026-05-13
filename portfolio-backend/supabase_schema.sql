-- ============================================================
-- Portfolio App - Supabase Schema
-- Run this entire file in Supabase SQL Editor
-- ============================================================

-- 1. Portfolio Holdings (持倉)
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,           -- e.g. "2330", "AAPL", "BTC"
    name VARCHAR(100),                     -- e.g. "台積電", "Apple Inc."
    asset_type VARCHAR(20) NOT NULL,       -- "tw_stock", "us_stock", "crypto", "gold", "etf"
    currency VARCHAR(10) NOT NULL,         -- "TWD", "USD"
    exchange VARCHAR(20),                  -- "TSE", "OTC", "NASDAQ", "NYSE"
    shares DECIMAL(18, 6) NOT NULL,        -- 股數/數量 (BTC 可以有小數)
    cost_price DECIMAL(18, 6) NOT NULL,    -- 平均成本價 (原幣)
    cost_price_twd DECIMAL(18, 2),         -- 成本價折台幣 (買入時匯率換算)
    buy_date DATE,                         -- 首次買入日期
    notes TEXT,                            -- 備註
    is_active BOOLEAN DEFAULT true,        -- false = 已出清但保留紀錄
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Dividend Records (配息紀錄)
CREATE TABLE IF NOT EXISTS dividend_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    holding_id UUID REFERENCES portfolio_holdings(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    ex_date DATE NOT NULL,                 -- 除息日
    pay_date DATE,                         -- 發放日
    dividend_per_share DECIMAL(18, 6) NOT NULL,  -- 每股配息 (原幣)
    currency VARCHAR(10) NOT NULL,
    shares_held DECIMAL(18, 6),            -- 當時持有股數
    total_dividend DECIMAL(18, 6),         -- 總配息金額 (原幣)
    total_dividend_twd DECIMAL(18, 2),     -- 折台幣
    exchange_rate DECIMAL(10, 6),          -- 換算時匯率
    source VARCHAR(20) DEFAULT 'manual',   -- "manual" or "auto"
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Watchlist (觀察清單)
CREATE TABLE IF NOT EXISTS watchlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100),
    asset_type VARCHAR(20) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    exchange VARCHAR(20),
    notes TEXT,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. User Settings (用戶設定)
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Custom Currency Pairs (自訂匯率看板)
CREATE TABLE IF NOT EXISTS currency_pairs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    from_currency VARCHAR(10) NOT NULL,    -- e.g. "USD"
    to_currency VARCHAR(10) NOT NULL,      -- e.g. "TWD"
    display_name VARCHAR(30),              -- e.g. "美元/台幣"
    sort_order INT DEFAULT 0,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_currency, to_currency)
);

-- 6. Price Cache (報價快取 - 短暫儲存，減少 API 呼叫)
CREATE TABLE IF NOT EXISTS price_cache (
    ticker VARCHAR(20) PRIMARY KEY,
    price DECIMAL(18, 6),
    price_change DECIMAL(18, 6),
    price_change_pct DECIMAL(10, 6),
    open_price DECIMAL(18, 6),
    high_price DECIMAL(18, 6),
    low_price DECIMAL(18, 6),
    volume BIGINT,
    currency VARCHAR(10),
    source VARCHAR(30),                    -- "shioaji", "twelve_data", "coingecko", "yahoo"
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    market_status VARCHAR(20)              -- "open", "closed", "pre", "post"
);

-- ============================================================
-- Default Data
-- ============================================================

-- Default currency pairs
INSERT INTO currency_pairs (from_currency, to_currency, display_name, sort_order, is_default)
VALUES 
    ('USD', 'TWD', '美元/台幣', 1, true),
    ('JPY', 'TWD', '日圓/台幣', 2, false)
ON CONFLICT (from_currency, to_currency) DO NOTHING;

-- Default settings
INSERT INTO user_settings (key, value, description) VALUES
    ('tw_stock_open', '09:00', '台股開盤時間'),
    ('tw_stock_close', '13:30', '台股收盤時間'),
    ('us_stock_open', '22:30', '美股開盤時間(台灣時間)'),
    ('us_stock_close', '05:00', '美股收盤時間(台灣時間)'),
    ('poll_interval_open', '5', '開盤輪詢間隔(分鐘)'),
    ('poll_interval_closed', '60', '收盤輪詢間隔(分鐘)'),
    ('crypto_poll_interval', '1', '加密貨幣輪詢間隔(分鐘)'),
    ('idle_timeout_minutes', '15', 'Render 閒置逾時(分鐘)')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON portfolio_holdings(ticker);
CREATE INDEX IF NOT EXISTS idx_holdings_active ON portfolio_holdings(is_active);
CREATE INDEX IF NOT EXISTS idx_dividends_ticker ON dividend_records(ticker);
CREATE INDEX IF NOT EXISTS idx_dividends_holding ON dividend_records(holding_id);
CREATE INDEX IF NOT EXISTS idx_price_cache_fetched ON price_cache(fetched_at);

-- ============================================================
-- Auto-update updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER holdings_updated_at
    BEFORE UPDATE ON portfolio_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
