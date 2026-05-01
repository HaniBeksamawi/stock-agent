# Stock Agent

## Files
- bot.py — trading bot
- dashboard.py — web dashboard
- start.py — runs both together
- requirements.txt — dependencies
- Procfile — Railway config

## How it works
- Scans 40 stocks continuously
- Scores each stock 0-10 (price, RSI, volume, MA, news)
- Buys when score >= 5
- Min $2,000 per trade, 5% of portfolio
- Max 10 positions at once
- Swaps worst position if better stock found
- Sells at +5% profit or -2.5% stop loss
- Halal filter always on

## Environment Variables (add in Railway)
- ALPACA_API_KEY
- ALPACA_SECRET_KEY
- NEWS_API_KEY

## Market hours
9:30am - 4:00pm EST, Mon-Fri only
