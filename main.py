import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from services.mongodb_service import MongoDBService

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def validate_environment() -> List[str]:
    """
    Validate required environment variables and return list of countries.
    
    Returns:
        List[str]: List of valid countries, empty list if COUNTRIES not specified
        
    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    # Check EODHD API key
    api_key = os.getenv('EODHD_API_KEY')
    if not api_key:
        raise ValueError("EODHD_API_KEY environment variable is not set")

    # Validate BATCH_SIZE
    batch_size = os.getenv('BATCH_SIZE', 100)
    if batch_size is not None:
        try:
            if int(batch_size) <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("BATCH_SIZE environment variable must be a positive integer")

    # Validate MINUTES_TO_WAIT
    minutes_to_wait = os.getenv('MINUTES_TO_WAIT', 10)
    if minutes_to_wait is not None:
        try:
            if int(minutes_to_wait) <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("MINUTES_TO_WAIT environment variable must be a positive integer")

    # Get countries from environment variable (optional)
    countries_str = os.getenv('COUNTRIES', '')
    if not countries_str:
        logger.info("No countries specified in COUNTRIES environment variable, will process all countries")
        return []

    # Split countries string into list
    countries = [country.strip() for country in countries_str.split(',')]
    if not countries:
        logger.info("No valid countries found in COUNTRIES environment variable, will process all countries")
        return []
        
    return

def main():
    """Main function to run the data collection process."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Validate environment
        validate_environment()

        # Initialize MongoDB service
        mongo_service = MongoDBService()
        
        # Check if tickers collection is empty
        if mongo_service.tickers.count_documents({}) > 0:
            logger.info("Tickers collection is not empty, skipping ticker fetch")
        else:
            # Get exchanges and fetch tickers
            exchanges = mongo_service.get_exchanges()
            if not exchanges:
                logger.warning("No exchanges found")
                return

            # Process each exchange
            for exchange in exchanges:
                exchange_code = exchange.get('Code')
                if not exchange_code:
                    continue

                logger.info(f"Fetching tickers for exchange: {exchange_code}")
                mongo_service.fetch_tickers(exchange_code)
        
        # Get batch size and wait time from environment variables
        batch_size = os.getenv('BATCH_SIZE', 100)
        minutes_to_wait = os.getenv('MINUTES_TO_WAIT', 10)
        
        # Collect fundamentals for all tickers
        mongo_service.collect_fundamentals(batch_size=batch_size, minutes_to_wait=minutes_to_wait)
            
    except ValueError as e:
        logger.error(str(e))
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")

if __name__ == "__main__":
    main()
