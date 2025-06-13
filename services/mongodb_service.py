import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from eodhd import APIClient
from tqdm import tqdm
import requests
import time

logger = logging.getLogger(__name__)

class MongoDBService:
    def __init__(self):
        """Initialize MongoDB connection."""
        try:
            # Get MongoDB connection details from environment variables
            host = os.getenv('MONGODB_HOST', 'db')
            port = int(os.getenv('MONGODB_PORT', '27017'))
            username = os.getenv('MONGODB_USERNAME')
            password = os.getenv('MONGODB_PASSWORD')
            database = os.getenv('MONGODB_DATABASE', 'stockfinder')
        

            # Create MongoDB connection string
            if username and password:
                connection_string = f"mongodb://{username}:{password}@{host}:{port}"
            else:
                connection_string = f"mongodb://{host}:{port}"

            # Connect to MongoDB
            self.client = MongoClient(connection_string)
            self.db = self.client[database]
            
            # Initialize collections
            self.tickers = self.db.tickers
            self.fundamentals = self.db.fundamentals
            
            # Initialize EODHD client
            self.eodhd = APIClient(os.getenv('EODHD_API_KEY'))
            
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {str(e)}")
            raise

    def get_exchanges(self) -> List[Dict[str, Any]]:
        """
        Get exchanges from EODHD API.
        Only returns exchanges from countries specified in COUNTRIES environment variable.
        
        Returns:
            List[Dict]: List of matching exchanges
        """
        try:
            # Get countries from environment variable
            countries_str = os.getenv('COUNTRIES', '')
            
            # Split countries string into list and strip whitespace
            if countries_str:
                target_countries = [country.strip() for country in countries_str.split(',')]
            
            # Get exchanges from EODHD
            exchanges_df = self.eodhd.get_exchanges()
            if exchanges_df is None or exchanges_df.empty:
                logger.warning("No exchanges found in EODHD API response")
                return []

            # Convert DataFrame to list of dictionaries
            all_exchanges = exchanges_df.to_dict('records')
            if not all_exchanges:
                logger.warning("No exchanges found after converting DataFrame")
                return []

            # Filter exchanges by target countries
            if not countries_str:
                return all_exchanges
            
            matching_exchanges = [
                exchange for exchange in all_exchanges 
                if exchange.get('Country') in target_countries
            ]
            
            return matching_exchanges
        except Exception as e:
            logger.error(f"Error getting exchanges: {str(e)}")
            return []

    def fetch_tickers(self, exchange: str) -> None:
        """
        Get tickers for an exchange from EODHD API and save them to MongoDB.
        
        Args:
            exchange (str): Exchange code
        """
        try:
            # Get tickers from EODHD
            tickers_df = self.eodhd.get_exchange_symbols(exchange)
            if tickers_df is None or tickers_df.empty:
                logger.warning(f"No tickers found for exchange {exchange}")
                return

            # Convert DataFrame to list of dictionaries
            tickers = tickers_df.to_dict('records')
            if not tickers:
                logger.warning(f"No tickers found after converting DataFrame for exchange {exchange}")
                return

            # Filter for Common Stock only
            tickers = [ticker for ticker in tickers if ticker.get('Type') == 'Common Stock']
            if not tickers:
                logger.warning(f"No Common Stock tickers found for exchange {exchange}")
                return

            # Process tickers to keep only required fields
            processed_tickers = []
            for ticker in tickers:
                processed_ticker = {
                    'Symbol': f"{ticker.get('Code')}.{exchange}",
                    'Name': ticker.get('Name'),
                    'Country': ticker.get('Country'),
                    'fundamentals_saved': False
                }
                processed_tickers.append(processed_ticker)

            # Insert all tickers at once
            self.tickers.insert_many(processed_tickers)
            logger.info(f"Inserted {len(processed_tickers)} tickers for exchange {exchange}")
            
        except Exception as e:
            logger.error(f"Error getting tickers for exchange {exchange}: {str(e)}")

    def get_fundamentals(self, symbol: str) -> None:
        """
        Get fundamental data for a ticker from EODHD API and save to MongoDB.
        Only inserts new data, does not update existing records.
        
        Args:
            symbol (str): Ticker symbol with exchange (e.g., 'AAPL.US')
            
        Returns:
            Optional[Dict]: Fundamental data if found, None otherwise
        """
        try:
            # Check if fundamentals already exist
            existing = self.fundamentals.find_one({'symbol': symbol})
            if existing:
                logger.info(f"Fundamentals already exist for {symbol}")
                return

            # Get fundamentals from EODHD
            fundamentals = self.eodhd.get_fundamentals_data(ticker=symbol)
            if not fundamentals:
                return

            # Insert into MongoDB
            self.fundamentals.insert_one(fundamentals)
            
            # Update ticker's fundamentals_saved flag
            self.tickers.update_one(
                {'Symbol': symbol},
                {'$set': {'fundamentals_saved': True, 'updated_at': datetime.now(timezone.utc)}},
                upsert=True
            )
            
            return fundamentals
        except Exception as e:
            logger.error(f"Error getting fundamentals for {symbol}: {str(e)}")
            return

    def collect_fundamentals(self, batch_size: int, minutes_to_wait: int) -> None:
        """
        Collect fundamental data for all tickers in the database that haven't had fundamentals saved yet.
        Processes tickers in batches to avoid memory or rate-limit issues.
        Args:
            batch_size (int): Number of tickers to process per batch.
            time_to_wait (int): Seconds to wait before retrying if not enough API calls are available.
        """
        logger.info("Collecting fundamental data for unsaved tickers in batches")
        
        # Get all tickers without fundamentals from MongoDB
        tickers_cursor = self.tickers.find({'fundamentals_saved': {'$eq': False}})
        tickers = list(tickers_cursor)
        
        if not tickers:
            logger.info("No unsaved tickers found in database")
            return

        logger.info(f"Found {len(tickers)} unsaved tickers")

        # Process in batches
        for i in range(0, len(tickers), batch_size):
            tickers_left = len(tickers) - i
            logger.info(f"Unprocessed tickers: {tickers_left}")
            while True:
                # Check remaining API calls before each batch
                remaining_calls = self.get_eodhd_remaining_api_calls()
                if remaining_calls is not None and batch_size * 10 > remaining_calls:
                    logger.warning(f"Not enough EODHD API calls remaining ({remaining_calls}) to process next batch of size {batch_size}. Waiting before retrying.")
                    logger.info(f"Waiting {minutes_to_wait} minutes before retrying...")
                    time.sleep(minutes_to_wait * 60)  # Convert minutes to seconds
                    continue
                break
            batch = tickers[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} tickers)")
            for ticker in tqdm(batch, desc=f"Batch {i//batch_size + 1}"):
                symbol = ticker.get('Symbol')
                if not symbol:
                    continue
                fundamentals = self.get_fundamentals(symbol)
                if not fundamentals:
                    logger.warning(f"No fundamentals found for ticker: {symbol}")
                    continue
                logger.info(f"Processed ticker: {symbol}")
        logger.info("Finished processing all batches.")

    def get_eodhd_remaining_api_calls(self) -> Optional[int]:
        """
        Check the remaining API calls (rate limit) for the EODHD API key using the /user endpoint.
        Returns:
            Optional[int]: Number of remaining API calls, or None if unavailable.
        """
        try:
            api_token = os.getenv('EODHD_API_KEY')
            url = f"https://eodhd.com/api/user?api_token={api_token}"
            response = requests.get(url)
            if response.status_code != 200:
                logger.warning(f"EODHD /user API returned status {response.status_code}")
                return None
            data = response.json()
            daily_limit = data.get('dailyRateLimit')
            used = data.get('apiRequests')
            extra = data.get('extraLimit', 0) or 0
            if daily_limit is not None and used is not None:
                remaining = int(daily_limit) + int(extra) - int(used)
                logger.info(f"EODHD API remaining calls: {remaining}")
                return remaining
            else:
                logger.warning("EODHD /user API did not return dailyRateLimit or apiRequests")
                return None
        except Exception as e:
            logger.error(f"Error checking EODHD API remaining calls: {str(e)}")
            return None