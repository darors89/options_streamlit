# broker_integration.py - PyRofex and PyHomebroker Integration
"""
Integration with Argentine brokers:
- PyRofex for derivatives (Rofex market)
- PyHomebroker for equities (BYMA market)

All credentials are handled securely and not stored.
"""

# Global broker instances
_rofex_session = None
_homebroker_session = None


def connect_to_broker(broker_type, credentials):
    """
    Connect to broker using provided credentials.
    
    Args:
        broker_type: 'rofex' or 'homebroker'
        credentials: Dictionary with connection parameters
    
    Returns:
        tuple: (success: bool, message: str)
    """
    global _rofex_session, _homebroker_session
    
    try:
        if broker_type == 'rofex':
            # Try to import pyRofex
            try:
                import pyRofex
            except ImportError:
                return (False, "pyRofex not installed. Install with: pip install pyRofex")
            
            # Initialize connection
            environment = pyRofex.Environment.REMARKET if credentials['environment'] == 'REMARKET' else pyRofex.Environment.LIVE
            
            pyRofex.initialize(
                user=credentials['user'],
                password=credentials['password'],
                account=credentials['account'],
                environment=environment
            )
            
            _rofex_session = {
                'user': credentials['user'],
                'account': credentials['account'],
                'environment': credentials['environment']
            }
            
            return (True, f"✓ Connected to Rofex ({credentials['environment']})")
        
        elif broker_type == 'homebroker':
            # Try to import pyhomebroker
            try:
                from pyhomebroker import HomeBroker
            except ImportError:
                return (False, "pyhomebroker not installed. Install with: pip install pyhomebroker")
            
            # Initialize connection
            broker_id = int(credentials['broker_id'])
            hb = HomeBroker(broker_id)
            
            hb.auth.login(
                usuario=credentials['user'],
                password=credentials['password'],
                dni=credentials['dni']
            )
            
            _homebroker_session = {
                'broker': hb,
                'broker_id': broker_id,
                'user': credentials['user']
            }
            
            broker_names = {
                11: 'Balanz',
                12: 'Bull Market',
                121: 'Invertir Online',
                134: 'Portfolio Personal'
            }
            
            return (True, f"✓ Connected to {broker_names.get(broker_id, 'Homebroker')}")
        
        else:
            return (False, "Invalid broker type")
    
    except Exception as e:
        return (False, f"Connection failed: {str(e)}")


def get_market_data(ticker, broker_type='auto'):
    """
    Get market data for a ticker.
    
    Args:
        ticker: Ticker symbol
        broker_type: 'rofex', 'homebroker', or 'auto'
    
    Returns:
        Dictionary with market data or None if failed
    """
    global _rofex_session, _homebroker_session
    
    if broker_type == 'auto':
        # Determine broker based on ticker format
        if any(x in ticker.upper() for x in ['DLR', 'RFX', 'GGAL', 'YPF']):
            broker_type = 'rofex' if _rofex_session else 'homebroker'
        else:
            broker_type = 'homebroker' if _homebroker_session else 'rofex'
    
    try:
        if broker_type == 'rofex' and _rofex_session:
            import pyRofex
            
            # Get market data
            md = pyRofex.get_market_data(
                ticker=ticker,
                entries=[
                    pyRofex.MarketDataEntry.BIDS,
                    pyRofex.MarketDataEntry.OFFERS,
                    pyRofex.MarketDataEntry.LAST
                ]
            )
            
            return {
                'ticker': ticker,
                'last_price': md['marketData']['LA']['price'] if 'LA' in md['marketData'] else None,
                'bid': md['marketData']['BI'][0]['price'] if 'BI' in md['marketData'] else None,
                'ask': md['marketData']['OF'][0]['price'] if 'OF' in md['marketData'] else None,
                'source': 'rofex'
            }
        
        elif broker_type == 'homebroker' and _homebroker_session:
            hb = _homebroker_session['broker']
            
            # Get market data
            data = hb.online.get_market_data(
                ticker=ticker,
                settlement='spot'
            )
            
            return {
                'ticker': ticker,
                'last_price': data.get('last', None),
                'bid': data.get('bid', None),
                'ask': data.get('ask', None),
                'volume': data.get('volume', None),
                'source': 'homebroker'
            }
        
        else:
            return None
    
    except Exception as e:
        print(f"Error getting market data: {e}")
        return None


def get_option_chain(underlying, broker_type='auto'):
    """
    Get option chain for an underlying.
    
    Args:
        underlying: Underlying ticker symbol
        broker_type: 'rofex', 'homebroker', or 'auto'
    
    Returns:
        List of option contracts or None if failed
    """
    global _rofex_session, _homebroker_session
    
    try:
        if broker_type == 'rofex' and _rofex_session:
            import pyRofex
            
            # Get all instruments
            instruments = pyRofex.get_all_instruments()
            
            # Filter options for this underlying
            options = []
            for instrument in instruments.get('instruments', []):
                symbol = instrument['instrumentId']['symbol']
                
                # Check if this is an option of the underlying
                if underlying in symbol and ('C' in symbol or 'P' in symbol):
                    options.append({
                        'symbol': symbol,
                        'underlying': underlying,
                        'type': 'call' if 'C' in symbol else 'put',
                        'source': 'rofex'
                    })
            
            return options
        
        elif broker_type == 'homebroker' and _homebroker_session:
            hb = _homebroker_session['broker']
            
            # Search for options
            options = hb.online.search_options(underlying)
            
            formatted_options = []
            for opt in options:
                formatted_options.append({
                    'symbol': opt.get('symbol', ''),
                    'underlying': underlying,
                    'type': opt.get('type', '').lower(),
                    'strike': opt.get('strike', None),
                    'expiration': opt.get('expiration', None),
                    'source': 'homebroker'
                })
            
            return formatted_options
        
        else:
            return None
    
    except Exception as e:
        print(f"Error getting option chain: {e}")
        return None


def disconnect_broker(broker_type=None):
    """
    Disconnect from broker.
    
    Args:
        broker_type: 'rofex', 'homebroker', or None (disconnect all)
    """
    global _rofex_session, _homebroker_session
    
    if broker_type == 'rofex' or broker_type is None:
        _rofex_session = None
    
    if broker_type == 'homebroker' or broker_type is None:
        if _homebroker_session and _homebroker_session.get('broker'):
            try:
                # Logout if method exists
                if hasattr(_homebroker_session['broker'].auth, 'logout'):
                    _homebroker_session['broker'].auth.logout()
            except:
                pass
        _homebroker_session = None


def is_connected(broker_type=None):
    """
    Check if connected to broker.
    
    Args:
        broker_type: 'rofex', 'homebroker', or None (check any)
    
    Returns:
        bool: True if connected
    """
    global _rofex_session, _homebroker_session
    
    if broker_type == 'rofex':
        return _rofex_session is not None
    elif broker_type == 'homebroker':
        return _homebroker_session is not None
    else:
        return _rofex_session is not None or _homebroker_session is not None
