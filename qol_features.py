# qol_features.py - Quality of Life Improvements
"""
Additional QoL features:
- Export to Excel/CSV
- Save/Load configurations
- Probability calculator
- Max pain calculator
- Strategy comparison
- Quick presets
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
from scipy.stats import norm
from io import BytesIO


# ==================== SAVE/LOAD CONFIGURATIONS ====================

def save_configuration(config_data):
    """Save current strategy configuration."""
    config = {
        'strategy_name': config_data['strategy_name'],
        'underlying': config_data['underlying'],
        'stock_price': config_data['stock_price'],
        'days_to_expiration': config_data['days_to_expiration'],
        'volatility': config_data['volatility'],
        'risk_free_rate': config_data['risk_free_rate'],
        'legs': config_data['legs'],
        'timestamp': datetime.now().isoformat()
    }
    
    return json.dumps(config, indent=2)


def load_configuration(json_string):
    """Load strategy configuration from JSON."""
    return json.loads(json_string)


# ==================== EXPORT TO EXCEL ====================

def export_to_excel(analysis_result, strategy_name, config_data):
    """Export analysis to Excel file."""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary
        summary = pd.DataFrame({
            'Metric': ['Strategy', 'Current P&L', 'Max Profit', 'Max Loss', 'R/R',
                      'Stock', 'DTE', 'Vol', 'Rate'],
            'Value': [
                strategy_name,
                f"${analysis_result['current_pnl']:.2f}",
                f"${analysis_result['max_profit']:.2f}",
                f"${analysis_result['max_loss']:.2f}",
                f"{analysis_result.get('risk_reward_ratio', 0):.2f}",
                f"${config_data['stock_price']:.2f}",
                config_data['days_to_expiration'],
                f"{config_data['volatility']*100:.1f}%",
                f"{config_data['risk_free_rate']*100:.1f}%"
            ]
        })
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Greeks
        greeks = pd.DataFrame({
            'Greek': ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'],
            'Value': [
                analysis_result['greeks']['delta'],
                analysis_result['greeks']['gamma'],
                analysis_result['greeks']['theta'],
                analysis_result['greeks']['vega'],
                analysis_result['greeks']['rho']
            ]
        })
        greeks.to_excel(writer, sheet_name='Greeks', index=False)
        
        # Payoff
        payoff = pd.DataFrame({
            'Stock Price': analysis_result['payoff_data']['stock_prices'],
            'P&L Expiration': analysis_result['payoff_data']['payoff_expiration'],
            'Current P&L': analysis_result['payoff_data']['payoff_current']
        })
        payoff.to_excel(writer, sheet_name='Payoff', index=False)
    
    return output.getvalue()


# ==================== PROBABILITY CALCULATOR ====================

def calculate_probabilities(stock_price, target_prices, days_to_exp, volatility):
    """Calculate probability of reaching targets."""
    T = days_to_exp / 365
    
    probs = {}
    for target in target_prices:
        d2 = (np.log(stock_price / target)) / (volatility * np.sqrt(T))
        prob_above = norm.cdf(d2)
        
        probs[target] = {
            'above': prob_above * 100,
            'below': (1 - prob_above) * 100
        }
    
    return probs


def calculate_profit_probability(analysis_result, stock_price, days_to_exp, volatility):
    """Calculate probability of profit at expiration."""
    break_evens = analysis_result.get('break_evens', [])
    
    if not break_evens:
        return None
    
    T = days_to_exp / 365
    
    if len(break_evens) == 1:
        # One break-even (e.g., long call/put)
        be = break_evens[0]
        d2 = (np.log(stock_price / be)) / (volatility * np.sqrt(T))
        
        # Determine if profit is above or below BE
        if analysis_result['max_profit'] > 0:
            # Check a point above BE
            test_prices = analysis_result['payoff_data']['stock_prices']
            test_payoffs = analysis_result['payoff_data']['payoff_expiration']
            
            above_be_idx = next((i for i, p in enumerate(test_prices) if p > be), None)
            if above_be_idx and test_payoffs[above_be_idx] > 0:
                prob_profit = norm.cdf(-d2) * 100  # Probability above BE
            else:
                prob_profit = norm.cdf(d2) * 100   # Probability below BE
        
        return prob_profit
    
    elif len(break_evens) == 2:
        # Two break-evens (e.g., spreads, straddles)
        be1, be2 = sorted(break_evens)
        
        # Probability between break-evens
        d2_lower = (np.log(stock_price / be1)) / (volatility * np.sqrt(T))
        d2_upper = (np.log(stock_price / be2)) / (volatility * np.sqrt(T))
        
        prob_between = norm.cdf(d2_lower) - norm.cdf(d2_upper)
        
        # Check if profit is between or outside BEs
        mid_price = (be1 + be2) / 2
        test_prices = analysis_result['payoff_data']['stock_prices']
        test_payoffs = analysis_result['payoff_data']['payoff_expiration']
        
        mid_idx = min(range(len(test_prices)), key=lambda i: abs(test_prices[i] - mid_price))
        
        if test_payoffs[mid_idx] > 0:
            # Profit is between BEs
            prob_profit = prob_between * 100
        else:
            # Profit is outside BEs
            prob_profit = (1 - prob_between) * 100
        
        return prob_profit
    
    return None


# ==================== MAX PAIN CALCULATOR ====================

def calculate_max_pain(option_chain, current_price):
    """
    Calculate max pain price (where options expire worthless).
    
    Args:
        option_chain: Option chain data
        current_price: Current stock price
    
    Returns:
        float: Max pain price
    """
    if not option_chain or option_chain['calls'].empty:
        return current_price
    
    # Get all strikes
    all_strikes = set()
    if not option_chain['calls'].empty:
        all_strikes.update(option_chain['calls']['strike'].unique())
    if not option_chain['puts'].empty:
        all_strikes.update(option_chain['puts']['strike'].unique())
    
    all_strikes = sorted(list(all_strikes))
    
    # Calculate total loss at each strike
    max_pain_strike = current_price
    min_total_loss = float('inf')
    
    for strike in all_strikes:
        total_loss = 0
        
        # Loss from calls
        for _, call in option_chain['calls'].iterrows():
            intrinsic = max(strike - call['strike'], 0)
            total_loss += intrinsic
        
        # Loss from puts
        if not option_chain['puts'].empty:
            for _, put in option_chain['puts'].iterrows():
                intrinsic = max(put['strike'] - strike, 0)
                total_loss += intrinsic
        
        if total_loss < min_total_loss:
            min_total_loss = total_loss
            max_pain_strike = strike
    
    return max_pain_strike


# ==================== STRATEGY COMPARISON ====================

def compare_strategies(strategy_results):
    """
    Compare multiple strategy analyses.
    
    Args:
        strategy_results: List of (strategy_name, analysis_result) tuples
    
    Returns:
        DataFrame: Comparison table
    """
    comparison = []
    
    for name, result in strategy_results:
        comparison.append({
            'Strategy': name,
            'Current P&L': result['current_pnl'],
            'Max Profit': result['max_profit'],
            'Max Loss': result['max_loss'],
            'R/R': result.get('risk_reward_ratio', 0),
            'Delta': result['greeks']['delta'],
            'Theta': result['greeks']['theta'],
            'Vega': result['greeks']['vega']
        })
    
    return pd.DataFrame(comparison)


# ==================== QUICK PRESETS ====================

QUICK_PRESETS = {
    'Bullish': {
        'strategies': ['Bull Call Spread', 'Long Call', 'Covered Call'],
        'description': 'Expecting moderate upward movement'
    },
    'Bearish': {
        'strategies': ['Bear Put Spread', 'Long Put', 'Protective Put'],
        'description': 'Expecting moderate downward movement'
    },
    'Neutral': {
        'strategies': ['Iron Condor', 'Short Straddle', 'Iron Butterfly'],
        'description': 'Expecting low volatility'
    },
    'High Volatility': {
        'strategies': ['Long Straddle', 'Long Strangle'],
        'description': 'Expecting large price movement'
    },
    'Income Generation': {
        'strategies': ['Covered Call', 'Cash-Secured Put', 'Iron Condor'],
        'description': 'Generate premium income'
    }
}


def get_strategy_suggestions(market_view):
    """Get strategy suggestions based on market view."""
    return QUICK_PRESETS.get(market_view, {}).get('strategies', [])


# ==================== ALERT THRESHOLDS ====================

def check_alerts(current_pnl, max_profit, max_loss, alert_settings):
    """
    Check if any alert conditions are met.
    
    Args:
        current_pnl: Current P&L
        max_profit: Max profit
        max_loss: Max loss
        alert_settings: Dict with alert thresholds
    
    Returns:
        list: List of triggered alerts
    """
    alerts = []
    
    # Profit target
    if alert_settings.get('profit_target'):
        target = alert_settings['profit_target']
        if current_pnl >= target:
            alerts.append(f"🎯 Profit target reached: ${current_pnl:.2f} >= ${target:.2f}")
    
    # Loss limit
    if alert_settings.get('loss_limit'):
        limit = alert_settings['loss_limit']
        if current_pnl <= -limit:
            alerts.append(f"⚠️ Loss limit reached: ${current_pnl:.2f} <= -${limit:.2f}")
    
    # % of max profit
    if alert_settings.get('pct_max_profit') and max_profit > 0:
        pct = alert_settings['pct_max_profit']
        threshold = max_profit * pct / 100
        if current_pnl >= threshold:
            alerts.append(f"📊 Reached {pct}% of max profit")
    
    # % of max loss
    if alert_settings.get('pct_max_loss') and max_loss < 0:
        pct = alert_settings['pct_max_loss']
        threshold = max_loss * pct / 100
        if current_pnl <= threshold:
            alerts.append(f"🚨 Reached {pct}% of max loss")
    
    return alerts


# ==================== POSITION SIZING ====================

def calculate_position_size(account_value, risk_percentage, max_loss_per_contract):
    """
    Calculate position size based on risk management.
    
    Args:
        account_value: Total account value
        risk_percentage: % of account to risk
        max_loss_per_contract: Max loss per contract
    
    Returns:
        dict: Position sizing recommendations
    """
    risk_amount = account_value * (risk_percentage / 100)
    
    if max_loss_per_contract < 0:
        max_contracts = int(risk_amount / abs(max_loss_per_contract))
    else:
        max_contracts = 1  # If no risk defined
    
    return {
        'max_contracts': max_contracts,
        'risk_amount': risk_amount,
        'total_risk': max_contracts * abs(max_loss_per_contract)
    }


# ==================== QUICK STATS ====================

def calculate_quick_stats(analysis_result, stock_price, days_to_exp, volatility):
    """Calculate additional quick statistics."""
    stats = {}
    
    # Profit range
    break_evens = analysis_result.get('break_evens', [])
    if len(break_evens) == 2:
        stats['profit_range'] = f"${min(break_evens):.2f} - ${max(break_evens):.2f}"
        stats['profit_range_width'] = abs(break_evens[1] - break_evens[0])
    elif len(break_evens) == 1:
        if analysis_result['max_profit'] > 0:
            stats['profit_above'] = f"> ${break_evens[0]:.2f}"
        else:
            stats['profit_below'] = f"< ${break_evens[0]:.2f}"
    
    # Return on risk
    if analysis_result['max_loss'] < 0:
        stats['return_on_risk'] = (analysis_result['max_profit'] / abs(analysis_result['max_loss'])) * 100
    
    # Probability of profit (if available)
    prob_profit = calculate_profit_probability(analysis_result, stock_price, days_to_exp, volatility)
    if prob_profit:
        stats['prob_profit'] = prob_profit
    
    # Days to break-even (rough estimate)
    if analysis_result['greeks']['theta'] != 0:
        days_to_be = -analysis_result['current_pnl'] / analysis_result['greeks']['theta']
        if days_to_be > 0 and days_to_be < days_to_exp:
            stats['days_to_breakeven'] = int(days_to_be)
    
    return stats
