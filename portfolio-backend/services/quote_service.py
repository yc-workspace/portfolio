import os
import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_API_KEY")
EXCHANGE_RATE_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

TW_STOCK_PATTERN = lambda t: (t.isdigit() and len(t) == 4) or (t.isdigit() and len(t) == 5)
CRYPTO_TICKERS = {"BTC", "ETH", "BNB", "SOL", "USDT"}

INDEX_SYMBOLS = {
    "SPX":   {"label": "S&P 500"},
    "NDX":   {"label": "NASDAQ 100"},
    "SOX":   {"label": "費城半導體"},
    "VIX":   {"label": "VIX"},
    "DXY":   {"label": "美元指數"},
    "TWII":  {"label": "台灣加權指數"},
    "XAU":   {"label": "黃金"},
    "BTC":   {"label": "比特幣"},
    "TXFR1": {"label": "台指期"},
}

class QuoteService:
    def __init__(self, shioaji_service=None):
        self.shioaji = shioaji_service
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    async def get_quote(self, ticker: str, asset_type: str = None) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        if asset_type == "crypto" or ticker in CRYPTO_TICKERS:
            return await self._get_crypto_quote(ticker)
        if TW_STOCK_PATTERN(ticker) or asset_type in ("tw_stock", "etf_tw"):
            return await self._get_tw_stock_quote(ticker)
        if ticker == "XAU" or asset_type == "gold":
            return await self._get_gold_quote()
        return await self._get_us_stock_quote(ticker)

    async def get_multiple_quotes(self, tickers_with_types: List[Dict]) -> Dict[str, Any]:
        tasks = [self.get_quote(i["ticker"], i.get("asset_type")) for i in tickers_with_types]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for item, result in zip(tickers_with_types, results):
            if isinstance(result, Exception):
                output[item["ticker"]] = {"error": str(result)}
            else:
                output[item["ticker"]] = result
        return output

    async def get_market_overview(self) -> List[Dict]:
        # Batch call: SPX, NDX, SOX, VIX, DXY in ONE Twelve Data request
        batch_result = await self._get_twelve_data_batch(["SPX", "NDX", "SOX", "VIX", "DXY"])
        twii, txf, xau, btc = await asyncio.gather(
            self._get_twii_quote(),
            self._get_txf_quote(),
            self._get_gold_quote(),
            self._get_crypto_quote("BTC"),
            return_exceptions=True
        )
        all_data = {
            "SPX":   batch_result.get("SPX"),
            "NDX":   batch_result.get("NDX"),
            "SOX":   batch_result.get("SOX"),
            "VIX":   batch_result.get("VIX"),
            "DXY":   batch_result.get("DXY"),
            "TWII":  None if isinstance(twii, Exception) else twii,
            "TXFR1": None if isinstance(txf,  Exception) else txf,
            "XAU":   None if isinstance(xau,  Exception) else xau,
            "BTC":   None if isinstance(btc,  Exception) else btc,
        }
        output = []
        for key in ["SPX","NDX","SOX","TWII","TXFR1","VIX","XAU","BTC","DXY"]:
            label = INDEX_SYMBOLS.get(key, {}).get("label", key)
            result = all_data.get(key)
            if not result or "error" in result:
                output.append({"symbol": key, "label": label, "price": None,
                                "change": None, "change_pct": None, "error": True})
            else:
                output.append({"symbol": key, "label": label, **result})
        return output

    async def get_exchange_rates(self, pairs: List[Dict]) -> List[Dict]:
        results = []
        for pair in pairs:
            try:
                rate = await self._get_exchange_rate(pair["from_currency"], pair["to_currency"])
                results.append({**pair, "rate": rate.get("rate"),
                                 "change_pct": rate.get("change_pct"),
                                 "fetched_at": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                results.append({**pair, "rate": None, "error": str(e)})
        return results

    async def _get_tw_stock_quote(self, ticker: str) -> Dict:
        if self.shioaji and self.shioaji.is_connected:
            cached = self.shioaji.get_cached_quote(ticker)
            if cached:
                return cached
            snapshot = await self.shioaji.get_snapshot([ticker])
            if snapshot.get(ticker):
                return snapshot[ticker]
        return await self._get_yahoo_quote(f"{ticker}.TW")

    async def _get_twii_quote(self) -> Dict:
        if self.shioaji and self.shioaji.is_connected:
            try:
                loop = asyncio.get_event_loop()
                def _get():
                    snapshots = self.shioaji.api.snapshots(
                        [self.shioaji.api.Contracts.Indexs.TSE["001"]])
                    if snapshots:
                        s = snapshots[0]
                        return {"price": float(s.close), "price_change": float(s.change_price),
                                "price_change_pct": float(s.change_rate),
                                "source": "shioaji", "currency": "TWD"}
                result = await loop.run_in_executor(None, _get)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Shioaji TWII failed: {e}")
        return await self._get_yahoo_quote("^TWII")

    async def _get_txf_quote(self) -> Dict:
        if self.shioaji and self.shioaji.is_connected:
            cached = self.shioaji.get_cached_quote("TXFR1")
            if cached:
                return cached
        txf = await self._get_yahoo_quote("TXF=F")
        if txf.get("price") and txf["price"] > 0:
            txf["note"] = "備援報價（永豐API未連線）"
            return txf
        result = await self._get_yahoo_quote("^TWII")
        result["note"] = "⚠ 顯示加權指數（台指期備援失敗）"
        return result

    async def _get_us_stock_quote(self, ticker: str) -> Dict:
        result = await self._get_twelve_data_single(ticker)
        if "error" not in result:
            return result
        return await self._get_yahoo_quote(ticker)

    async def _get_crypto_quote(self, ticker: str) -> Dict:
        coin_map = {"BTC": "bitcoin", "ETH": "ethereum",
                    "BNB": "binancecoin", "SOL": "solana"}
        coin_id = coin_map.get(ticker.upper(), ticker.lower())
        try:
            resp = await self.http.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd",
                        "include_24hr_change": "true", "include_24hr_vol": "true"},
                headers={"Accept": "application/json"}
            )
            data = resp.json()
            if coin_id in data:
                d = data[coin_id]
                return {"ticker": ticker, "price": d.get("usd"),
                        "price_change_pct": d.get("usd_24h_change"),
                        "volume": d.get("usd_24h_vol"),
                        "source": "coingecko", "currency": "USD",
                        "fetched_at": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            logger.error(f"CoinGecko failed {ticker}: {e}")
        return {"ticker": ticker, "error": "CoinGecko failed"}

    async def _get_gold_quote(self) -> Dict:
        result = await self._get_yahoo_quote("GC=F")
        if result.get("price") and result["price"] > 0:
            result["source"] = "yahoo_gold"
            return result
        td = await self._get_twelve_data_single("XAU/USD")
        if "error" not in td:
            return td
        return {"ticker": "XAU", "error": "Gold price unavailable"}

    async def _get_twelve_data_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        if not TWELVE_DATA_KEY:
            return {s: {"error": "No API key"} for s in symbols}
        symbol_str = ",".join(symbols)
        try:
            resp = await self.http.get(
                "https://api.twelvedata.com/quote",
                params={"symbol": symbol_str, "apikey": TWELVE_DATA_KEY}
            )
            raw = resp.json()
            if len(symbols) == 1:
                raw = {symbols[0]: raw}
            result = {}
            for sym, data in raw.items():
                if "code" in data or (isinstance(data.get("status"), str) and data["status"] == "error"):
                    result[sym] = {"error": data.get("message", "error")}
                    continue
                try:
                    price = float(data.get("close") or data.get("price") or 0)
                    prev  = float(data.get("previous_close") or price)
                    change = price - prev
                    change_pct = (change / prev * 100) if prev else 0
                    result[sym] = {"ticker": sym, "price": price,
                                   "price_change": change, "price_change_pct": change_pct,
                                   "open": float(data.get("open") or 0),
                                   "high": float(data.get("high") or 0),
                                   "low":  float(data.get("low") or 0),
                                   "volume": int(data.get("volume") or 0),
                                   "prev_close": prev, "source": "twelve_data",
                                   "currency": "USD",
                                   "fetched_at": datetime.now(timezone.utc).isoformat()}
                except Exception as e:
                    result[sym] = {"error": str(e)}
            return result
        except Exception as e:
            logger.error(f"Twelve Data batch failed {symbols}: {e}")
            return {s: {"error": str(e)} for s in symbols}

    async def _get_twelve_data_single(self, symbol: str) -> Dict:
        batch = await self._get_twelve_data_batch([symbol])
        return batch.get(symbol, {"error": "No data"})

    async def get_historical_kbars(self, ticker: str, start: str, end: str,
                                    interval: str = "1day") -> List[Dict]:
        if TW_STOCK_PATTERN(ticker) and self.shioaji and self.shioaji.is_connected:
            result = await self.shioaji.get_kbars(ticker, start, end)
            if result:
                return result
        if not TWELVE_DATA_KEY:
            return []
        symbol = f"{ticker}.TW" if TW_STOCK_PATTERN(ticker) else ticker
        try:
            resp = await self.http.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol": symbol, "interval": interval,
                        "start_date": start, "end_date": end,
                        "apikey": TWELVE_DATA_KEY, "outputsize": 5000}
            )
            data = resp.json()
            if "values" in data:
                return [{"ts": item["datetime"],
                         "open": float(item["open"]), "high": float(item["high"]),
                         "low":  float(item["low"]),  "close": float(item["close"]),
                         "volume": int(item.get("volume") or 0)}
                        for item in reversed(data["values"])]
        except Exception as e:
            logger.error(f"Historical data failed {ticker}: {e}")
        return []

    async def _get_yahoo_quote(self, symbol: str) -> Dict:
        try:
            resp = await self.http.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                                       "Chrome/120.0.0.0 Safari/537.36"}
            )
            data = resp.json()
            result_list = data.get("chart", {}).get("result", [])
            if result_list:
                meta = result_list[0].get("meta", {})
                price = meta.get("regularMarketPrice") or 0
                prev = (meta.get("chartPreviousClose") or
                        meta.get("previousClose") or
                        meta.get("regularMarketPreviousClose") or price)
                change = price - prev
                change_pct = (change / prev * 100) if prev else 0
                return {"ticker": symbol, "price": price,
                        "price_change": round(change, 4),
                        "price_change_pct": round(change_pct, 4),
                        "open":   meta.get("regularMarketOpen") or 0,
                        "high":   meta.get("regularMarketDayHigh") or 0,
                        "low":    meta.get("regularMarketDayLow") or 0,
                        "volume": meta.get("regularMarketVolume") or 0,
                        "source": "yahoo_finance",
                        "currency": meta.get("currency", "USD"),
                        "fetched_at": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            logger.error(f"Yahoo Finance failed {symbol}: {e}")
        return {"ticker": symbol, "error": "Yahoo Finance failed"}

    async def _get_exchange_rate(self, from_cur: str, to_cur: str) -> Dict:
        if EXCHANGE_RATE_KEY:
            try:
                resp = await self.http.get(
                    f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_KEY}/pair/{from_cur}/{to_cur}"
                )
                data = resp.json()
                if data.get("result") == "success":
                    return {"rate": data["conversion_rate"], "change_pct": None}
            except Exception as e:
                logger.error(f"ExchangeRate-API failed {from_cur}/{to_cur}: {e}")
        td = await self._get_twelve_data_single(f"{from_cur}/{to_cur}")
        if "error" not in td:
            return {"rate": td.get("price"), "change_pct": td.get("price_change_pct")}
        yahoo = await self._get_yahoo_quote(f"{from_cur}{to_cur}=X")
        if yahoo.get("price"):
            return {"rate": yahoo["price"], "change_pct": yahoo.get("price_change_pct")}
        return {"rate": None, "error": "All exchange rate sources failed"}
