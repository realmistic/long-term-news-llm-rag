import pandas as pd
import yfinance as yf
from datetime import timedelta
from tqdm import tqdm
import warnings
import sys
import traceback
import logging

# Set up logging
logging.basicConfig(
    filename='market_stats.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
input_file_path = 'data/news_feed_flattened.parquet'
output_file_path = 'data/news_feed_with_market_stats.parquet'

def calculate_market_metrics(df):
    """Calculate market metrics for all tickers in bulk."""
    # Get unique tickers and date ranges
    tickers = df[df['type'] == 'individual']['ticker'].unique().tolist()
    tickers.append('^GSPC')  # Add S&P 500
    
    # Convert dates to datetime and localize to UTC
    df['end_date'] = pd.to_datetime(df['end_date']).dt.tz_localize(None)
    
    # Get date range
    start_date = df['end_date'].min() - timedelta(days=10)  # Extra days for weekly calc
    end_date = df['end_date'].max() + timedelta(days=1)
    
    print(f"Downloading historical data for {len(tickers)} tickers")
    
    # Download historical data for all tickers at once
    all_history = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        for ticker in tqdm(tickers, desc="Downloading ticker data"):
            try:
                ticker_obj = yf.Ticker(ticker)
                hist = ticker_obj.history(start=start_date, end=end_date)
                if not hist.empty:
                    all_history[ticker] = hist
            except Exception as e:
                print(f"Error downloading data for {ticker}: {str(e)}")
    
    # Calculate returns for each ticker
    returns_data = []
    for ticker, hist in all_history.items():
        # Calculate daily and weekly returns for each date
        for date in pd.to_datetime(df['end_date'].unique()):
            try:
                # Convert hist index to UTC for comparison
                hist_index = hist.index.tz_localize(None)
                # Get relevant prices
                date_idx = hist_index.get_indexer([date], method='ffill')[0]
                if date_idx < 0 or date_idx >= len(hist):
                    continue
                
                end_price = hist['Close'].iloc[date_idx]
                
                # Daily return
                if date_idx > 0:
                    start_price_daily = hist['Close'].iloc[date_idx-1]
                    daily_return = (end_price - start_price_daily) / start_price_daily
                else:
                    daily_return = None
                
                # Weekly return (5 trading days)
                if date_idx >= 5:
                    start_price_weekly = hist['Close'].iloc[date_idx-5]
                    weekly_return = (end_price - start_price_weekly) / start_price_weekly
                else:
                    weekly_return = None
                
                returns_data.append({
                    'ticker': ticker,
                    'date': date,
                    'daily_return': daily_return,
                    'weekly_return': weekly_return
                })
            except Exception as e:
                print(f"Error calculating returns for {ticker} on {date}: {str(e)}")
    
    # Convert to DataFrame and pivot for easier joining
    returns_df = pd.DataFrame(returns_data)
    
    # Calculate market metrics more efficiently using unique combinations
    unique_combinations = df[['end_date', 'ticker', 'type']].drop_duplicates()
    market_metrics = []
    
    for _, row in unique_combinations.iterrows():
        date = pd.to_datetime(row['end_date'])
        ticker = row['ticker'] if row['type'] == 'individual' else 'multiple_tickers'
        
        # Get market returns for this date
        market_data = returns_df[
            (returns_df['date'] == date) & 
            (returns_df['ticker'] == '^GSPC')
        ]
        market_data = market_data.iloc[0] if not market_data.empty else pd.Series()
        
        # Get ticker returns for individual stocks
        if ticker != 'multiple_tickers':
            ticker_data = returns_df[
                (returns_df['date'] == date) & 
                (returns_df['ticker'] == ticker)
            ]
            ticker_data = ticker_data.iloc[0] if not ticker_data.empty else pd.Series()
            
            weekly_return = ticker_data.get('weekly_return')
            market_weekly_return = market_data.get('weekly_return')
            growth_above_market = (
                weekly_return - market_weekly_return 
                if weekly_return is not None and market_weekly_return is not None 
                else None
            )
        else:
            # For non-individual entries (multiple_tickers), use market returns for all metrics
            weekly_return = market_data.get('weekly_return')
            market_weekly_return = market_data.get('weekly_return')
            growth_above_market = None  # No growth above market since it is the market
        
        market_metrics.append({
            'date': date,
            'ticker': ticker,
            'weekly_return': weekly_return,
            'market_daily_return': market_data.get('daily_return'),
            'market_weekly_return': market_data.get('weekly_return'),
            'growth_above_market': growth_above_market
        })
    
    return pd.DataFrame(market_metrics)

def main():
    print(f"Reading data from {input_file_path}")
    df = pd.read_parquet(input_file_path)
    # Ensure end_date is datetime
    df['end_date'] = pd.to_datetime(df['end_date'])
    print(f"Loaded {len(df)} entries")
    
    # Calculate market metrics
    print("Calculating market metrics...")
    market_metrics = calculate_market_metrics(df)
    
    # Merge market metrics with original data
    print("Merging market metrics with original data...")
    print(f"Original DataFrame shape: {df.shape}")
    print(f"Market metrics DataFrame shape: {market_metrics.shape}")
    
    # Ensure date columns are in the same timezone-naive format
    market_metrics['date'] = pd.to_datetime(market_metrics['date']).dt.tz_localize(None)
    df['end_date'] = pd.to_datetime(df['end_date']).dt.tz_localize(None)
    
    # Debug info before merge
    print("\nSample dates from original DataFrame:")
    print(df['end_date'].head())
    print("\nSample dates from market metrics:")
    print(market_metrics['date'].head())
    
    # Check for duplicates
    print("\nChecking for duplicates in original DataFrame:")
    duplicates = df.groupby(['end_date', 'ticker']).size().reset_index(name='count')
    duplicates = duplicates[duplicates['count'] > 1]
    if not duplicates.empty:
        print("Found duplicates in original DataFrame:")
        print(duplicates.head())
    
    print("\nChecking for duplicates in market metrics:")
    metric_duplicates = market_metrics.groupby(['date', 'ticker']).size().reset_index(name='count')
    metric_duplicates = metric_duplicates[metric_duplicates['count'] > 1]
    if not metric_duplicates.empty:
        print("Found duplicates in market metrics:")
        print(metric_duplicates.head())
    
    # Merge market metrics with original data
    print("\nMerging market metrics with original data...")
    
    # Ensure we only merge the market metrics columns we need
    market_metrics_subset = market_metrics[[
        'date', 'ticker', 
        'weekly_return', 'market_daily_return', 
        'market_weekly_return', 'growth_above_market'
    ]]
    
    # Drop existing market metrics columns if they exist
    columns_to_drop = ['weekly_return', 'market_daily_return', 'market_weekly_return', 'growth_above_market']
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])

    # Merge with market metrics
    df = pd.merge(
        df,
        market_metrics_subset,
        left_on=['end_date', 'ticker'],
        right_on=['date', 'ticker'],
        how='left'
    ).drop('date', axis=1)
    
    print(f"\nMerged DataFrame shape: {df.shape}")
    print("Columns in merged DataFrame:", df.columns.tolist())
    
    print(f"\nEnhanced DataFrame shape: {df.shape}")
    print("Columns in enhanced DataFrame:", df.columns.tolist())
    
    # Verify market metrics columns exist and have data
    print("\nVerifying market metrics before saving:")
    market_cols = ['weekly_return', 'market_daily_return', 'market_weekly_return', 'growth_above_market']
    for col in market_cols:
        if col in df.columns:
            non_null_count = df[col].count()
            print(f"{col}: {non_null_count} non-null values out of {len(df)} rows")
        else:
            print(f"WARNING: Column {col} is missing!")
    
    # Ensure all required columns are present
    print("\nAll columns in DataFrame:", sorted(df.columns.tolist()))
    
    # Save enhanced dataset only if market metrics columns exist
    if all(col in df.columns for col in market_cols):
        print(f"\nSaving enhanced dataset to {output_file_path}")
        df.to_parquet(output_file_path, compression="brotli")
        print(f"Saved {len(df)} entries with market metrics")
    else:
        raise ValueError("Market metrics columns are missing from the DataFrame!")
    
    # Print sample of the data to verify
    print("\nSample of the enhanced data:")
    print(df[['ticker', 'end_date']].head())
    print("\nMarket metrics columns:")
    market_cols = ['weekly_return', 'market_daily_return', 'market_weekly_return', 'growth_above_market']
    for col in market_cols:
        if col in df.columns:
            print(f"\n{col}:")
            print(df[col].head())
        else:
            print(f"\n{col} not found in DataFrame")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_msg = f"Error occurred: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Print to console
        logging.error(error_msg)  # Log to file
