from typing import List
import pandas as pd
import matplotlib.pyplot as plt
from .types import Trade

def analyze_trades(trades: List[Trade]) -> pd.DataFrame:
    """Convert list of trades to DataFrame for analysis"""
    trade_data = []
    for trade in trades:
        trade_data.append({
            'entry_time': trade.entry_time,
            'exit_time': trade.exit_time,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'position': trade.position.name,
            'profit': trade.profit,
            'duration': trade.duration
        })
    return pd.DataFrame(trade_data)

def calculate_metrics(trades: List[Trade], initial_capital: float) -> pd.DataFrame:
    """Calculate extended trading metrics"""
    df = analyze_trades(trades)
    
    metrics = {
        'total_trades': len(df),
        'winning_trades': len(df[df['profit'] > 0]),
        'losing_trades': len(df[df['profit'] <= 0]),
        'win_rate': len(df[df['profit'] > 0]) / len(df) if len(df) > 0 else 0,
        'avg_win': df[df['profit'] > 0]['profit'].mean(),
        'avg_loss': df[df['profit'] <= 0]['profit'].mean(),
        'largest_win': df['profit'].max(),
        'largest_loss': df['profit'].min(),
        'avg_duration': df['duration'].mean(),
        'total_profit': df['profit'].sum(),
        'final_capital': initial_capital + df['profit'].sum()
    }
    
    return pd.Series(metrics)

def plot_equity_curve(equity_curve: pd.Series, drawdown_curve: pd.Series) -> None:
    """Plot equity curve with drawdown"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), 
                                  gridspec_kw={'height_ratios': [3, 1]})
    
    equity_curve.plot(ax=ax1, label='Equity')
    ax1.set_title('Equity Curve')
    ax1.set_ylabel('Portfolio Value ($)')
    ax1.legend()
    ax1.grid(True)
    
    drawdown_curve.plot(ax=ax2, label='Drawdown', color='red')
    ax2.set_title('Drawdown')
    ax2.set_ylabel('Drawdown (%)')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.show()

def plot_trade_analysis(trades: List[Trade]) -> None:
    """Plot comprehensive trade analysis"""
    df = analyze_trades(trades)
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # Profit distribution
    df['profit'].hist(ax=ax1, bins=30)
    ax1.set_title('Profit Distribution')
    ax1.set_xlabel('Profit ($)')
    ax1.set_ylabel('Frequency')
    
    # Cumulative profits
    df['profit'].cumsum().plot(ax=ax2)
    ax2.set_title('Cumulative Profits')
    ax2.set_xlabel('Trade Number')
    ax2.set_ylabel('Cumulative Profit ($)')
    
    # Duration distribution
    df['duration'].dt.total_seconds().hist(ax=ax3, bins=30)
    ax3.set_title('Trade Duration Distribution')
    ax3.set_xlabel('Duration (seconds)')
    ax3.set_ylabel('Frequency')
    
    # Win rate by month
    monthly_wins = df[df['profit'] > 0].groupby(df['exit_time'].dt.to_period('M')).size()
    monthly_total = df.groupby(df['exit_time'].dt.to_period('M')).size()
    (monthly_wins / monthly_total * 100).plot(ax=ax4, kind='bar')
    ax4.set_title('Monthly Win Rate')
    ax4.set_xlabel('Month')
    ax4.set_ylabel('Win Rate (%)')
    
    plt.tight_layout()
    plt.show()