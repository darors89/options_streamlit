# app.py - Main Streamlit Application
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import local modules
from blackscholes import BlackScholes, analyze_strategy
from strategies import STRATEGY_CONFIGS, STRATEGY_CATEGORIES
from plotting import plot_payoff_chart, plot_volatility_surface, create_pnl_table
from broker_integration import connect_to_broker, get_market_data

# Page config
st.set_page_config(
    page_title="Options Strategy Builder",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .stApp {
        background-color: #0a0e27;
    }
    .main-header {
        color: #60a5fa;
        font-size: 2.5rem;
        font-weight: 300;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #0d1135;
        border: 1px solid rgba(96, 165, 250, 0.3);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .profit {
        color: #22c55e;
    }
    .loss {
        color: #ef4444;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'strategy' not in st.session_state:
    st.session_state.strategy = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'online_mode' not in st.session_state:
    st.session_state.online_mode = False
if 'broker_connected' not in st.session_state:
    st.session_state.broker_connected = False
if 'broker_type' not in st.session_state:
    st.session_state.broker_type = None

# Header
st.markdown('<h1 class="main-header">📊 Options Strategy Builder</h1>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # Online/Offline Mode Toggle
    mode = st.radio(
        "Mode",
        ["🔒 Offline", "🌐 Online"],
        horizontal=True
    )
    st.session_state.online_mode = (mode == "🌐 Online")
    
    st.markdown("---")
    
    # If online mode but not connected, show broker login
    if st.session_state.online_mode and not st.session_state.broker_connected:
        st.markdown("### 🔌 Connect to Broker")
        
        broker_type = st.selectbox(
            "Broker",
            ["PyRofex", "PyHomebroker"]
        )
        
        if broker_type == "PyRofex":
            with st.form("rofex_login"):
                user = st.text_input("User")
                password = st.text_input("Password", type="password")
                account = st.text_input("Account")
                environment = st.selectbox("Environment", ["REMARKET", "LIVE"])
                
                submitted = st.form_submit_button("Connect")
                
                if submitted:
                    success, message = connect_to_broker(
                        broker_type="rofex",
                        credentials={
                            "user": user,
                            "password": password,
                            "account": account,
                            "environment": environment
                        }
                    )
                    
                    if success:
                        st.session_state.broker_connected = True
                        st.session_state.broker_type = "rofex"
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        else:  # PyHomebroker
            with st.form("homebroker_login"):
                broker_id = st.selectbox(
                    "Broker",
                    {
                        "11": "Balanz",
                        "12": "Bull Market",
                        "121": "Invertir Online",
                        "134": "Portfolio Personal"
                    }
                )
                user = st.text_input("User")
                password = st.text_input("Password", type="password")
                dni = st.text_input("DNI")
                
                submitted = st.form_submit_button("Connect")
                
                if submitted:
                    success, message = connect_to_broker(
                        broker_type="homebroker",
                        credentials={
                            "broker_id": broker_id,
                            "user": user,
                            "password": password,
                            "dni": dni
                        }
                    )
                    
                    if success:
                        st.session_state.broker_connected = True
                        st.session_state.broker_type = "homebroker"
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        st.info("🔒 Credentials sent securely. Not stored locally.")
    
    # If connected or offline, show strategy configuration
    elif st.session_state.strategy:
        st.markdown(f"### {st.session_state.strategy}")
        
        # Show disconnect button if online
        if st.session_state.online_mode and st.session_state.broker_connected:
            if st.button("🔌 Disconnect"):
                st.session_state.broker_connected = False
                st.session_state.broker_type = None
                st.rerun()
        
        st.markdown("---")
        
        # Market Parameters
        st.markdown("#### 📈 Market Parameters")
        
        stock_price = st.number_input(
            "Stock Price ($)",
            value=100.0,
            min_value=0.01,
            step=0.01,
            format="%.2f"
        )
        
        days_to_expiration = st.number_input(
            "Days to Expiration",
            value=30,
            min_value=1,
            max_value=365,
            step=1
        )
        
        volatility = st.number_input(
            "Volatility (%)",
            value=25.0,
            min_value=0.1,
            max_value=200.0,
            step=1.0,
            format="%.1f"
        )
        
        risk_free_rate = st.number_input(
            "Risk-Free Rate (%)",
            value=5.0,
            min_value=0.0,
            max_value=50.0,
            step=0.1,
            format="%.1f"
        )
        
        st.markdown("---")
        
        # Option Legs Configuration
        st.markdown("#### 🎯 Option Legs")
        
        config = STRATEGY_CONFIGS[st.session_state.strategy]
        leg_params = []
        
        for idx, leg_config in enumerate(config['legs']):
            with st.expander(f"{leg_config['label']}", expanded=True):
                strike = st.number_input(
                    leg_config['strikeLabel'],
                    value=float(stock_price + (idx - len(config['legs'])//2) * 5),
                    min_value=0.01,
                    step=0.01,
                    format="%.2f",
                    key=f"strike_{idx}"
                )
                
                premium = st.number_input(
                    "Premium ($)",
                    value=5.0 - idx * 0.5,
                    min_value=0.01,
                    step=0.01,
                    format="%.2f",
                    key=f"premium_{idx}"
                )
                
                leg_params.append({
                    'type': leg_config['type'],
                    'position': leg_config['position'],
                    'strike': strike,
                    'premium': premium
                })
        
        st.markdown("---")
        
        # Analyze Button
        if st.button("📊 Analyze Strategy", use_container_width=True, type="primary"):
            with st.spinner("Analyzing..."):
                result = analyze_strategy(
                    strategy_name=st.session_state.strategy,
                    stock_price=stock_price,
                    legs=leg_params,
                    days_to_expiration=days_to_expiration,
                    volatility=volatility / 100,
                    risk_free_rate=risk_free_rate / 100
                )
                
                st.session_state.analysis_result = result
                st.success("✓ Analysis completed!")
                st.rerun()
        
        # Mode indicator
        st.markdown("---")
        if st.session_state.online_mode and st.session_state.broker_connected:
            st.info(f"🟢 Online: Connected to {st.session_state.broker_type}")
        elif st.session_state.online_mode:
            st.warning("🟡 Online: Not connected")
        else:
            st.info("🔒 Offline: Browser calculations")
    
    else:
        st.info("👈 Select a strategy to begin")

# Main content
if st.session_state.strategy is None:
    # Strategy Selection
    st.markdown("### Select Strategy")
    
    tabs = st.tabs([cat['label'] for cat in STRATEGY_CATEGORIES])
    
    for tab, category in zip(tabs, STRATEGY_CATEGORIES):
        with tab:
            cols = st.columns(4)
            for idx, strategy in enumerate(category['strategies']):
                col_idx = idx % 4
                with cols[col_idx]:
                    if st.button(
                        strategy,
                        use_container_width=True,
                        key=f"strategy_{strategy}"
                    ):
                        st.session_state.strategy = strategy
                        st.rerun()

else:
    # Show Results
    if st.session_state.analysis_result:
        result = st.session_state.analysis_result
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pnl_class = "profit" if result['current_pnl'] >= 0 else "loss"
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">Current P&L</div>
                <div class="{pnl_class}" style="font-size: 1.5rem; font-weight: 600;">
                    ${result['current_pnl']:.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">Max Profit</div>
                <div class="profit" style="font-size: 1.5rem; font-weight: 600;">
                    ${result['max_profit']:.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">Max Loss</div>
                <div class="loss" style="font-size: 1.5rem; font-weight: 600;">
                    ${abs(result['max_loss']):.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            rr_value = result['risk_reward_ratio'] if result['risk_reward_ratio'] else 0
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem; color: #9ca3af;">Risk/Reward</div>
                <div style="font-size: 1.5rem; font-weight: 600; color: #60a5fa;">
                    {rr_value:.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Greeks
        st.markdown("### 📊 Greeks")
        
        greek_cols = st.columns(5)
        greeks_list = ['delta', 'gamma', 'theta', 'vega', 'rho']
        
        for col, greek in zip(greek_cols, greeks_list):
            with col:
                value = result['greeks'][greek]
                st.metric(
                    label=greek.capitalize(),
                    value=f"{value:.4f}"
                )
        
        # Break-evens
        if result['break_evens']:
            st.markdown("### 🎯 Break-even Points")
            be_cols = st.columns(len(result['break_evens']))
            for idx, (col, be) in enumerate(zip(be_cols, result['break_evens'])):
                with col:
                    st.info(f"**BE {idx+1}:** ${be:.2f}")
        
        st.markdown("---")
        
        # Payoff Chart
        st.markdown("### 📈 Payoff Diagram")
        
        fig = plot_payoff_chart(
            result=result,
            stock_price=stock_price,
            strategy_name=st.session_state.strategy,
            legs=leg_params
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # P&L Table
        st.markdown("### 📊 P&L Table")
        
        table_df = create_pnl_table(
            result=result,
            stock_price=stock_price
        )
        
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("---")
        
        # Volatility Surface
        st.markdown("### 🌐 Volatility Surface")
        
        fig_surface = plot_volatility_surface(
            legs=leg_params,
            stock_price=stock_price,
            days_to_expiration=days_to_expiration
        )
        
        st.plotly_chart(fig_surface, use_container_width=True)
    
    else:
        st.info("👈 Configure parameters and click 'Analyze Strategy'")
    
    # Back button
    st.markdown("---")
    if st.button("← Back to Strategy Selection"):
        st.session_state.strategy = None
        st.session_state.analysis_result = None
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #6b7280; font-size: 0.8rem;">
        Options Strategy Builder | Built with Streamlit & Python
    </div>
    """,
    unsafe_allow_html=True
)
