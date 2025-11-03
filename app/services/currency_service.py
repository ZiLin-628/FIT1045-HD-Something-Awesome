# app/services/currency_service.py

"""Service for managing currency conversion and exchange rates."""

import logging
from datetime import datetime
from decimal import Decimal

import requests

from app.currency import BASE_CURRENCY, validate_currency
from app.database.models import ExchangeRate
from app.exception import InvalidInputError

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service class for handling currency conversion and exchange rate management."""

    # API URL
    CDN_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/{api_version}/{endpoint}"
    FALLBACK_URL = "https://{date}.currency-api.pages.dev/{api_version}/{endpoint}"

    API_VERSION = "v1"

    def __init__(self, db_session):
        """
        Initialize CurrencyService.

        Args:
            db_session: SQLAlchemy database session.
        """
        self.db_session = db_session

    def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str = BASE_CURRENCY,
        date: str = "latest",
        minified: bool = False,
    ) -> Decimal:
        """
        Get the exchange rate between two currencies.

        Args:
            from_currency (str): Source currency code.
            to_currency (str): Target currency code (default: MYR).
            date (str): Date or 'latest' for current rate.
            minified (bool): Whether to use minified JSON endpoint.

        Returns:
            Decimal: Exchange rate value.

        Raises:
            InvalidInputError: If a currency is unsupported or fetch fails.
        """
        logger.info(f"Getting exchange rate: {from_currency} -> {to_currency}")

        # Convert to currency name to uppercase
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Check if is a valid currency
        if not validate_currency(from_currency):
            logger.error(f"Unsupported currency: {from_currency}")
            raise InvalidInputError(f"Unsupported currency: {from_currency}")
        if not validate_currency(to_currency):
            logger.error(f"Unsupported currency: {to_currency}")
            raise InvalidInputError(f"Unsupported currency: {to_currency}")

        # If converting to same currency
        if from_currency == to_currency:
            logger.info(f"Same currency conversion: {from_currency}")
            return Decimal("1.0")

        # Check cache rate
        cached_rate = self._get_cached_rate(from_currency, to_currency)
        if cached_rate:
            logger.info(
                f"Using cached exchange rate: {from_currency} -> {to_currency} = {cached_rate}"
            )
            return cached_rate

        # Fetch from API and cache
        logger.info(
            f"Fetching exchange rate from API: {from_currency} -> {to_currency}"
        )
        return self._fetch_and_cache_rate(
            from_currency,
            to_currency,
            from_currency.lower(),
            to_currency.lower(),
            date,
            minified,
        )

    def _get_cached_rate(self, from_currency: str, to_currency: str) -> Decimal | None:
        """
        Retrieve cached exchange rate if still valid (refreshes at midnight daily).

        Args:
            from_currency (str): Source currency code.
            to_currency (str): Target currency code.

        Returns:
            Decimal | None: Cached rate or None if expired/not found.
        """
        # Get start of today (midnight 00:00:00)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        rate_record = (
            self.db_session.query(ExchangeRate)
            .filter_by(from_currency=from_currency, to_currency=to_currency)
            .filter(ExchangeRate.last_updated >= today_start)
            .first()
        )

        return rate_record.rate if rate_record else None

    def _fetch_and_cache_rate(
        self,
        from_currency: str,
        to_currency: str,
        from_currency_lower: str,
        to_currency_lower: str,
        date: str,
        minified: bool,
    ) -> Decimal:
        """
        Fetch exchange rate from Currency API and store in cache.

        Args:
            from_currency (str): Source currency (uppercase).
            to_currency (str): Target currency (uppercase).
            from_currency_lower (str): Source currency (lowercase).
            to_currency_lower (str): Target currency (lowercase).
            date (str): Date string or 'latest'.
            minified (bool): Use minified API response.

        Returns:
            Decimal: Exchange rate value.

        Raises:
            InvalidInputError: If API fetch fails and no cache exists.
        """

        # For eg, currencies/eur --> 1 EUR = X MYR

        # Use lowercase for API endpoint
        endpoint = f"currencies/{from_currency_lower}"
        endpoint += ".min.json" if minified else ".json"

        urls = [
            self.CDN_URL.format(
                date=date, api_version=self.API_VERSION, endpoint=endpoint
            ),
            self.FALLBACK_URL.format(
                date=date, api_version=self.API_VERSION, endpoint=endpoint
            ),
        ]

        last_exception = None

        # Fetch data from api
        for url in urls:
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()

                # Result stored
                data = response.json()

                # If first URL not working, try next
                if from_currency_lower not in data:
                    continue

                # Get the rates
                rates_dict = data[from_currency_lower]

                if to_currency_lower not in rates_dict:
                    raise InvalidInputError(
                        f"Currency {to_currency} not found in API data"
                    )

                # Get the rate for "TARGET CURRENCY" = X (in MYR)
                rate = Decimal(str(rates_dict[to_currency_lower]))

                # Cache the rate
                self._cache_rate(from_currency, to_currency, rate)
                logger.info(
                    f"Exchange rate fetched and cached: {from_currency} -> {to_currency} = {rate}"
                )

                return rate

            except (requests.RequestException, ValueError) as e:
                last_exception = e
                logger.warning(f"Failed to fetch from URL: {e}")
                continue

        # If both url fail
        # Use last cached rate even if expired
        logger.warning(
            f"All API requests failed for {from_currency} -> {to_currency}, checking for expired cache"
        )
        last_rate = (
            self.db_session.query(ExchangeRate)
            .filter_by(from_currency=from_currency, to_currency=to_currency)
            .first()
        )

        if last_rate:
            logger.info(f"Using expired cached rate: {from_currency} -> {to_currency}")
            return last_rate.rate

        logger.error(f"No exchange rate available for {from_currency} -> {to_currency}")
        raise InvalidInputError(
            f"Failed to fetch exchange rate for {from_currency} -> {to_currency}. "
            f"No cached rate available. Error: {last_exception}"
        )

    def _cache_rate(self, from_currency: str, to_currency: str, rate: Decimal):
        """
        Cache exchange rate in the database.

        Args:
            from_currency (str): Source currency.
            to_currency (str): Target currency.
            rate (Decimal): Exchange rate value.
        """

        # Check if have previous record
        existing = (
            self.db_session.query(ExchangeRate)
            .filter_by(from_currency=from_currency, to_currency=to_currency)
            .first()
        )

        if existing:
            existing.rate = rate
            existing.last_updated = datetime.now()

        # Create for new rate record
        else:
            new_rate = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                last_updated=datetime.now(),
            )
            self.db_session.add(new_rate)

        self.db_session.commit()

    def convert_to_myr(
        self,
        amount: Decimal,
        from_currency: str,
        date: str = "latest",
        minified: bool = False,
    ) -> Decimal:
        """
        Convert an amount from any supported currency to MYR.

        Args:
            amount (Decimal): Amount to convert.
            from_currency (str): Source currency code.
            date (str): Date string or 'latest' (default).
            minified (bool): Use minified API response.

        Returns:
            Decimal: Converted amount in MYR.

        Raises:
            InvalidInputError: If currency conversion fails.
        """
        logger.info(f"Converting {amount} {from_currency} to MYR")

        from_currency = from_currency.upper()

        # X MYR always = X MYR
        if from_currency == BASE_CURRENCY:
            logger.info(f"No conversion needed for {BASE_CURRENCY}")
            return amount

        rate = self.get_exchange_rate(
            from_currency, BASE_CURRENCY, date=date, minified=minified
        )
        converted = amount * rate
        logger.info(f"Converted {amount} {from_currency} to {converted} MYR")
        return converted
