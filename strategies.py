# strategies.py - Options Strategies Definitions

# Strategy configurations with detailed leg information
STRATEGY_CONFIGS = {
    # Basic Strategies
    'Covered Call': {
        'description': 'Long stock + Short call',
        'has_stock': True,
        'legs': [
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call',
                'strikeLabel': 'Call Strike'
            }
        ]
    },
    'Protective Put': {
        'description': 'Long stock + Long put',
        'has_stock': True,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Protection)',
                'strikeLabel': 'Put Strike'
            }
        ]
    },
    'Covered Put': {
        'description': 'Short stock + Short put',
        'has_stock': True,
        'legs': [
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put',
                'strikeLabel': 'Put Strike'
            }
        ]
    },
    'Protective Call': {
        'description': 'Short stock + Long call',
        'has_stock': True,
        'legs': [
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Protection)',
                'strikeLabel': 'Call Strike'
            }
        ]
    },
    
    # Spreads
    'Bull Call Spread': {
        'description': 'Long lower strike call + Short higher strike call',
        'has_stock': False,
        'legs': [
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Lower Strike)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Upper Strike)',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    'Bear Put Spread': {
        'description': 'Long higher strike put + Short lower strike put',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Upper Strike)',
                'strikeLabel': 'Upper Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (Lower Strike)',
                'strikeLabel': 'Lower Strike'
            }
        ]
    },
    'Bull Put Spread': {
        'description': 'Short higher strike put + Long lower strike put',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (Upper Strike)',
                'strikeLabel': 'Upper Strike'
            },
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Lower Strike)',
                'strikeLabel': 'Lower Strike'
            }
        ]
    },
    'Bear Call Spread': {
        'description': 'Short lower strike call + Long higher strike call',
        'has_stock': False,
        'legs': [
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Lower Strike)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Upper Strike)',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    
    # Volatility Strategies
    'Long Straddle': {
        'description': 'Long call + Long put at same strike',
        'has_stock': False,
        'legs': [
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (ATM)',
                'strikeLabel': 'Strike (ATM)'
            },
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (ATM)',
                'strikeLabel': 'Strike (ATM)'
            }
        ]
    },
    'Short Straddle': {
        'description': 'Short call + Short put at same strike',
        'has_stock': False,
        'legs': [
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (ATM)',
                'strikeLabel': 'Strike (ATM)'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (ATM)',
                'strikeLabel': 'Strike (ATM)'
            }
        ]
    },
    'Long Strangle': {
        'description': 'Long OTM call + Long OTM put',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Lower Strike)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Upper Strike)',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    'Short Strangle': {
        'description': 'Short OTM call + Short OTM put',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (Lower Strike)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Upper Strike)',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    
    # Butterflies
    'Long Call Butterfly': {
        'description': 'Buy 1 lower call, Sell 2 middle calls, Buy 1 upper call',
        'has_stock': False,
        'legs': [
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Lower)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call 1 (Middle)',
                'strikeLabel': 'Middle Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call 2 (Middle)',
                'strikeLabel': 'Middle Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Upper)',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    'Long Put Butterfly': {
        'description': 'Buy 1 upper put, Sell 2 middle puts, Buy 1 lower put',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Upper)',
                'strikeLabel': 'Upper Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put 1 (Middle)',
                'strikeLabel': 'Middle Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put 2 (Middle)',
                'strikeLabel': 'Middle Strike'
            },
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Lower)',
                'strikeLabel': 'Lower Strike'
            }
        ]
    },
    'Iron Butterfly': {
        'description': 'Short straddle protected by long strangle',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Lower)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (ATM)',
                'strikeLabel': 'ATM Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (ATM)',
                'strikeLabel': 'ATM Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Upper)',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    
    # Condors
    'Iron Condor': {
        'description': 'OTM bull put spread + OTM bear call spread',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Lowest)',
                'strikeLabel': 'Lowest Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (Lower)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Upper)',
                'strikeLabel': 'Upper Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Highest)',
                'strikeLabel': 'Highest Strike'
            }
        ]
    },
    'Long Call Condor': {
        'description': 'Buy call spread, sell wider call spread',
        'has_stock': False,
        'legs': [
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Lowest)',
                'strikeLabel': 'Lowest Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Lower)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Upper)',
                'strikeLabel': 'Upper Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Highest)',
                'strikeLabel': 'Highest Strike'
            }
        ]
    },
    'Long Put Condor': {
        'description': 'Buy put spread, sell wider put spread',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Highest)',
                'strikeLabel': 'Highest Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (Upper)',
                'strikeLabel': 'Upper Strike'
            },
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put (Lower)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Lowest)',
                'strikeLabel': 'Lowest Strike'
            }
        ]
    },
    
    # Advanced Strategies
    'Collar': {
        'description': 'Long stock + Long put + Short call',
        'has_stock': True,
        'legs': [
            {
                'type': 'put',
                'position': 'long',
                'label': 'Long Put (Protection)',
                'strikeLabel': 'Lower Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call',
                'strikeLabel': 'Upper Strike'
            }
        ]
    },
    'Jade Lizard': {
        'description': 'Short OTM put + Short OTM call spread',
        'has_stock': False,
        'legs': [
            {
                'type': 'put',
                'position': 'short',
                'label': 'Short Put',
                'strikeLabel': 'Put Strike'
            },
            {
                'type': 'call',
                'position': 'short',
                'label': 'Short Call (Lower)',
                'strikeLabel': 'Lower Call Strike'
            },
            {
                'type': 'call',
                'position': 'long',
                'label': 'Long Call (Upper)',
                'strikeLabel': 'Upper Call Strike'
            }
        ]
    },
}

# Categories for UI organization
STRATEGY_CATEGORIES = [
    {
        'key': 'basic',
        'label': '📚 Basic',
        'strategies': ['Covered Call', 'Protective Put', 'Covered Put', 'Protective Call']
    },
    {
        'key': 'spreads',
        'label': '📊 Spreads',
        'strategies': ['Bull Call Spread', 'Bear Put Spread', 'Bull Put Spread', 'Bear Call Spread']
    },
    {
        'key': 'volatility',
        'label': '⚡ Volatility',
        'strategies': ['Long Straddle', 'Short Straddle', 'Long Strangle', 'Short Strangle']
    },
    {
        'key': 'butterflies',
        'label': '🦋 Butterflies',
        'strategies': ['Long Call Butterfly', 'Long Put Butterfly', 'Iron Butterfly']
    },
    {
        'key': 'condors',
        'label': '🦅 Condors',
        'strategies': ['Iron Condor', 'Long Call Condor', 'Long Put Condor']
    },
    {
        'key': 'advanced',
        'label': '🚀 Advanced',
        'strategies': ['Collar', 'Jade Lizard']
    }
]
