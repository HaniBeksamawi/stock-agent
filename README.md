# 🤖 Stock Agent FINAL — Setup & Deployment Guide

## What this bot does
- Scans 40 trending stocks continuously
- Scores each stock 0-10 based on price momentum, RSI, volume, MA, and news
- Buys when momentum score >= 5
- Sizes trades based on score: higher score = bigger trade (min $2,000)
- Holds max 10 positions at once
- If all 10 slots full and a better stock is found → swaps the worst one
- Sells at +5% profit or -2.5% stop loss
- Live dashboard you can view from anywhere
- Manual buy/sell button on dashboard

---

## Files in this zip
- bot.py — the trading bot
- dashboard.py — the web dashboard
- start.py — starts both bot + dashboard together
- requirements.txt — Python dependencies
- Procfile — tells Railway how to run it
- README.md — this file

---

## Step 1 — Create GitHub account
1. Go to https://github.com and sign up (free)

---

## Step 2 — Create a new repository
1. Click "+" top right → "New repository"
2. Name it: stock-agent
3. Set to Public
4. Click "Create repository"
5. Click "uploading an existing file"
6. Drag ALL 6 files from this zip into the upload area
7. Click "Commit changes"

---

## Step 3 — Deploy to Railway
1. Go to https://railway.app
2. Click "Start a New Project"
3. Choose "Deploy from GitHub repo"
4. Select your stock-agent repo
5. Railway will auto-detect and start building

---

## Step 4 — Add Environment Variables on Railway
1. Click your service → "Variables" tab
2. Add these three:

| Key                  | Value                                        |
|----------------------|----------------------------------------------|
| ALPACA_API_KEY       | PKSQZQMDJ3XE54T6EROABF3WGW                  |
| ALPACA_SECRET_KEY    | H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp|
| NEWS_API_KEY         | 164efb308b644a1084fd3b54226342f4             |

3. Click Deploy

---

## Step 5 — Get your dashboard URL
1. Click your service → "Settings" tab
2. Under "Domains" click "Generate Domain"
3. Open that URL in any browser — your live dashboard!

---

## Bot Logic

### Buy conditions
| Signal       | Threshold              | Points |
|--------------|------------------------|--------|
| Price change | >= 0.5% today          | +2     |
| Price change | >= 1.5% today          | +1     |
| Price change | >= 3.0% today          | +1     |
| RSI          | Between 45 and 78      | +2     |
| Volume       | >= 1.2x average        | +2     |
| Price vs MA  | Above 20-period MA     | +1     |
| Day change   | >= 1% from prev close  | +1     |
| News         | Positive headlines     | +1 bonus|
| News         | Negative headlines     | -2 penalty|

**Score >= 5 out of 10 = BUY**

### Trade sizing
| Momentum Score | % of Portfolio | Approx Amount |
|---------------|----------------|---------------|
| 3             | 3%             | ~$3,000       |
| 5             | 5%             | ~$5,000       |
| 7             | 7%             | ~$7,000       |
| 9             | 9%             | ~$9,000       |
| 10            | 10%            | ~$10,000      |
Minimum trade: $2,000

### Sell conditions
- Take profit: +5%
- Stop loss: -2.5%
- Bad news score <= -3

### Smart swap
- Max 10 positions held at once
- If full and better stock found → sells worst position and buys the new one
- Only swaps if new stock has 2+ higher momentum AND worst is in negative P&L

### Halal filter
Automatically blocks:
- Alcohol, beer, wine, spirits
- Pork, pig, swine
- Mortgage, interest-bearing finance
- Gambling, casino, betting
- Tobacco, cigarettes, vaping
- Adult entertainment
- Weapons manufacturers

---

## Market hours
Bot only trades 9:30am - 4:00pm EST (Monday - Friday)
Sleeps on weekends and after hours automatically

---

## Updating the bot
1. Make changes to files
2. Go to GitHub repo → click file → pencil icon
3. Replace content → Commit changes
4. Railway auto-redeploys in ~60 seconds
