# ===== ULTIMATE TRADING BOT =====
import os
import numpy as np
import pandas as pd
import yfinance as yf
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from telegram import Bot
from telegram.error import TelegramError
import time
import asyncio

# ===== CONFIGURATION =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7576447919:AAF8MLrf62I80LxWPy2RXsr5jQdqEdsbfBU")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "466184052")
TIME_FRAME = '1h'
SCAN_INTERVAL = 300  # 5 minutes

# ===== MARKET CONFIGURATION =====
MARKETS = {
    # Forex
    'EURUSD=X': {'name': 'EUR/USD', 'period': '60d'},
    'GBPUSD=X': {'name': 'GBP/USD', 'period': '60d'},
    'USDJPY=X': {'name': 'USD/JPY', 'period': '60d'},
    'AUDUSD=X': {'name': 'AUD/USD', 'period': '60d'},
    
    # Crypto
    'BTC-USD': {'name': 'BTC/USD', 'period': '60d'},
    
    # Commodities
    'GC=F': {'name': 'Gold (XAU/USD)', 'period': '60d'},
    'CL=F': {'name': 'Crude Oil (USOIL)', 'period': '60d'},
    
    # Indices
    '^DJI': {'name': 'US30', 'period': '60d'}
}

# ===== IMPROVED DATA FETCHING =====
def fetch_data(symbol, period):
    """Robust data fetching with retry logic"""
    for attempt in range(3):
        try:
            df = yf.download(
                tickers=symbol,
                period=period,
                interval=TIME_FRAME,
                progress=False,
                auto_adjust=True,
                threads=True
            )
            if len(df) >= 200:  # Minimum for reliable indicators
                df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                df.columns = ['open', 'high', 'low', 'close', 'volume']
                return df.dropna()
            time.sleep(2)
        except Exception as e:
            print(f"Attempt {attempt+1} failed for {symbol}: {str(e)[:100]}")
            time.sleep(5)
    return None

# ===== FIXED INDICATOR CALCULATION =====
def calculate_indicators(df, market_name):
    """Reliable technical indicators"""
    try:
        # Clean data
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        if len(df) < 200:
            return None
        
        # Calculate indicators
        close = df['close']
        df['ma50'] = SMAIndicator(close, window=50).sma_indicator()
        df['ma200'] = SMAIndicator(close, window=200).sma_indicator()
        df['rsi'] = RSIIndicator(close, window=14).rsi()
        df['atr'] = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=close,
            window=14
        ).average_true_range()
        
        print(f"{market_name.ljust(12)} | "
              f"Price: {df['close'].iloc[-1]:.2f} | "
              f"MA50: {df['ma50'].iloc[-1]:.2f} | "
              f"MA200: {df['ma200'].iloc[-1]:.2f} | "
              f"RSI: {df['rsi'].iloc[-1]:.2f}")
              
        return df.dropna()
    except Exception as e:
        print(f"Indicator error for {market_name}: {str(e)[:100]}")
        return None

# ===== SIGNAL GENERATION =====
def check_signals(df, market_name):
    """Enhanced signal detection"""
    try:
        if df is None or len(df) < 2:
            return False, False, None, None
            
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Trend condition
        trend_up = current['ma50'] > current['ma200']
        trend_down = current['ma50'] < current['ma200']
        
        # RSI condition
        rsi_ok = 30 < current['rsi'] < 70
        
        # Candlestick pattern
        bull_engulf = (current['close'] > current['open']) and \
                     (current['open'] < previous['close']) and \
                     (current['close'] > previous['open'])
        
        bear_engulf = (current['close'] < current['open']) and \
                     (current['open'] > previous['close']) and \
                     (current['close'] < previous['open'])
        
        return (
            trend_up and rsi_ok and bull_engulf,
            trend_down and rsi_ok and bear_engulf,
            current['close'],
            current['atr']
        )
    except Exception as e:
        print(f"Signal error for {market_name}: {str(e)[:100]}")
        return False, False, None, None

# ===== TELEGRAM ALERTS =====
async def send_alert(bot, market_name, signal, levels):
    """Professional alert formatting"""
    try:
        emoji = "🚀" if signal == "BUY" else "⚠️"
        message = (
            f"{emoji} *{signal} ALERT* {emoji}\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"• **Market:** {market_name}\n"
            f"• **Entry Price:** `{levels['entry']:.5f}`\n"
            f"• **Stop Loss:** `{levels['sl']:.5f}`\n"
            f"• **Take Profit 1:** `{levels['tp1']:.5f}` (1:1)\n"
            f"• **Take Profit 2:** `{levels['tp2']:.5f}` (1:2)\n"
            f"• **Take Profit 3:** `{levels['tp3']:.5f}` (1:3)\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"_MA50/200 Cross | RSI Filtered_"
        )
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Alert failed: {str(e)[:100]}")

# ===== MAIN BOT LOGIC =====
async def trading_cycle(bot):
    """Complete market analysis"""
    start_time = time.time()
    print(f"\n🔍 Scanning {len(MARKETS)} markets at {pd.Timestamp.now()}")
    
    for symbol, config in MARKETS.items():
        try:
            # Get market data
            df = fetch_data(symbol, config['period'])
            if df is None:
                continue
                
            # Calculate indicators
            df = calculate_indicators(df, config['name'])
            if df is None:
                continue
                
            # Check signals
            buy, sell, price, atr = check_signals(df, config['name'])
            
            if buy or sell:
                levels = {
                    'entry': price,
                    'sl': price - (atr * 0.5) if buy else price + (atr * 0.5),
                    'tp1': price + (atr * 1) if buy else price - (atr * 1),
                    'tp2': price + (atr * 2) if buy else price - (atr * 2),
                    'tp3': price + (atr * 3) if buy else price - (atr * 3)
                }
                await send_alert(bot, config['name'], "BUY" if buy else "SELL", levels)
                
        except Exception as e:
            print(f"Error processing {config['name']}: {str(e)[:100]}")
    
    print(f"✅ Scan completed in {time.time() - start_time:.2f} seconds")

async def main():
    """Run bot continuously"""
    bot = Bot(token=TELEGRAM_TOKEN)
    print(f"\n⚡ Trading Bot Activated - Tracking {len(MARKETS)} Markets")
    print("⚙️ Configuration:")
    print(f"- Timeframe: {TIME_FRAME}")
    print(f"- Scan Interval: {SCAN_INTERVAL//60} minutes")
    print("- Strategy: MA50/200 Cross + RSI + Engulfing")
    
    while True:
        try:
            await trading_cycle(bot)
            await asyncio.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"🛑 Critical error: {str(e)[:100]}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    print("Starting Ultimate Trading Bot...")
    asyncio.run(main())