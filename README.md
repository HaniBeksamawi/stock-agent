# 🤖 Stock Agent — Setup & Deployment Guide

## What this bot does
- Scans 30 trending stocks every 15 minutes
- Reads latest news and scores sentiment
- Checks RSI, price momentum, and volume
- Buys when 3+ signals agree
- Sells at +10% profit or -5% stop loss
- Shows a live dashboard you can view from anywhere

---

## Step 1 — Install GitHub Desktop
1. Go to https://desktop.github.com
2. Download and install it
3. Sign in with your GitHub account (create one free at github.com if needed)

---

## Step 2 — Create a GitHub Repository
1. Open GitHub Desktop
2. Click "File" → "New Repository"
3. Name it: `stock-agent`
4. Choose a local folder (e.g. your Desktop)
5. Click "Create Repository"
6. Click "Publish Repository" (top bar) → make sure "Keep this code private" is checked → Publish

---

## Step 3 — Add the bot files
1. Open the folder GitHub Desktop created (right-click repo → "Show in Finder/Explorer")
2. Copy ALL these files into that folder:
   - bot.py
   - dashboard.py
   - start.py
   - requirements.txt
   - Procfile
3. Back in GitHub Desktop you'll see the files appear
4. At the bottom left, type "Initial commit" in the Summary box
5. Click "Commit to main"
6. Click "Push origin" (top bar)

---

## Step 4 — Deploy to Railway
1. Go to https://railway.app
2. Click "Start a New Project"
3. Choose "Deploy from GitHub repo"
4. Select your `stock-agent` repo
5. Railway will detect it automatically

---

## Step 5 — Add Environment Variables on Railway
1. In your Railway project, click your service
2. Click the "Variables" tab
3. Add these one by one:

| Key | Value |
|-----|-------|
| ALPACA_API_KEY | PKSQZQMDJ3XE54T6EROABF3WGW |
| ALPACA_SECRET_KEY | H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp |
| NEWS_API_KEY | 164efb308b644a1084fd3b54226342f4 |

4. Click "Deploy" — Railway will restart with the keys

---

## Step 6 — Get your Dashboard URL
1. In Railway, click your service → "Settings" tab
2. Under "Domains" click "Generate Domain"
3. You'll get a URL like: `https://stock-agent-xxxx.railway.app`
4. Open that URL in any browser — that's your live dashboard!

---

## What you'll see on the dashboard
- 💰 Portfolio value (updates every 15s)
- 💵 Cash available
- 📈 Open positions with live P&L
- 📋 Activity log showing every decision the bot makes

---

## Bot Logic Summary
| Signal | Required |
|--------|----------|
| News score ≥ 2 | ✅ Positive headlines |
| Price up ≥ 2% today | ✅ Momentum |
| RSI between 50-72 | ✅ Not overbought |
| Volume 1.5x average | ✅ People piling in |
| Above 20-period MA | ✅ Uptrend confirmed |

**Buy when 3+ signals agree. Sell at +10% or -5%.**
