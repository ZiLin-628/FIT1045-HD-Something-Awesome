# app/currency.py

"""Currency management constants and utilities."""

import logging

logger = logging.getLogger(__name__)

# Supported currencies
BASE_CURRENCY = "MYR"
SUPPORTED_CURRENCIES = {
    "MYR": "RM",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "SGD": "$",
    "AUD": "$",
    "JPY": "¥",
    "CNY": "¥",
    "THB": "฿",
    "IDR": "Rp",
}


def get_currency_symbol(currency_code: str) -> str:
    """
    Get the symbol for a given currency code.

    Args:
        currency_code (str): currency code.

    Returns:
        str: Corresponding currency symbol or the code itself if not found.
    """
    currency_code = currency_code.upper()
    symbol = SUPPORTED_CURRENCIES.get(currency_code, currency_code)
    logger.debug(f"Retrieved currency symbol for {currency_code}: {symbol}")
    return symbol


def validate_currency(currency_code: str) -> bool:
    """
    Check if a currency code is supported for this money tracker.

    Args:
        currency_code (str): currency code.

    Returns:
        bool: True if supported, False otherwise.
    """
    is_valid = currency_code.upper() in SUPPORTED_CURRENCIES
    if not is_valid:
        logger.warning(f"Unsupported currency code: {currency_code}")
    return is_valid


def get_currency_list() -> list[str]:
    """
    Get a list of all supported currency codes.

    Returns:
        list[str]: Supported currency codes.
    """
    return list(SUPPORTED_CURRENCIES.keys())
