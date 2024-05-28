# Intraday Cryptocurrency Trading Bot

## Overview

This project implements an intraday cryptocurrency trading bot that utilizes various trading strategies to generate buy and sell signals on USDT pairs listed on the Binance exchange. The bot is designed to execute trades based on predefined strategies and capture necessary data in a SQLite database.

## Features

- Fetches real-time data for USDT pairs from Binance without requiring API keys.
- Implements multiple trading strategies, including:
  - Simple Strategy: Buy signals are generated based on a combination of moving averages, RSI, MACD, Bollinger Bands, and ADX indicators.
  - Moving Average Crossover Strategy: Buy signals are generated when a shorter-term moving average crosses above a longer-term moving average, and sell signals are generated when the opposite occurs.
  - Stochastic Oscillator Strategy: Buy signals are generated when the stochastic oscillator crosses above the oversold level, and sell signals are generated when it crosses below the overbought level.
  - Volume Weighted Average Price (VWAP) Strategy: Buy signals are generated when the current price is below VWAP, and sell signals are generated when the current price is above VWAP.
  - Breakout Strategy: Buy signals are generated when the price breaks above a resistance level, and sell signals are generated when the price breaks below a support level.
- Captures necessary data, including open, high, low, close prices, volume, and various technical indicators, in a SQLite database.
- Provides detailed logging and messages for each trade and strategy execution.

## Dependencies

- Python 3.x
- SQLite
- pandas
- requests
- TA-Lib (Technical Analysis Library)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your_username/crypto-trading-bot.git
   ```

2. Navigate to the project directory:

   ```bash
   cd crypto-trading-bot
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a SQLite database named `crypto_trading.db`.

## Configuration

No API keys are required as the bot fetches data from Binance's public endpoints.

## Usage

To run the trading bot, execute the `main.py` script:

```bash
python main.py
```

The bot will execute the predefined strategies on all available USDT pairs and generate buy/sell signals accordingly. Detailed logs and messages will be displayed in the terminal.

## Customization

You can customize the bot by:

- Adding or modifying trading strategies in the `main.py` script.
- Adjusting strategy parameters and conditions based on your preferences and risk appetite.
- Extending the functionality to include additional indicators or trading signals.

## Disclaimer

This project is for educational and informational purposes only. Cryptocurrency trading involves significant risk, and past performance is not indicative of future results. Always conduct thorough research and consult with a financial advisor before making any investment decisions.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

Special thanks to Binance for providing access to their public API and supporting cryptocurrency trading development efforts.3
