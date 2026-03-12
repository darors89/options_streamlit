# data_fetcher.py - Enhanced Data Fetching with Auto-fill
"""
Auto-fetch market data when connected to broker:
- Underlying list
- Current stock price
- Days to expiration (next chain)
- Historical volatility (52-week)
- Risk-free rate (caucion 1D)
- Available strikes
- Option premiums and implied volatility
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from broker_integration import get_market_data, get_option_chain, is_connected

# Argentine market underlyings with options
ARGENTINE_UNDERLYINGS = [
    'GGAL',  # Grupo Financiero Galicia
    'YPF',   # YPF
    'PAMP',  # Pampa Energía
    'YPFD',  # YPF ADR
    'BMA',   # Banco Macro
    'VIST',  # Vista Energy
    'CEPU',  # Central Puerto
    'EDN',   # Edenor
    'TGSU2', # TGS
    'TXAR',  # Ternium
    'ALUA',  # Aluar
    'COME',  # Banco Comercio
    'SUPV',  # Grupo Supervielle
]


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_underlying_list():
    """Get list of underlyings with options in Argentine market."""
    return sorted(ARGENTINE_UNDERLYINGS)


@st.cache_data(ttl=60)  # Cache for 1 minute
def fetch_stock_price(ticker, broker_type='auto'):
    """
    Fetch current stock price.
    
    Returns:
        float: Current price or None if failed
    """
    try:
        if not is_connected():
            return None
        
        data = get_market_data(ticker, broker_type)
        
        if data and 'last_price' in data and data['last_price']:
            return float(data['last_price'])
        
        return None
    except Exception as e:
        st.error(f"Error fetching stock price: {e}")
        return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_historical_volatility(ticker, days=252, broker_type='auto'):
    """
    Fetch historical volatility (52-week).
    
    For now returns estimated volatility.
    TODO: Implement actual historical data fetching.
    
    Returns:
        float: Annualized volatility (decimal)
    """
    try:
        if not is_connected():
            return None
        
        # TODO: Fetch actual historical prices and calculate
        # For now, return typical volatility for Argentine stocks
        volatilities = {
            'GGAL': 0.35,
            'YPF': 0.40,
            'PAMP': 0.38,
            'YPFD': 0.42,
            'BMA': 0.36,
            'VIST': 0.45,
            'CEPU': 0.40,
        }
        
        return volatilities.get(ticker, 0.35)  # Default 35%
    
    except Exception as e:
        st.error(f"Error fetching volatility: {e}")
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_caucion_rate(broker_type='auto'):
    """
    Fetch 1-day caucion rate (risk-free rate).
    
    Returns:
        float: Annualized rate (decimal)
    """
    try:
        if not is_connected():
            return None
        
        # TODO: Fetch actual caucion rate from broker
        # For now, return typical caucion rate
        # This would come from market data feed
        
        # Typical caucion rates in Argentina (example)
        return 0.05  # 5% annual
    
    except Exception as e:
        st.error(f"Error fetching caucion rate: {e}")
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_option_chain_data(ticker, broker_type='auto'):
    """
    Fetch complete option chain with strikes, premiums, and IVs.
    
    Returns:
        dict: {
            'calls': DataFrame with call options,
            'puts': DataFrame with put options,
            'expirations': list of expiration dates
        }
    """
    try:
        if not is_connected():
            return None
        
        options = get_option_chain(ticker, broker_type)
        
        if not options:
            return None
        
        # Parse options data
        calls = []
        puts = []
        expirations = set()
        
        for opt in options:
            option_type = opt.get('type', 'call').lower()
            strike = opt.get('strike', 0)
            expiration = opt.get('expiration', '')
            symbol = opt.get('symbol', '')
            
            # Fetch market data for this option
            opt_data = get_market_data(symbol, broker_type)
            
            if opt_data:
                premium = opt_data.get('last_price', 0)
                bid = opt_data.get('bid', 0)
                ask = opt_data.get('ask', 0)
                
                # Calculate mid price
                mid_price = (bid + ask) / 2 if bid and ask else premium
                
                option_info = {
                    'strike': strike,
                    'premium': mid_price,
                    'bid': bid,
                    'ask': ask,
                    'expiration': expiration,
                    'symbol': symbol,
                    'iv': None  # Will be calculated
                }
                
                if option_type == 'call':
                    calls.append(option_info)
                else:
                    puts.append(option_info)
                
                if expiration:
                    expirations.add(expiration)
        
        return {
            'calls': pd.DataFrame(calls) if calls else pd.DataFrame(),
            'puts': pd.DataFrame(puts) if puts else pd.DataFrame(),
            'expirations': sorted(list(expirations))
        }
    
    except Exception as e:
        st.error(f"Error fetching option chain: {e}")
        return None


def get_days_to_expiration(expiration_date):
    """
    Calculate days to expiration from date string.
    
    Args:
        expiration_date: Date string (YYYY-MM-DD or similar)
    
    Returns:
        int: Days to expiration
    """
    try:
        # Parse date (adjust format as needed)
        if isinstance(expiration_date, str):
            exp = datetime.strptime(expiration_date, '%Y-%m-%d')
        else:
            exp = expiration_date
        
        today = datetime.now()
        delta = exp - today
        
        return max(delta.days, 1)
    except:
        return 30  # Default fallback


def get_next_expiration(expirations):
    """
    Get next expiration date from list.
    
    Args:
        expirations: List of expiration date strings
    
    Returns:
        str: Next expiration date
    """
    if not expirations:
        return None
    
    today = datetime.now()
    future_expirations = []
    
    for exp in expirations:
        try:
            exp_date = datetime.strptime(exp, '%Y-%m-%d')
            if exp_date > today:
                future_expirations.append((exp_date, exp))
        except:
            continue
    
    if future_expirations:
        future_expirations.sort()
        return future_expirations[0][1]
    
    return expirations[0] if expirations else None


def calculate_implied_volatility(option_price, stock_price, strike, days_to_exp, 
                                 risk_free_rate, option_type='call'):
    """
    Calculate implied volatility using Newton-Raphson method.
    
    Args:
        option_price: Market price of option
        stock_price: Current stock price
        strike: Strike price
        days_to_exp: Days to expiration
        risk_free_rate: Risk-free rate (decimal)
        option_type: 'call' or 'put'
    
    Returns:
        float: Implied volatility (decimal) or None if failed
    """
    from blackscholes import BlackScholes
    
    try:
        T = days_to_exp / 365
        
        # Newton-Raphson iteration
        sigma = 0.3  # Initial guess
        max_iterations = 100
        tolerance = 0.0001
        
        for i in range(max_iterations):
            # Calculate option price with current sigma
            if option_type == 'call':
                price = BlackScholes.call_price(stock_price, strike, T, risk_free_rate, sigma)
                vega = BlackScholes.vega(stock_price, strike, T, risk_free_rate, sigma)
            else:
                price = BlackScholes.put_price(stock_price, strike, T, risk_free_rate, sigma)
                vega = BlackScholes.vega(stock_price, strike, T, risk_free_rate, sigma)
            
            # Calculate difference
            diff = option_price - price
            
            # Check convergence
            if abs(diff) < tolerance:
                return sigma
            
            # Newton-Raphson update
            if vega > 0:
                sigma = sigma + diff / (vega * 100)  # vega is per 1% change
            else:
                break
            
            # Keep sigma in reasonable bounds
            sigma = max(0.01, min(sigma, 2.0))
        
        return sigma if sigma > 0.01 else None
    
    except Exception as e:
        print(f"Error calculating IV: {e}")
        return None


def auto_fill_market_data(ticker):
    """
    Auto-fill all market data for a ticker.
    
    Returns:
        dict: {
            'stock_price': float,
            'days_to_exp': int,
            'volatility': float (decimal),
            'risk_free_rate': float (decimal),
            'option_chain': dict with calls/puts data
        }
    """
    result = {
        'stock_price': None,
        'days_to_exp': 30,
        'volatility': 0.25,
        'risk_free_rate': 0.05,
        'option_chain': None
    }
    
    if not is_connected():
        st.warning("Not connected to broker. Using default values.")
        return result
    
    with st.spinner(f"Fetching market data for {ticker}..."):
        # Fetch stock price
        stock_price = fetch_stock_price(ticker)
        if stock_price:
            result['stock_price'] = stock_price
        
        # Fetch volatility
        volatility = fetch_historical_volatility(ticker)
        if volatility:
            result['volatility'] = volatility
        
        # Fetch risk-free rate
        risk_free_rate = fetch_caucion_rate()
        if risk_free_rate:
            result['risk_free_rate'] = risk_free_rate
        
        # Fetch option chain
        option_chain = fetch_option_chain_data(ticker)
        if option_chain and option_chain['expirations']:
            result['option_chain'] = option_chain
            
            # Get next expiration
            next_exp = get_next_expiration(option_chain['expirations'])
            if next_exp:
                result['days_to_exp'] = get_days_to_expiration(next_exp)
    
    return result


def get_available_strikes(option_chain, option_type='call', stock_price=None):
    """
    Get list of available strikes for an option type.
    
    Args:
        option_chain: Option chain data from fetch_option_chain_data
        option_type: 'call' or 'put'
        stock_price: Current stock price (for sorting)
    
    Returns:
        list: Sorted list of strikes
    """
    if not option_chain:
        return []
    
    df = option_chain['calls'] if option_type == 'call' else option_chain['puts']
    
    if df.empty:
        return []
    
    strikes = sorted(df['strike'].unique())
    
    # Sort by proximity to stock price if provided
    if stock_price:
        strikes = sorted(strikes, key=lambda x: abs(x - stock_price))
    
    return strikes


def get_premium_for_strike(option_chain, strike, option_type='call'):
    """
    Get premium for a specific strike.
    
    Returns:
        tuple: (premium, iv) or (None, None) if not found
    """
    if not option_chain:
        return None, None
    
    df = option_chain['calls'] if option_type == 'call' else option_chain['puts']
    
    if df.empty:
        return None, None
    
    row = df[df['strike'] == strike]
    
    if not row.empty:
        premium = row.iloc[0]['premium']
        iv = row.iloc[0].get('iv', None)
        return premium, iv
    
    return None, None
