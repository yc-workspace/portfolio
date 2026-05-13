import os
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ShioajiService:
    """
    Wrapper for Shioaji API (永豐證券)
    Uses on-demand connection: connect when user is active, disconnect when idle
    """
    
    def __init__(self):
        self.api = None
        self.is_connected = False
        self._api_key = os.getenv("SHIOAJI_API_KEY")
        self._secret_key = os.getenv("SHIOAJI_SECRET_KEY")
        self._subscribed_tickers = set()
        self._quote_cache: Dict[str, Any] = {}
        self._last_quote_time: Dict[str, datetime] = {}

    @property
    def available(self) -> bool:
        """Check if Shioaji credentials are configured"""
        return bool(self._api_key and self._secret_key)

    async def login(self) -> bool:
        """Connect to Shioaji API"""
        if not self.available:
            logger.info("Shioaji credentials not configured, skipping")
            return False
        
        if self.is_connected:
            logger.info("Shioaji already connected")
            return True

        try:
            import shioaji as sj
            
            loop = asyncio.get_event_loop()
            
            def _login():
                api = sj.Shioaji()
                api.login(
                    api_key=self._api_key,
                    secret_key=self._secret_key,
                    subscribe_trade=False,  # We don't need trade updates
                    contracts_timeout=10000,
                )
                return api
            
            self.api = await loop.run_in_executor(None, _login)
            self.is_connected = True
            logger.info("Shioaji login successful")
            
            # Set up quote callbacks
            self._setup_callbacks()
            return True
            
        except Exception as e:
            logger.error(f"Shioaji login failed: {e}")
            self.is_connected = False
            return False

    def _setup_callbacks(self):
        """Set up quote update callbacks"""
        if not self.api:
            return
        
        try:
            import shioaji as sj
            from shioaji import TickSTKv1, TickFOPv1, Exchange
            
            @self.api.on_tick_stk_v1()
            def on_stock_tick(exchange: Exchange, tick: TickSTKv1):
                self._quote_cache[tick.code] = {
                    "ticker": tick.code,
                    "price": float(tick.close),
                    "price_change": float(tick.price_chg),
                    "price_change_pct": float(tick.pct_chg),
                    "volume": tick.total_volume,
                    "high": float(tick.high),
                    "low": float(tick.low),
                    "open": float(tick.open),
                    "source": "shioaji",
                    "currency": "TWD",
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
                self._last_quote_time[tick.code] = datetime.now(timezone.utc)
            
            @self.api.on_tick_fop_v1()
            def on_futures_tick(exchange: Exchange, tick: TickFOPv1):
                self._quote_cache[tick.code] = {
                    "ticker": tick.code,
                    "price": float(tick.close),
                    "price_change": float(tick.price_chg),
                    "price_change_pct": float(tick.pct_chg),
                    "volume": tick.total_volume,
                    "high": float(tick.high),
                    "low": float(tick.low),
                    "open": float(tick.open),
                    "source": "shioaji",
                    "currency": "TWD",
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to setup Shioaji callbacks: {e}")

    async def subscribe_ticker(self, ticker: str, is_futures: bool = False):
        """Subscribe to real-time quote for a ticker"""
        if not self.is_connected or not self.api:
            return False
        
        try:
            import shioaji as sj
            loop = asyncio.get_event_loop()
            
            def _subscribe():
                if is_futures:
                    # Taiwan futures - use R1 for front month
                    contract = self.api.Contracts.Futures.TXF.TXFR1
                else:
                    contract = self.api.Contracts.Stocks[ticker]
                
                self.api.quote.subscribe(
                    contract,
                    quote_type=sj.constant.QuoteType.Tick,
                    version=sj.constant.QuoteVersion.v1
                )
            
            await loop.run_in_executor(None, _subscribe)
            self._subscribed_tickers.add(ticker)
            logger.info(f"Subscribed to {ticker}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {ticker}: {e}")
            return False

    async def get_snapshot(self, tickers: list) -> Dict[str, Any]:
        """Get current snapshot prices for multiple tickers at once"""
        if not self.is_connected or not self.api:
            return {}
        
        try:
            import shioaji as sj
            loop = asyncio.get_event_loop()
            
            def _snapshot():
                contracts = [self.api.Contracts.Stocks[t] for t in tickers if t.isdigit() or t.isalpha()]
                snapshots = self.api.snapshots(contracts)
                result = {}
                for s in snapshots:
                    result[s.code] = {
                        "ticker": s.code,
                        "price": float(s.close),
                        "price_change": float(s.change_price),
                        "price_change_pct": float(s.change_rate),
                        "volume": s.total_volume,
                        "open": float(s.open),
                        "high": float(s.high),
                        "low": float(s.low),
                        "source": "shioaji",
                        "currency": "TWD",
                        "fetched_at": datetime.now(timezone.utc).isoformat()
                    }
                return result
            
            return await loop.run_in_executor(None, _snapshot)
            
        except Exception as e:
            logger.error(f"Shioaji snapshot failed: {e}")
            return {}

    async def get_kbars(self, ticker: str, start: str, end: str) -> list:
        """Get historical K-bar data"""
        if not self.is_connected or not self.api:
            return []
        
        try:
            import shioaji as sj
            loop = asyncio.get_event_loop()
            
            def _kbars():
                contract = self.api.Contracts.Stocks[ticker]
                kbars = self.api.kbars(contract=contract, start=start, end=end)
                import pandas as pd
                df = pd.DataFrame({**kbars})
                df['ts'] = pd.to_datetime(df['ts'])
                return df.to_dict(orient='records')
            
            return await loop.run_in_executor(None, _kbars)
            
        except Exception as e:
            logger.error(f"Shioaji kbars failed for {ticker}: {e}")
            return []

    def get_cached_quote(self, ticker: str) -> Optional[Dict]:
        """Get quote from in-memory cache (populated by subscriptions)"""
        return self._quote_cache.get(ticker)

    async def logout(self):
        """Disconnect from Shioaji"""
        if self.is_connected and self.api:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.api.logout)
                logger.info("Shioaji logged out")
            except Exception as e:
                logger.error(f"Shioaji logout error: {e}")
            finally:
                self.is_connected = False
                self.api = None
                self._subscribed_tickers.clear()
                self._quote_cache.clear()
