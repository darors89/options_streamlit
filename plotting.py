# plotting.py - Plotly Visualizations
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def plot_payoff_chart(result, stock_price, strategy_name, legs):
    """
    Create interactive payoff diagram with Plotly.
    
    Shows:
    - Main strategy P&L at expiration (blue line)
    - Current P&L (green line)
    - Individual leg P&L (translucent lines)
    - Break-even points
    - Current stock price marker
    """
    prices = result['payoff_data']['stock_prices']
    payoff_exp = result['payoff_data']['payoff_expiration']
    payoff_curr = result['payoff_data']['payoff_current']
    
    fig = go.Figure()
    
    # Individual legs (translucent)
    if legs:
        for idx, leg in enumerate(legs):
            leg_payoff = []
            for price in prices:
                if leg['type'] == 'call':
                    intrinsic = max(price - leg['strike'], 0)
                else:
                    intrinsic = max(leg['strike'] - price, 0)
                
                multiplier = 1 if leg['position'] == 'long' else -1
                payoff = multiplier * (intrinsic - leg['premium']) * 100
                leg_payoff.append(payoff)
            
            # Color based on type and position
            if leg['type'] == 'call':
                color = 'rgba(16, 185, 129, 0.3)' if leg['position'] == 'long' else 'rgba(239, 68, 68, 0.3)'
            else:
                color = 'rgba(59, 130, 246, 0.3)' if leg['position'] == 'long' else 'rgba(139, 92, 246, 0.3)'
            
            fig.add_trace(go.Scatter(
                x=prices,
                y=leg_payoff,
                mode='lines',
                name=f"{leg['position'].title()} {leg['type'].title()} @{leg['strike']:.0f}",
                line=dict(color=color, width=1, dash='dot'),
                hovertemplate='Price: $%{x:.2f}<br>P&L: $%{y:.2f}<extra></extra>'
            ))
    
    # Current P&L (green)
    fig.add_trace(go.Scatter(
        x=prices,
        y=payoff_curr,
        mode='lines',
        name='Current P&L',
        line=dict(color='#22c55e', width=2),
        hovertemplate='Price: $%{x:.2f}<br>Current P&L: $%{y:.2f}<extra></extra>'
    ))
    
    # P&L at expiration (blue, bold)
    fig.add_trace(go.Scatter(
        x=prices,
        y=payoff_exp,
        mode='lines',
        name='At Expiration',
        line=dict(color='#3b82f6', width=3),
        hovertemplate='Price: $%{x:.2f}<br>P&L at Exp: $%{y:.2f}<extra></extra>'
    ))
    
    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # Current stock price marker
    fig.add_vline(
        x=stock_price,
        line_dash="dash",
        line_color="#3b82f6",
        annotation_text="Current",
        annotation_position="top"
    )
    
    # Break-even markers
    for idx, be in enumerate(result['break_evens']):
        fig.add_vline(
            x=be,
            line_dash="dot",
            line_color="#f59e0b",
            annotation_text=f"BE {idx+1}",
            annotation_position="top"
        )
    
    # Layout
    fig.update_layout(
        title=f"{strategy_name} - Payoff Diagram",
        xaxis_title="Stock Price ($)",
        yaxis_title="Profit/Loss ($)",
        hovermode='x unified',
        template='plotly_dark',
        height=500,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig


def plot_volatility_surface(legs, stock_price, days_to_expiration):
    """
    Create 3D volatility surface visualization.
    
    Shows:
    - IV surface across strikes and maturities
    - Marks the strategy's options
    """
    # Generate sample volatility surface
    strikes = np.linspace(stock_price * 0.7, stock_price * 1.3, 20)
    dtes = np.array([7, 14, 30, 60, 90, 120, 180])
    
    # Create mesh
    strike_mesh, dte_mesh = np.meshgrid(strikes, dtes)
    
    # Simple IV smile model
    iv_surface = np.zeros_like(strike_mesh)
    for i in range(len(dtes)):
        for j in range(len(strikes)):
            moneyness = strikes[j] / stock_price
            atm_distance = abs(moneyness - 1)
            
            # Base IV increases with time
            base_iv = 0.20 + (dtes[i] / 365) * 0.15
            
            # Smile effect
            smile = atm_distance * 0.3
            
            # Add noise
            noise = np.random.normal(0, 0.02)
            
            iv_surface[i, j] = base_iv + smile + noise
    
    # Create 3D surface
    fig = go.Figure(data=[
        go.Surface(
            x=strike_mesh,
            y=dte_mesh,
            z=iv_surface,
            colorscale='Viridis',
            name='IV Surface',
            hovertemplate='Strike: $%{x:.2f}<br>DTE: %{y}<br>IV: %{z:.2%}<extra></extra>'
        )
    ])
    
    # Mark strategy options
    if legs:
        strategy_strikes = [leg['strike'] for leg in legs]
        strategy_dtes = [days_to_expiration] * len(legs)
        
        # Interpolate IV for strategy strikes
        strategy_ivs = []
        for strike in strategy_strikes:
            moneyness = strike / stock_price
            atm_distance = abs(moneyness - 1)
            base_iv = 0.20 + (days_to_expiration / 365) * 0.15
            smile = atm_distance * 0.3
            strategy_ivs.append(base_iv + smile)
        
        # Add markers for strategy options
        fig.add_trace(go.Scatter3d(
            x=strategy_strikes,
            y=strategy_dtes,
            z=strategy_ivs,
            mode='markers',
            marker=dict(
                size=10,
                color='#f59e0b',
                symbol='diamond',
                line=dict(color='#fbbf24', width=2)
            ),
            name='Strategy Options',
            hovertemplate='Strike: $%{x:.2f}<br>DTE: %{y}<br>IV: %{z:.2%}<extra></extra>'
        ))
    
    # Layout
    fig.update_layout(
        title="Volatility Surface",
        scene=dict(
            xaxis_title="Strike ($)",
            yaxis_title="Days to Expiration",
            zaxis_title="Implied Volatility",
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.3)
            )
        ),
        template='plotly_dark',
        height=600
    )
    
    return fig


def create_pnl_table(result, stock_price):
    """
    Create P&L table at different stock prices.
    
    Returns DataFrame with:
    - Price
    - P&L at Expiration
    - Current P&L
    - % Change from current price
    """
    prices = result['payoff_data']['stock_prices']
    payoff_exp = result['payoff_data']['payoff_expiration']
    payoff_curr = result['payoff_data']['payoff_current']
    
    # Sample every Nth point for readability
    step = len(prices) // 15
    if step < 1:
        step = 1
    
    indices = list(range(0, len(prices), step))
    if len(prices) - 1 not in indices:
        indices.append(len(prices) - 1)
    
    # Find index closest to current stock price
    closest_idx = min(range(len(prices)), key=lambda i: abs(prices[i] - stock_price))
    if closest_idx not in indices:
        indices.append(closest_idx)
    indices.sort()
    
    data = []
    for idx in indices:
        price = prices[idx]
        pnl_exp = payoff_exp[idx]
        pnl_curr = payoff_curr[idx]
        pct_change = ((price - stock_price) / stock_price) * 100
        
        is_current = abs(price - stock_price) < (stock_price * 0.01)
        
        data.append({
            'Price': f"${price:.2f}{'  ←' if is_current else ''}",
            'At Expiration': f"${pnl_exp:+.2f}",
            'Current P&L': f"${pnl_curr:+.2f}",
            '% Change': f"{pnl_exp:+.1f}%"
        })
    
    df = pd.DataFrame(data)
    
    # Style function for coloring
    def color_pnl(val):
        if isinstance(val, str) and val.startswith('$'):
            num = float(val.replace('$', '').replace('+', '').replace(',', ''))
            color = '#22c55e' if num >= 0 else '#ef4444'
            return f'color: {color}'
        return ''
    
    return df
