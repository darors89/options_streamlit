# 📊 Options Strategy Builder - Streamlit

**Professional options trading analysis platform built entirely in Python.**

Complete control over calculations, transparent code, easy to deploy and maintain.

---

## ✨ Features

- **50+ Options Strategies** - From basic covered calls to advanced iron condors
- **Black-Scholes Engine** - Complete implementation with all Greeks
- **Interactive Charts** - Plotly-based payoff diagrams and volatility surfaces
- **Dual Mode:**
  - 🔒 **Offline Mode:** All calculations in-browser, no backend needed
  - 🌐 **Online Mode:** Connect to PyRofex or PyHomebroker for real market data
- **P&L Tables** - Detailed profit/loss analysis at different stock prices
- **100% Python** - All code visible, transparent, and controllable

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone or download files
cd streamlit_app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run app
streamlit run app.py
```

App will open at `http://localhost:8501`

---

## 🌐 Deploy to Streamlit Cloud (FREE)

### Option 1: GitHub (Recommended)

1. **Create GitHub repository:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin YOUR_REPO_URL
   git push -u origin main
   ```

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Select your repository
   - Main file: `app.py`
   - Click "Deploy"

3. **Done!** Your app will be live at `your-app.streamlit.app`

### Option 2: Direct Upload

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Upload all `.py` files and `requirements.txt`
3. Deploy

---

## 📁 File Structure

```
streamlit_app/
├── app.py                    # Main Streamlit app
├── blackscholes.py           # Black-Scholes calculations
├── strategies.py             # Strategy definitions
├── plotting.py               # Plotly charts
├── broker_integration.py     # PyRofex/PyHomebroker
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

---

## 🎯 How to Use

### 1. Select Strategy
- Choose from 6 categories: Basic, Spreads, Volatility, Butterflies, Condors, Advanced
- Click on any strategy to configure

### 2. Configure Parameters

**Market Parameters:**
- Stock Price
- Days to Expiration
- Volatility (%)
- Risk-Free Rate (%)

**Option Legs:**
- Each strategy shows specific legs
- Configure Strike and Premium for each
- Labels are dynamic (e.g., "Long Call - Lower Strike")

### 3. Analyze
- Click "📊 Analyze Strategy"
- View results:
  - Current P&L, Max Profit, Max Loss, Risk/Reward
  - All Greeks (Delta, Gamma, Theta, Vega, Rho)
  - Break-even points
  - Interactive payoff chart
  - P&L table
  - 3D volatility surface

---

## 🔌 Broker Integration (Optional)

### PyRofex (Derivatives)

1. **Install:**
   ```bash
   pip install pyRofex
   ```

2. **Uncomment in requirements.txt:**
   ```txt
   pyRofex>=1.2.0
   ```

3. **Connect in app:**
   - Toggle to "🌐 Online"
   - Select "PyRofex"
   - Enter credentials:
     - User
     - Password
     - Account
     - Environment (REMARKET/LIVE)
   - Click "Connect"

### PyHomebroker (Equities)

1. **Install:**
   ```bash
   pip install pyhomebroker
   ```

2. **Uncomment in requirements.txt:**
   ```txt
   pyhomebroker>=0.50
   ```

3. **Connect in app:**
   - Toggle to "🌐 Online"
   - Select "PyHomebroker"
   - Enter credentials:
     - Broker (Balanz, IOL, etc.)
     - User
     - Password
     - DNI
   - Click "Connect"

**🔒 Security:** Credentials are sent securely and NOT stored locally.

---

## 📊 Code Overview

### Black-Scholes Implementation

All calculations are transparent and verifiable:

```python
# blackscholes.py

class BlackScholes:
    @staticmethod
    def call_price(S, K, T, r, sigma, q=0):
        """Calculate European call option price"""
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        d2_val = BlackScholes.d2(S, K, T, r, sigma, q)
        
        call = S * np.exp(-q * T) * norm.cdf(d1_val) - \
               K * np.exp(-r * T) * norm.cdf(d2_val)
        return max(call, 0)
```

**Every formula is visible and can be reviewed/modified.**

### Strategy Definitions

```python
# strategies.py

STRATEGY_CONFIGS = {
    'Bull Call Spread': {
        'legs': [
            {'type': 'call', 'position': 'long', 'label': 'Long Call (Lower)'},
            {'type': 'call', 'position': 'short', 'label': 'Short Call (Upper)'}
        ]
    },
    # ... 50+ more strategies
}
```

**Easy to add new strategies or modify existing ones.**

---

## 🛠️ Customization

### Add New Strategy

Edit `strategies.py`:

```python
STRATEGY_CONFIGS['My Strategy'] = {
    'description': 'Description here',
    'has_stock': False,  # or True if uses stock
    'legs': [
        {
            'type': 'call',  # or 'put'
            'position': 'long',  # or 'short'
            'label': 'Long Call',
            'strikeLabel': 'Lower Strike'
        },
        # Add more legs...
    ]
}

# Add to category
STRATEGY_CATEGORIES[0]['strategies'].append('My Strategy')
```

### Modify Calculations

Edit `blackscholes.py` - all formulas are there and transparent.

### Customize Charts

Edit `plotting.py` - Plotly charts are fully customizable.

---

## 🎨 Dark Theme

The app uses a professional dark blue theme:
- Background: `#0a0e27` (deep navy)
- Cards: `#0d1135` (midnight blue)
- Accents: Blue, green (profit), red (loss)
- All customizable in `app.py` CSS section

---

## 📈 Advantages vs Next.js/Vercel

| Feature | Streamlit | Next.js/Vercel |
|---------|-----------|----------------|
| **Setup Time** | 5 min | 2-3 hours |
| **Code Control** | 100% visible Python | TypeScript + Python split |
| **Deploy** | 1 click | Complex (2 services) |
| **Calculations** | Direct Python | API calls to backend |
| **Debugging** | Simple (one language) | Complex (2 languages) |
| **Maintenance** | Easy | Moderate |
| **Cost** | Free | Free (but complex) |

---

## 🐛 Troubleshooting

### App won't start

```bash
# Check Python version (3.8+)
python --version

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Run with verbose
streamlit run app.py --logger.level=debug
```

### Charts not showing

- Check if `plotly` is installed: `pip install plotly`
- Clear cache: Delete `.streamlit` folder
- Refresh browser (Ctrl+Shift+R)

### Broker connection fails

- Verify credentials are correct
- Check if pyRofex/pyhomebroker is installed
- Try with REMARKET environment first
- Check console for detailed errors

---

## 📝 Next Steps

### Immediate Use:
1. ✅ Deploy to Streamlit Cloud
2. ✅ Start analyzing strategies offline
3. ✅ Review and modify calculations

### Future Enhancements:
1. **Add Broker Integration:**
   - Install pyRofex/pyhomebroker
   - Connect to real market data
   - Fetch option chains automatically

2. **Custom Strategies:**
   - Add your own strategies to `strategies.py`
   - Define custom legs and configurations

3. **Advanced Features:**
   - Excel upload for data
   - Volatility forecasting models
   - Portfolio tracking
   - Backtesting

---

## 🎓 Learning Resources

- **Black-Scholes Model:** [Wikipedia](https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model)
- **Options Greeks:** [Investopedia](https://www.investopedia.com/trading/using-the-greeks-to-understand-options/)
- **Streamlit Docs:** [docs.streamlit.io](https://docs.streamlit.io)
- **Plotly Docs:** [plotly.com/python](https://plotly.com/python/)

---

## 📞 Support

The code is fully open and transparent. All calculations are in `blackscholes.py` and can be reviewed/modified as needed.

---

## ⭐ Why This Approach?

1. **Control:** See every formula, modify as needed
2. **Transparency:** No hidden calculations
3. **Simplicity:** One language (Python), easy to understand
4. **Maintainability:** Easy to update and extend
5. **Speed:** From concept to deploy in minutes
6. **Free:** No costs, runs on Streamlit Cloud

---

## 🎉 You're Ready!

```bash
streamlit run app.py
```

**Your professional options trading platform is ready to use!** 🚀

---

Built with ❤️ in Python | Powered by Streamlit
