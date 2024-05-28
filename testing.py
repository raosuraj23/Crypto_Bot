import sqlite3
import requests
import pandas as pd
from datetime import datetime
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.trend import ADXIndicator
import time

# Fetch USDT pairs from Binance without API keys
def fetch_usdt_pairs():
    try:
        response = requests.get('https://api.binance.com/api/v3/ticker/price')
        if response.status_code == 200:
            symbols = [item['symbol'] for item in response.json() if item['symbol'].endswith('USDT')]
            return symbols
        else:
            print(f"Failed to fetch symbols. Status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

def fetch_crypto_data(symbol, interval='1h'):
    try:
        # Fetch real-time data for the specified symbol
        response = requests.get(f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}')
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f'Failed to fetch data for symbol: {symbol} Status code: {response.status_code}')
            return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def create_tables(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_data (
            symbol TEXT,
            timestamp DATETIME,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            quote_asset_volume REAL,
            number_of_trades INTEGER,
            taker_buy_base_asset_volume REAL,
            taker_buy_quote_asset_volume REAL,
            ignore INTEGER,
            ema_short REAL,
            ema_long REAL,
            rsi REAL,
            macd REAL,
            signal REAL,
            bb_high REAL,
            bb_low REAL,
            bb_mavg REAL,
            sma_50 REAL,
            sma_200 REAL,
            obv REAL,
            adx REAL,
            PRIMARY KEY (symbol, timestamp)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            entry_timestamp DATETIME,
            entry_price REAL,
            quantity REAL,
            side TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            entry_timestamp DATETIME,
            exit_timestamp DATETIME,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            profit_loss REAL,
            profit_percent REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_results (
            id INTEGER PRIMARY KEY,
            strategy TEXT,
            symbol TEXT,
            entry_timestamp DATETIME,
            exit_timestamp DATETIME,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            profit_loss REAL,
            profit_percent REAL
        )
    ''')

    conn.commit()

def insert_klines_to_db(conn, symbol, klines):
    cursor = conn.cursor()
    for kline in klines:
        timestamp = datetime.fromtimestamp(kline[0] / 1000.0)
        cursor.execute('''
            INSERT OR IGNORE INTO raw_data (
                symbol, timestamp, open, high, low, close, volume, quote_asset_volume, number_of_trades,
                taker_buy_base_asset_volume, taker_buy_quote_asset_volume, ignore
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol,
            timestamp,
            float(kline[1]),
            float(kline[2]),
            float(kline[3]),
            float(kline[4]),
            float(kline[5]),
            float(kline[7]),
            int(kline[8]),
            float(kline[9]),
            float(kline[10]),
            int(kline[11])
        ))
    conn.commit()

def calculate_indicators(conn, symbol):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, close, high, low, volume
        FROM raw_data
        WHERE symbol = ?
        ORDER BY timestamp ASC
    ''', (symbol,))
    rows = cursor.fetchall()

    if len(rows) > 0:
        df = pd.DataFrame(rows, columns=['timestamp', 'close', 'high', 'low', 'volume'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])

        ema_short = EMAIndicator(close=df['close'], window=12).ema_indicator()
        ema_long = EMAIndicator(close=df['close'], window=26).ema_indicator()
        rsi = RSIIndicator(close=df['close'], window=14).rsi()
        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9).macd_diff()
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        bb_high = bb.bollinger_hband()
        bb_low = bb.bollinger_lband()
        sma_50 = df['close'].rolling(window=50).mean()
        sma_200 = df['close'].rolling(window=200).mean()
        obv = (df['volume'] * ((df['close'].diff() > 0) * 2 - 1)).cumsum()
        adx = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()

        df['ema_short'] = ema_short
        df['ema_long'] = ema_long
        df['rsi'] = rsi
        df['macd'] = macd
        df['bb_high'] = bb_high
        df['bb_low'] = bb_low
        df['sma_50'] = sma_50
        df['sma_200'] = sma_200
        df['obv'] = obv
        df['adx'] = adx

        df.dropna(inplace=True)
        
        for row in df.itertuples():
            cursor.execute('''
                UPDATE raw_data
                SET ema_short=?, ema_long=?, rsi=?, macd=?, bb_high=?, bb_low=?, sma_50=?, sma_200=?, obv=?, adx=?
                WHERE symbol=? AND timestamp=?
            ''', (row.ema_short, row.ema_long, row.rsi, row.macd, row.bb_high, row.bb_low, row.sma_50, row.sma_200, row.obv, row.adx, symbol, row.timestamp))
            conn.commit()

def execute_strategy(conn, strategy_name, strategy_func):
    cursor = conn.cursor()
    usdt_pairs = fetch_usdt_pairs()
    for symbol in usdt_pairs:
        klines = fetch_crypto_data(symbol)
        if klines:
            insert_klines_to_db(conn, symbol, klines)
            calculate_indicators(conn, symbol)
            strategy_func(conn, symbol, strategy_name)
            
def ema_crossover_strategy(conn, symbol, strategy_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT symbol, timestamp, close, ema_short, ema_long
        FROM raw_data
        WHERE symbol = ?
        ORDER BY timestamp ASC
    ''', (symbol,))
    rows = cursor.fetchall()

    balance = 1000  # Starting balance
    position = None

    for row in rows:
        symbol, timestamp, close, ema_short, ema_long = row
        
        # Check if any indicator is None
        if any(x is None for x in [ema_short, ema_long]):
            continue  # Skip this iteration if any indicator is None

        # Define buy and sell conditions based on indicators
        buy_condition = (ema_short > ema_long)
        sell_condition = (ema_short < ema_long)

        if buy_condition and balance >= 10 and not position:
            quantity = 10 / close
            cursor.execute('''
                INSERT INTO positions (symbol, entry_timestamp, entry_price, quantity, side)
                VALUES (?, ?, ?, ?, 'BUY')
            ''', (symbol, timestamp, close, quantity))
            conn.commit()
            position = (symbol, timestamp, close, quantity)
            balance -= 10
            print(f"Buy signal for {symbol} at {timestamp} at price {close}")

        if sell_condition and position:
            entry_symbol, entry_timestamp, entry_price, quantity = position
            profit_loss = (close - entry_price) * quantity
            profit_percent = (profit_loss / (entry_price * quantity)) * 100
            balance += (quantity * close)

            cursor.execute('''
                INSERT INTO trades (symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            cursor.execute('''
                INSERT INTO strategy_results (strategy, symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            print(f"Sell signal for {symbol} at {timestamp} at price {close} with P&L: {profit_loss}, {profit_percent}%")
            position = None

def rsi_overbought_oversold_strategy(conn, symbol, strategy_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT symbol, timestamp, close, rsi
        FROM raw_data
        WHERE symbol = ?
        ORDER BY timestamp ASC
    ''', (symbol,))
    rows = cursor.fetchall()

    balance = 1000  # Starting balance
    position = None

    for row in rows:
        symbol, timestamp, close, rsi = row
        
        # Check if any indicator is None
        if rsi is None:
            continue  # Skip this iteration if RSI is None

        # Define buy and sell conditions based on RSI
        buy_condition = (rsi < 30)
        sell_condition = (rsi > 70)

        if buy_condition and balance >= 10 and not position:
            quantity = 10 / close
            cursor.execute('''
                INSERT INTO positions (symbol, entry_timestamp, entry_price, quantity, side)
                VALUES (?, ?, ?, ?, 'BUY')
            ''', (symbol, timestamp, close, quantity))
            conn.commit()
            position = (symbol, timestamp, close, quantity)
            balance -= 10
            print(f"Buy signal for {symbol} at {timestamp} at price {close}")

        if sell_condition and position:
            entry_symbol, entry_timestamp, entry_price, quantity = position
            profit_loss = (close - entry_price) * quantity
            profit_percent = (profit_loss / (entry_price * quantity)) * 100
            balance += (quantity * close)

            cursor.execute('''
                INSERT INTO trades (symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            cursor.execute('''
                INSERT INTO strategy_results (strategy, symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            print(f"Sell signal for {symbol} at {timestamp} at price {close} with P&L: {profit_loss}, {profit_percent}%")
            position = None

def simple_strategy(conn, symbol, strategy_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT symbol, timestamp, close, ema_short, ema_long, rsi, macd, bb_high, bb_low, sma_50, sma_200, obv, adx
        FROM raw_data
        WHERE symbol = ?
        ORDER BY timestamp ASC
    ''', (symbol,))
    rows = cursor.fetchall()

    balance = 1000  # Starting balance
    position = None

    for row in rows:
        symbol, timestamp, close, ema_short, ema_long, rsi, macd, bb_high, bb_low, sma_50, sma_200, obv, adx = row
        
        # Check if any indicator is None
        if any(x is None for x in [ema_short, ema_long, rsi, macd, bb_high, bb_low, sma_50, sma_200, obv, adx]):
            continue  # Skip this iteration if any indicator is None

        # Define buy and sell conditions based on indicators
        buy_condition = (ema_short > ema_long) and (rsi < 30) and (macd > 0) and (close > bb_low) and (adx > 25)
        sell_condition = (ema_short < ema_long) and (rsi > 70) and (macd < 0) and (close < bb_high) and (adx > 25)

        if buy_condition and balance >= 10 and not position:
            quantity = 10 / close
            cursor.execute('''
                INSERT INTO positions (symbol, entry_timestamp, entry_price, quantity, side)
                VALUES (?, ?, ?, ?, 'BUY')
            ''', (symbol, timestamp, close, quantity))
            conn.commit()
            position = (symbol, timestamp, close, quantity)
            balance -= 10
            print(f"Buy signal for {symbol} at {timestamp} at price {close}")

        if sell_condition and position:
            entry_symbol, entry_timestamp, entry_price, quantity = position
            profit_loss = (close - entry_price) * quantity
            profit_percent = (profit_loss / (entry_price * quantity)) * 100
            balance += (quantity * close)

            cursor.execute('''
                INSERT INTO trades (symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            cursor.execute('''
                INSERT INTO strategy_results (strategy, symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            print(f"Sell signal for {symbol} at {timestamp} at price {close} with P&L: {profit_loss}, {profit_percent}%")
            position = None

def stochastic_oscillator_strategy(conn, symbol, strategy_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT symbol, timestamp, close, high, low
        FROM raw_data
        WHERE symbol = ?
        ORDER BY timestamp ASC
    ''', (symbol,))
    rows = cursor.fetchall()

    balance = 1000  # Starting balance
    position = None

    for row in rows:
        symbol, timestamp, close, high, low = row

        # Calculate stochastic oscillator
        if len(rows) >= 14:
            close_prices = [r[2] for r in rows[:14]]
            stochastic_value = (close - min(close_prices)) / (max(close_prices) - min(close_prices)) * 100

            # Define buy and sell conditions based on stochastic oscillator
            buy_condition = (stochastic_value < 20)
            sell_condition = (stochastic_value > 80)

            if buy_condition and balance >= 10 and not position:
                quantity = 10 / close
                cursor.execute('''
                    INSERT INTO positions (symbol, entry_timestamp, entry_price, quantity, side)
                    VALUES (?, ?, ?, ?, 'BUY')
                ''', (symbol, timestamp, close, quantity))
                conn.commit()
                position = (symbol, timestamp, close, quantity)
                balance -= 10
                print(f"Buy signal for {symbol} at {timestamp} at price {close}")

            if sell_condition and position:
                entry_symbol, entry_timestamp, entry_price, quantity = position
                profit_loss = (close - entry_price) * quantity
                profit_percent = (profit_loss / (entry_price * quantity)) * 100
                balance += (quantity * close)

                cursor.execute('''
                    INSERT INTO trades (symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
                conn.commit()

                cursor.execute('''
                    INSERT INTO strategy_results (strategy, symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (strategy_name, symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
                conn.commit()

                print(f"Sell signal for {symbol} at {timestamp} at price {close} with P&L: {profit_loss}, {profit_percent}%")
                position = None

def moving_average_crossover_strategy(conn, symbol, strategy_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT symbol, timestamp, close, sma_50, sma_200
        FROM raw_data
        WHERE symbol = ?
        ORDER BY timestamp ASC
    ''', (symbol,))
    rows = cursor.fetchall()

    balance = 1000  # Starting balance
    position = None

    for row in rows:
        symbol, timestamp, close, sma_50, sma_200 = row

        # Check if any indicator is None
        if any(x is None for x in [sma_50, sma_200]):
            continue  # Skip this iteration if any indicator is None

        # Define buy and sell conditions based on moving average crossover
        buy_condition = (sma_50 > sma_200)
        sell_condition = (sma_50 < sma_200)

        if buy_condition and balance >= 10 and not position:
            quantity = 10 / close
            cursor.execute('''
                INSERT INTO positions (symbol, entry_timestamp, entry_price, quantity, side)
                VALUES (?, ?, ?, ?, 'BUY')
            ''', (symbol, timestamp, close, quantity))
            conn.commit()
            position = (symbol, timestamp, close, quantity)
            balance -= 10
            print(f"Buy signal for {symbol} at {timestamp} at price {close}")

        if sell_condition and position:
            entry_symbol, entry_timestamp, entry_price, quantity = position
            profit_loss = (close - entry_price) * quantity
            profit_percent = (profit_loss / (entry_price * quantity)) * 100
            balance += (quantity * close)

            cursor.execute('''
                INSERT INTO trades (symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            cursor.execute('''
                INSERT INTO strategy_results (strategy, symbol, entry_timestamp, exit_timestamp, entry_price, exit_price, quantity, profit_loss, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, symbol, entry_timestamp, timestamp, entry_price, close, quantity, profit_loss, profit_percent))
            conn.commit()

            print(f"Sell signal for {symbol} at {timestamp} at price {close} with P&L: {profit_loss}, {profit_percent}%")
            position = None


# Main function
def main():
    conn = sqlite3.connect('crypto_trading.db')
    create_tables(conn)

    while True:
        execute_strategy(conn, "Simple Strategy", simple_strategy)
        execute_strategy(conn, "EMA Crossover Strategy", ema_crossover_strategy)
        execute_strategy(conn, "RSI Overbought/Oversold Strategy", rsi_overbought_oversold_strategy)
        execute_strategy(conn, "Moving Average Crossover Strategy", moving_average_crossover_strategy)
        execute_strategy(conn, "Stochastic Oscillator Strategy", stochastic_oscillator_strategy)
        time.sleep(60)  # Wait for 60 seconds before fetching data again
    
    conn.close()

if __name__ == "__main__":
    main()