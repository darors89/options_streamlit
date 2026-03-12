# 🔐 SECRETS CONFIGURATION - Complete Guide

## ✅ TL;DR

**Local:**
1. Create `.streamlit/secrets.toml`
2. Add credentials
3. Add to `.gitignore`

**Streamlit Cloud:**
1. Deploy app
2. Settings → Secrets → Paste secrets
3. Done!

---

## 📁 Step 1: Create Secrets File (Local)

```bash
# In your project root
mkdir -p .streamlit
touch .streamlit/secrets.toml
```

---

## 📝 Step 2: Add Your Credentials

### Template 1: PyRofex Only

```toml
# .streamlit/secrets.toml

[rofex]
user = "YOUR_ROFEX_USERNAME"
password = "YOUR_ROFEX_PASSWORD"
account = "YOUR_ROFEX_ACCOUNT"
environment = "REMARKET"  # or "LIVE"

[defaults]
default_underlying = "GGAL"
auto_connect = true
```

### Template 2: PyHomebroker Only

```toml
# .streamlit/secrets.toml

[homebroker]
broker_id = "11"  # 11=Balanz, 121=IOL, 134=Portfolio Personal
user = "YOUR_HOMEBROKER_USERNAME"
password = "YOUR_HOMEBROKER_PASSWORD"
dni = "YOUR_DNI_NUMBER"

[defaults]
default_underlying = "GGAL"
auto_connect = true
```

### Template 3: Both (Recommended)

```toml
# .streamlit/secrets.toml

# PyRofex Credentials
[rofex]
user = "YOUR_ROFEX_USERNAME"
password = "YOUR_ROFEX_PASSWORD"
account = "YOUR_ROFEX_ACCOUNT"
environment = "REMARKET"

# PyHomebroker Credentials
[homebroker]
broker_id = "11"
user = "YOUR_HOMEBROKER_USERNAME"
password = "YOUR_HOMEBROKER_PASSWORD"
dni = "YOUR_DNI_NUMBER"

# App Defaults
[defaults]
default_underlying = "GGAL"
auto_connect = true
preferred_broker = "rofex"  # or "homebroker"
```

---

## 🚫 Step 3: Add to .gitignore

```bash
# .gitignore
.streamlit/secrets.toml
```

**⚠️ CRITICAL:** Never commit secrets to GitHub!

---

## ✅ Step 4: Verify Setup

```python
# Test in Python
import streamlit as st

# This will work if secrets.toml exists
print(st.secrets["rofex"]["user"])
```

Or run the app:

```bash
streamlit run app_enhanced.py
```

If auto-connect is enabled, you'll see:
```
🟢 Auto-connected to rofex
```

---

## 🌐 Streamlit Cloud Setup

### Step 1: Deploy Normally

```bash
git add .
git commit -m "Initial deploy"
git push
```

Deploy on https://share.streamlit.io

### Step 2: Add Secrets via Dashboard

1. Go to your deployed app
2. Click **⚙️ Settings** (top right)
3. Click **Secrets** (left menu)
4. Paste your secrets:

```toml
[rofex]
user = "YOUR_ROFEX_USERNAME"
password = "YOUR_ROFEX_PASSWORD"
account = "YOUR_ROFEX_ACCOUNT"
environment = "REMARKET"

[homebroker]
broker_id = "11"
user = "YOUR_HOMEBROKER_USERNAME"
password = "YOUR_HOMEBROKER_PASSWORD"
dni = "YOUR_DNI_NUMBER"

[defaults]
default_underlying = "GGAL"
auto_connect = true
preferred_broker = "rofex"
```

5. Click **Save**
6. App auto-redeploys with secrets

---

## 🔒 How Auto-Connect Works

### In `app_enhanced.py`:

```python
# Auto-connect on app start
if not st.session_state.broker_connected and 'rofex' in st.secrets:
    with st.spinner("Auto-connecting to broker..."):
        success, message = connect_to_broker(
            broker_type="rofex",
            credentials={
                "user": st.secrets["rofex"]["user"],
                "password": st.secrets["rofex"]["password"],
                "account": st.secrets["rofex"]["account"],
                "environment": st.secrets["rofex"]["environment"]
            }
        )
        
        if success:
            st.session_state.broker_connected = True
            st.session_state.broker_type = "rofex"
```

**Result:** App connects automatically on startup!

---

## 📊 Auto-Fill Workflow

Once connected, here's what happens:

### 1. Select Strategy
```
User clicks "Bull Call Spread"
→ Sidebar shows configuration
```

### 2. Select Underlying
```
Dropdown shows: GGAL (default), YPF, PAMP, etc.
User selects "GGAL"
```

### 3. Click "Auto-Fill Market Data"
```
Button appears when connected
User clicks → Fetches:
  ✓ Stock Price: $25.40 (from market)
  ✓ Days to Exp: 23 (next expiration)
  ✓ Volatility: 35% (52-week historical)
  ✓ Risk-Free Rate: 5.2% (caucion 1D)
  ✓ Option Chain: All strikes with premiums
```

### 4. Configure Legs
```
Strike dropdown shows:
  [20, 22.5, 25, 27.5, 30, ...]
  
User selects strike = 25
→ Premium auto-fills: $2.15 (from market)
→ IV auto-calculates: 37.2%

Both are EDITABLE!
```

### 5. Analyze
```
Click "Analyze Strategy"
→ Results appear with charts
```

---

## 🎯 Complete Example

### Your `.streamlit/secrets.toml`:

```toml
[rofex]
user = "john.doe@example.com"
password = "MySecurePass123!"
account = "DEMO123"
environment = "REMARKET"

[defaults]
default_underlying = "GGAL"
auto_connect = true
```

### What Happens:

```
1. streamlit run app_enhanced.py
   └─> Reads secrets.toml
   └─> Auto-connects to Rofex
   └─> Shows "🟢 Connected: rofex"

2. Select "Bull Call Spread"
   └─> Sidebar shows config
   └─> Underlying dropdown: GGAL selected
   
3. Click "🔄 Auto-Fill Market Data"
   └─> Fetches GGAL data
   └─> Stock Price: $25.40 ✓
   └─> DTE: 23 days ✓
   └─> Vol: 35% ✓
   └─> Rate: 5.2% ✓
   
4. Configure First Leg (Long Call)
   └─> Strike dropdown: [20, 22.5, 25, 27.5, 30]
   └─> Select: 25
   └─> Premium auto-fills: $2.15
   └─> IV auto-fills: 37.2%
   └─> Can edit both values!
   
5. Configure Second Leg (Short Call)
   └─> Strike dropdown: [20, 22.5, 25, 27.5, 30]
   └─> Select: 27.5
   └─> Premium auto-fills: $1.30
   └─> IV auto-fills: 35.8%
   
6. Click "📊 Analyze Strategy"
   └─> Results + Charts appear
```

---

## 🔍 Verify Everything Works

### Test Checklist:

```bash
# 1. Secrets file exists
ls .streamlit/secrets.toml

# 2. Not in Git
git status  # Should NOT show secrets.toml

# 3. Can read secrets
streamlit run app_enhanced.py
# Look for: "🟢 Auto-connected to rofex"

# 4. Auto-fill works
# Select strategy → Click "Auto-Fill" → Data loads

# 5. Strike dropdown works
# See available strikes from market

# 6. Premium auto-fills
# Select strike → Premium appears

# 7. Can edit values
# Change premium → Still works
```

---

## 🐛 Troubleshooting

### "KeyError: 'rofex'"

**Cause:** Secrets file doesn't exist or wrong format.

**Solution:**
```bash
# Check file exists
cat .streamlit/secrets.toml

# Verify TOML format (must use [section] and key = "value")
```

### "Auto-connect failed"

**Cause:** Wrong credentials or broker server down.

**Solution:**
```toml
# Start with REMARKET environment
environment = "REMARKET"

# Check credentials are correct
# Try connecting manually first
```

### "Auto-fill button doesn't appear"

**Cause:** Not connected to broker.

**Solution:**
```python
# Check connection status
if st.session_state.broker_connected:
    st.success("Connected!")
else:
    st.error("Not connected")
```

### "No strikes in dropdown"

**Cause:** Option chain fetch failed.

**Solution:**
```python
# Check if option_chain is loaded
if st.session_state.option_chain:
    st.write("Option chain loaded!")
else:
    st.warning("No option chain data")
```

---

## 🔄 Different Environments

### Development (Local)

```toml
# .streamlit/secrets.toml
[rofex]
environment = "REMARKET"  # Use demo
```

### Production (Streamlit Cloud)

```toml
# Streamlit Cloud → Settings → Secrets
[rofex]
environment = "LIVE"  # Use real account
```

**Pro Tip:** Use different accounts for dev/prod!

---

## 🎨 Optional: Multiple Accounts

```toml
# .streamlit/secrets.toml

[rofex_demo]
user = "demo_user"
password = "demo_pass"
account = "DEMO123"
environment = "REMARKET"

[rofex_live]
user = "real_user"
password = "real_pass"
account = "REAL456"
environment = "LIVE"

[defaults]
active_account = "rofex_demo"  # Switch easily
```

---

## 📚 Best Practices

✅ **DO:**
- Use `.streamlit/secrets.toml` for credentials
- Add to `.gitignore`
- Use REMARKET for testing
- Rotate passwords regularly

❌ **DON'T:**
- Commit secrets to Git
- Share secrets.toml file
- Use LIVE without testing first
- Hardcode credentials in code

---

## 🎉 Summary

### Local Setup:
```bash
mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF
[rofex]
user = "YOUR_USER"
password = "YOUR_PASSWORD"
account = "YOUR_ACCOUNT"
environment = "REMARKET"
EOF

echo ".streamlit/secrets.toml" >> .gitignore
streamlit run app_enhanced.py
```

### Streamlit Cloud:
```
1. Deploy app
2. Settings → Secrets → Paste credentials
3. Save → Auto-redeploy
```

### Usage:
```
1. App auto-connects
2. Select strategy
3. Select underlying (GGAL default)
4. Click "Auto-Fill" → Data loads
5. Configure strikes (dropdowns)
6. Premiums auto-fill (editable)
7. Analyze!
```

---

**That's it! Your credentials are secure and auto-fill works perfectly.** 🚀
