# blackscholes.py - Black-Scholes Model Implementation
import numpy as np
from scipy.stats import norm

class BlackScholes:
    """
    Complete Black-Scholes option pricing model with Greeks.
    All calculations are transparent and verifiable.
    """
    
    @staticmethod
    def d1(S, K, T, r, sigma, q=0):
        """
        Calculate d1 parameter.
        
        Args:
            S: Stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
        """
        if T <= 0 or sigma <= 0:
            return 0
        
        return (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    @staticmethod
    def d2(S, K, T, r, sigma, q=0):
        """Calculate d2 parameter."""
        if T <= 0 or sigma <= 0:
            return 0
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        return d1_val - sigma * np.sqrt(T)
    
    @staticmethod
    def call_price(S, K, T, r, sigma, q=0):
        """
        Calculate European call option price.
        
        Formula:
        C = S * e^(-qT) * N(d1) - K * e^(-rT) * N(d2)
        """
        if T <= 0:
            return max(S - K, 0)
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        d2_val = BlackScholes.d2(S, K, T, r, sigma, q)
        
        call = S * np.exp(-q * T) * norm.cdf(d1_val) - K * np.exp(-r * T) * norm.cdf(d2_val)
        return max(call, 0)
    
    @staticmethod
    def put_price(S, K, T, r, sigma, q=0):
        """
        Calculate European put option price.
        
        Formula:
        P = K * e^(-rT) * N(-d2) - S * e^(-qT) * N(-d1)
        """
        if T <= 0:
            return max(K - S, 0)
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        d2_val = BlackScholes.d2(S, K, T, r, sigma, q)
        
        put = K * np.exp(-r * T) * norm.cdf(-d2_val) - S * np.exp(-q * T) * norm.cdf(-d1_val)
        return max(put, 0)
    
    @staticmethod
    def delta(S, K, T, r, sigma, option_type='call', q=0):
        """
        Calculate Delta - rate of change of option price with respect to stock price.
        
        Call Delta: e^(-qT) * N(d1)
        Put Delta: -e^(-qT) * N(-d1)
        """
        if T <= 0:
            if option_type == 'call':
                return 1 if S > K else 0
            else:
                return -1 if S < K else 0
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        
        if option_type == 'call':
            return np.exp(-q * T) * norm.cdf(d1_val)
        else:
            return -np.exp(-q * T) * norm.cdf(-d1_val)
    
    @staticmethod
    def gamma(S, K, T, r, sigma, q=0):
        """
        Calculate Gamma - rate of change of delta with respect to stock price.
        Same for calls and puts.
        
        Gamma: e^(-qT) * n(d1) / (S * sigma * sqrt(T))
        """
        if T <= 0:
            return 0
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        return np.exp(-q * T) * norm.pdf(d1_val) / (S * sigma * np.sqrt(T))
    
    @staticmethod
    def theta(S, K, T, r, sigma, option_type='call', q=0):
        """
        Calculate Theta - rate of change of option price with respect to time.
        Returns daily theta (divide by 365).
        """
        if T <= 0:
            return 0
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        d2_val = BlackScholes.d2(S, K, T, r, sigma, q)
        
        term1 = -(S * norm.pdf(d1_val) * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
        
        if option_type == 'call':
            term2 = r * K * np.exp(-r * T) * norm.cdf(d2_val)
            term3 = -q * S * np.exp(-q * T) * norm.cdf(d1_val)
            return (term1 - term2 + term3) / 365
        else:
            term2 = r * K * np.exp(-r * T) * norm.cdf(-d2_val)
            term3 = q * S * np.exp(-q * T) * norm.cdf(-d1_val)
            return (term1 + term2 - term3) / 365
    
    @staticmethod
    def vega(S, K, T, r, sigma, q=0):
        """
        Calculate Vega - rate of change of option price with respect to volatility.
        Same for calls and puts.
        Returns vega per 1% change in volatility.
        """
        if T <= 0:
            return 0
        
        d1_val = BlackScholes.d1(S, K, T, r, sigma, q)
        return S * np.exp(-q * T) * norm.pdf(d1_val) * np.sqrt(T) / 100
    
    @staticmethod
    def rho(S, K, T, r, sigma, option_type='call', q=0):
        """
        Calculate Rho - rate of change of option price with respect to interest rate.
        Returns rho per 1% change in interest rate.
        """
        if T <= 0:
            return 0
        
        d2_val = BlackScholes.d2(S, K, T, r, sigma, q)
        
        if option_type == 'call':
            return K * T * np.exp(-r * T) * norm.cdf(d2_val) / 100
        else:
            return -K * T * np.exp(-r * T) * norm.cdf(-d2_val) / 100


def analyze_strategy(strategy_name, stock_price, legs, days_to_expiration, 
                     volatility, risk_free_rate, dividend_yield=0):
    """
    Analyze an options strategy using Black-Scholes model.
    
    Args:
        strategy_name: Name of the strategy
        stock_price: Current stock price
        legs: List of option legs with type, position, strike, premium
        days_to_expiration: Days until expiration
        volatility: Implied volatility (decimal)
        risk_free_rate: Risk-free rate (decimal)
        dividend_yield: Dividend yield (decimal)
    
    Returns:
        Dictionary with analysis results
    """
    T = days_to_expiration / 365  # Convert to years
    
    # Calculate current P&L and Greeks
    current_pnl = 0
    total_delta = 0
    total_gamma = 0
    total_theta = 0
    total_vega = 0
    total_rho = 0
    
    for leg in legs:
        # Current option value
        if leg['type'] == 'call':
            current_value = BlackScholes.call_price(
                stock_price, leg['strike'], T, risk_free_rate, volatility, dividend_yield
            )
            delta = BlackScholes.delta(
                stock_price, leg['strike'], T, risk_free_rate, volatility, 'call', dividend_yield
            )
            theta = BlackScholes.theta(
                stock_price, leg['strike'], T, risk_free_rate, volatility, 'call', dividend_yield
            )
            rho = BlackScholes.rho(
                stock_price, leg['strike'], T, risk_free_rate, volatility, 'call', dividend_yield
            )
        else:  # put
            current_value = BlackScholes.put_price(
                stock_price, leg['strike'], T, risk_free_rate, volatility, dividend_yield
            )
            delta = BlackScholes.delta(
                stock_price, leg['strike'], T, risk_free_rate, volatility, 'put', dividend_yield
            )
            theta = BlackScholes.theta(
                stock_price, leg['strike'], T, risk_free_rate, volatility, 'put', dividend_yield
            )
            rho = BlackScholes.rho(
                stock_price, leg['strike'], T, risk_free_rate, volatility, 'put', dividend_yield
            )
        
        # Greeks (same for calls and puts)
        gamma = BlackScholes.gamma(
            stock_price, leg['strike'], T, risk_free_rate, volatility, dividend_yield
        )
        vega = BlackScholes.vega(
            stock_price, leg['strike'], T, risk_free_rate, volatility, dividend_yield
        )
        
        # Multiplier for long/short
        multiplier = 1 if leg['position'] == 'long' else -1
        
        # P&L = (Current Value - Premium Paid) * 100 shares * multiplier
        current_pnl += multiplier * (current_value - leg['premium']) * 100
        
        # Aggregate Greeks
        total_delta += multiplier * delta * 100
        total_gamma += multiplier * gamma * 100
        total_theta += multiplier * theta * 100
        total_vega += multiplier * vega * 100
        total_rho += multiplier * rho * 100
    
    # Generate payoff data
    price_range = np.linspace(stock_price * 0.5, stock_price * 1.5, 300)
    payoff_expiration = []
    payoff_current = []
    
    for S in price_range:
        # At expiration (intrinsic value only)
        payoff_exp = 0
        payoff_curr = 0
        
        for leg in legs:
            # Intrinsic value at expiration
            if leg['type'] == 'call':
                intrinsic = max(S - leg['strike'], 0)
                # Current value
                current_val = BlackScholes.call_price(
                    S, leg['strike'], T, risk_free_rate, volatility, dividend_yield
                )
            else:
                intrinsic = max(leg['strike'] - S, 0)
                current_val = BlackScholes.put_price(
                    S, leg['strike'], T, risk_free_rate, volatility, dividend_yield
                )
            
            multiplier = 1 if leg['position'] == 'long' else -1
            
            payoff_exp += multiplier * (intrinsic - leg['premium']) * 100
            payoff_curr += multiplier * (current_val - leg['premium']) * 100
        
        payoff_expiration.append(payoff_exp)
        payoff_current.append(payoff_curr)
    
    # Find max profit and max loss
    max_profit = max(payoff_expiration)
    max_loss = min(payoff_expiration)
    
    # Find break-even points
    break_evens = []
    for i in range(len(payoff_expiration) - 1):
        if payoff_expiration[i] * payoff_expiration[i+1] < 0:
            # Linear interpolation to find exact break-even
            be = price_range[i] - payoff_expiration[i] * (price_range[i+1] - price_range[i]) / \
                 (payoff_expiration[i+1] - payoff_expiration[i])
            break_evens.append(float(be))
    
    # Risk/Reward ratio
    risk_reward_ratio = None
    if max_loss < 0 and max_profit > 0:
        risk_reward_ratio = max_profit / abs(max_loss)
    
    return {
        'current_pnl': float(current_pnl),
        'max_profit': float(max_profit),
        'max_loss': float(max_loss),
        'break_evens': break_evens,
        'greeks': {
            'delta': float(total_delta),
            'gamma': float(total_gamma),
            'theta': float(total_theta),
            'vega': float(total_vega),
            'rho': float(total_rho),
        },
        'risk_reward_ratio': float(risk_reward_ratio) if risk_reward_ratio else None,
        'payoff_data': {
            'stock_prices': price_range.tolist(),
            'payoff_expiration': payoff_expiration,
            'payoff_current': payoff_current,
        }
    }
