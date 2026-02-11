import requests
import logging

logger = logging.getLogger("NanoClaw.Tools")

def web_search_tool(query):
    """
    Mock Web Search (or actual Brave API if key present).
    """
    logger.info(f"Searching web for: {query}")
    # TODO: Integrate Brave Search API here
    return ["Mock News 1: Crypto is rallying", "Mock News 2: ETF approved"]

def crypto_api_tool(symbol):
    """
    Mock Crypto Data Fetcher.
    """
    logger.info(f"Fetching extra data for: {symbol}")
    # TODO: Integrate Coingecko API
    return {"market_cap_rank": 1, "volume_24h": 500000000}
