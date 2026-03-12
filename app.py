# app_enhanced.py - Enhanced Streamlit App with Auto-fill
"""
Enhanced version with:
- Auto-connect using secrets
- Auto-fill market data when connected
- Dropdown for underlyings (default GGAL)
- Dropdown for strikes
- Editable premium and IV
- Multiple QoL improvements
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Import local modules
from blackscholes import BlackScholes, analyze_strategy
from strategies import STRATEGY_CONFIGS, STRATEGY_CATEGORIES
from plotting import plot_payoff_chart, plot_volatility_surface, create_pnl_table
from broker_integration import connect_to_broker, is_connected, disconnect_broker
from data_fetcher import (
    get_underlying_list,
    auto_fill_market_data,
    get_available_strikes,
    get_premium_for_strike,
    calculate_implied_volatility
)

# Page config
st.set_page_config(
    page_title="Options Strategy Builder",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp { background-color: #0a0e27; }
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
    .profit { color: #22c55e; }
    .loss { color: #ef4444; }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'strategy' not in st.session_state:
    st.session_state.strategy = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'broker_connected' not in st.session_state:
    st.session_state.broker_connected = False
if 'broker_type' not in st.session_state:
    st.session_state.broker_type = None
if 'selected_underlying' not in st.session_state:
    st.session_state.selected_underlying = 'GGAL'
if 'option_chain' not in st.session_state:
    st.session_state.option_chain = None
if 'market_data_loaded' not in st.session_state:
    st.session_state.market_data_loaded = False

# Auto-connect using secrets (if available)
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

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<h1 class="main-header">📊 Options Strategy Builder</h1>', unsafe_allow_html=True)
with col2:
    if st.session_state.broker_connected:
        st.success(f"🟢 Connected: {st.session_state.broker_type}")
        if st.button("🔌 Disconnect", key="disconnect_main"):
            disconnect_broker()
            st.session_state.broker_connected = False
            st.session_state.broker_type = None
            st.rerun()
    else:
        st.info("🔒 Offline Mode")

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # If not connected, show connect option
    if not st.session_state.broker_connected:
        if st.button("🌐 Connect to Broker"):
            # Show connection form
            st.session_state.show_connect_form = True
        
        if st.session_state.get('show_connect_form', False):
            broker_type = st.selectbox("Broker", ["PyRofex", "PyHomebroker"])
            
            if broker_type == "PyRofex":
                with st.form("rofex_login"):
                    user = st.text_input("User")
                    password = st.text_input("Password", type="password")
                    account = st.text_input("Account")
                    environment = st.selectbox("Environment", ["REMARKET", "LIVE"])
                    
                    if st.form_submit_button("Connect"):
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
                            st.session_state.show_connect_form = False
                            st.rerun()
                        else:
                            st.error(message)
    
    st.markdown("---")
    
    # Strategy configuration (if strategy selected)
    if st.session_state.strategy:
        st.markdown(f"### {st.session_state.strategy}")
        
        # Underlying selection
        st.markdown("#### 📈 Underlying")
        
        underlyings = get_underlying_list()
        default_idx = underlyings.index('GGAL') if 'GGAL' in underlyings else 0
        
        selected_underlying = st.selectbox(
            "Ticker",
            underlyings,
            index=default_idx,
            key="underlying_select"
        )
        
        # Auto-fetch button
        if st.session_state.broker_connected:
            if st.button("🔄 Auto-Fill Market Data", type="primary"):
                market_data = auto_fill_market_data(selected_underlying)
                
                # Store in session state
                st.session_state.market_data = market_data
                st.session_state.option_chain = market_data['option_chain']
                st.session_state.market_data_loaded = True
                st.success("✓ Market data loaded!")
                st.rerun()
        
        st.markdown("---")
        
        # Market Parameters
        st.markdown("#### 📊 Market Parameters")
        
        # Use auto-filled data if available, otherwise defaults
        if st.session_state.get('market_data_loaded', False):
            md = st.session_state.market_data
            default_price = md['stock_price'] if md['stock_price'] else 100.0
            default_dte = md['days_to_exp']
            default_vol = md['volatility'] * 100
            default_rate = md['risk_free_rate'] * 100
        else:
            default_price = 100.0
            default_dte = 30
            default_vol = 25.0
            default_rate = 5.0
        
        stock_price = st.number_input(
            "Stock Price ($)",
            value=float(default_price),
            min_value=0.01,
            step=0.01,
            format="%.2f",
            help="Auto-filled from market when connected"
        )
        
        days_to_expiration = st.number_input(
            "Days to Expiration",
            value=int(default_dte),
            min_value=1,
            max_value=365,
            step=1,
            help="Auto-filled to next expiration when connected"
        )
        
        volatility = st.number_input(
            "Volatility (%)",
            value=float(default_vol),
            min_value=0.1,
            max_value=200.0,
            step=1.0,
            format="%.1f",
            help="Auto-filled from 52-week historical vol when connected"
        )
        
        risk_free_rate = st.number_input(
            "Risk-Free Rate (%)",
            value=float(default_rate),
            min_value=0.0,
            max_value=50.0,
            step=0.1,
            format="%.1f",
            help="Auto-filled from 1D caucion rate when connected"
        )
        
        st.markdown("---")
        
        # Option Legs Configuration
        st.markdown("#### 🎯 Option Legs")
        
        config = STRATEGY_CONFIGS[st.session_state.strategy]
        leg_params = []
        
        option_chain = st.session_state.get('option_chain', None)
        
        for idx, leg_config in enumerate(config['legs']):
            with st.expander(f"{leg_config['label']}", expanded=True):
                # Strike selection
                if option_chain and not option_chain['calls'].empty:
                    # Use dropdown with available strikes
                    available_strikes = get_available_strikes(
                        option_chain,
                        leg_config['type'],
                        stock_price
                    )
                    
                    if available_strikes:
                        # Find closest to default
                        default_strike = stock_price + (idx - len(config['legs'])//2) * 5
                        closest_idx = min(range(len(available_strikes)),
                                        key=lambda i: abs(available_strikes[i] - default_strike))
                        
                        strike = st.selectbox(
                            leg_config['strikeLabel'],
                            available_strikes,
                            index=closest_idx,
                            key=f"strike_select_{idx}",
                            format_func=lambda x: f"${x:.2f}"
                        )
                        
                        # Get premium for selected strike
                        fetched_premium, fetched_iv = get_premium_for_strike(
                            option_chain,
                            strike,
                            leg_config['type']
                        )
                        
                        default_premium = fetched_premium if fetched_premium else 5.0
                    else:
                        # Fallback to number input
                        strike = st.number_input(
                            leg_config['strikeLabel'],
                            value=float(stock_price + (idx - len(config['legs'])//2) * 5),
                            min_value=0.01,
                            step=0.01,
                            format="%.2f",
                            key=f"strike_{idx}"
                        )
                        default_premium = 5.0
                        fetched_iv = None
                else:
                    # Number input if no option chain
                    strike = st.number_input(
                        leg_config['strikeLabel'],
                        value=float(stock_price + (idx - len(config['legs'])//2) * 5),
                        min_value=0.01,
                        step=0.01,
                        format="%.2f",
                        key=f"strike_{idx}"
                    )
                    default_premium = 5.0
                    fetched_iv = None
                
                # Premium input (editable)
                premium = st.number_input(
                    "Premium ($)",
                    value=float(default_premium),
                    min_value=0.01,
                    step=0.01,
                    format="%.2f",
                    key=f"premium_{idx}",
                    help="Auto-filled from market when connected, but editable"
                )
                
                # Implied Volatility (display and editable)
                if fetched_iv:
                    iv_display = fetched_iv * 100
                else:
                    # Calculate IV from premium
                    T = days_to_expiration / 365
                    calc_iv = calculate_implied_volatility(
                        premium, stock_price, strike, days_to_expiration,
                        risk_free_rate / 100, leg_config['type']
                    )
                    iv_display = calc_iv * 100 if calc_iv else volatility
                
                iv = st.number_input(
                    "Implied Vol (%)",
                    value=float(iv_display),
                    min_value=0.1,
                    max_value=200.0,
                    step=1.0,
                    format="%.1f",
                    key=f"iv_{idx}",
                    help="Auto-calculated from premium, but editable"
                )
                
                leg_params.append({
                    'type': leg_config['type'],
                    'position': leg_config['position'],
                    'strike': strike,
                    'premium': premium,
                    'iv': iv / 100
                })
        
        st.markdown("---")
        
        # Analyze Button
        if st.button("📊 Analyze Strategy", type="primary", use_container_width=True):
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
        
        # Quick Actions
        st.markdown("---")
        st.markdown("#### ⚡ Quick Actions")
        
        col_qa1, col_qa2 = st.columns(2)
        with col_qa1:
            if st.button("📋 Save Config", use_container_width=True):
                # TODO: Implement save configuration
                st.info("Feature coming soon!")
        with col_qa2:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.market_data_loaded = False
                st.session_state.option_chain = None
                st.rerun()
    
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
        
        # Action buttons
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        with col_btn1:
            if st.button("← Back to Strategies"):
                st.session_state.strategy = None
                st.session_state.analysis_result = None
                st.rerun()
        with col_btn2:
            if st.button("📊 Compare Strategies"):
                st.info("Feature coming soon!")
        with col_btn3:
            if st.button("📥 Export to Excel"):
                st.info("Feature coming soon!")
        with col_btn4:
            if st.button("🔔 Set Alert"):
                st.info("Feature coming soon!")
        
        st.markdown("---")
        
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
                st.metric(label=greek.capitalize(), value=f"{value:.4f}")
        
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
        
        table_df = create_pnl_table(result=result, stock_price=stock_price)
        st.dataframe(table_df, use_container_width=True, hide_index=True)
        
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

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #6b7280; font-size: 0.8rem;">
        Options Strategy Builder | Built with Streamlit & Python | 
        {status}
    </div>
    """.format(
        status="🟢 Connected" if st.session_state.broker_connected else "🔒 Offline"
    ),
    unsafe_allow_html=True
)
