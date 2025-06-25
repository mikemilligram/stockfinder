# StockFinder

A data collection service for stock tickers and their fundamental data from [EODHD](https://eodhd.com) (EOD Historical Data), built with Python and MongoDB.

## Prerequisites

- An EODHD API key (can be obtained from [EODHD](https://eodhd.com))

## Setup

### Docker compose

```
services:
  stockfinder:
    container_name: stockfinder
    image: ghcr.io/mikemilligram/stockfinder:latest
    environment:
      COUNTRIES: USA,Germany
      EODHD_API_KEY: ${EODHD_API_KEY}
    restart: unless-stopped
    depends_on:
      - mongo
    networks:
      - stockfinder

  mongo:
    container_name: mongo
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped
    networks:
      - stockfinder

volumes:
  mongo_data:

networks:
  stockfinder:
    name: stockfinder_net
```

## Configuration

The application can be configured using the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `EODHD_API_KEY` | Your EODHD API key for accessing their services | `-` |
| `COUNTRIES` | Comma-separated list of countries to filter exchanges (e.g., "USA,Germany") | `-` |
| `MONGODB_HOST` | MongoDB server hostname or IP address | `mongo` |
| `MONGODB_PORT` | MongoDB server port | `27017` |
| `MONGODB_USERNAME` | Username for MongoDB authentication | `-` |
| `MONGODB_PASSWORD` | Password for MongoDB authentication | `-` |
| `MONGODB_DATABASE` | Name of the MongoDB database to use | `stockfinder` |
| `LOG_LEVEL` | Python logging level (INFO, DEBUG, WARNING, ERROR) | `INFO` |
| `BATCH_SIZE` | Number of tickers to process per batch | `100` |
| `MINUTES_TO_WAIT` | Minutes to wait before retrying if API rate limit is reached | `10` |

## How It Works
- On first run, fetches tickers for all exchanges (or only those from the specified countries) and stores them in MongoDB
- Collects fundamental data for all tickers in batches, respecting EODHD API rate limits
- If the API limit is reached, waits for the configured time and resumes
- On subsequent starts or restarts of the container, the process will continue fetching fundamental data where it left off, ensuring no duplicate work is done.
