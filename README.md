# StockFinder

A data collection and REST API service for stock tickers and their fundamentals, built with FastAPI and MongoDB.

## Setup

### Docker compose

```
services:
  stockfinder:
    build: .
    environment:
      COUNTRIES: USA,Germany
      EODHD_API_KEY: ${EODHD_API_KEY}
      MONGODB_HOST: ${MONGODB_HOST}
    restart: unless-stopped 
```

## Environment Variables
- `EODHD_API_KEY` (required): Your EODHD API key
- `COUNTRIES` (optional): Comma-separated list of countries to filter exchanges
- `MONGODB_HOST` (default: db)
- `MONGODB_PORT` (default: 27017)
- `MONGODB_USERNAME` (optional)
- `MONGODB_PASSWORD` (optional)
- `MONGODB_DATABASE` (default: stockfinder)
- `LOG_LEVEL` (default: INFO)
- `BATCH_SIZE` (default: 50): Number of tickers to process per batch when collecting fundamental data
- `MINUTES_TO_WAIT` (default: 10): Minutes to wait before retrying if API rate limit is reached

## How It Works
- On first run, fetches tickers for all exchanges (or only those from the specified countries) and stores them in MongoDB
- Collects fundamental data for all tickers in batches, respecting EODHD API rate limits
- If the API limit is reached, waits for the configured time and resumes
- On subsequent starts or restarts of the container, the process will continue fetching fundamental data where it left off, ensuring no duplicate work is done.


**Note:** You must provide your own EODHD API key and MongoDB instance.