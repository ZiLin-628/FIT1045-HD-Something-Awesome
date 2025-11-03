# tests/test_prediction_service.py

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import TransactionType
from app.services.prediction_service import PredictionService


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def prediction_service(mock_db_session):
    return PredictionService(mock_db_session)


class TestPredictCategoryMonthlySpending:

    @patch("app.services.prediction_service.datetime")
    @pytest.mark.parametrize(
        "historical,expected_method",
        [
            ([400.0, 450.0, 420.0, 480.0, 460.0, 440.0], "Exponential Smoothing"),
            ([450.0], "Simple Average"),
            ([], "Current Pace Only"),
        ],
    )
    def test_prediction_methods(
        self,
        mock_datetime,
        prediction_service,
        mock_db_session,
        historical,
        expected_method,
    ):
        mock_datetime.now.return_value = datetime(2025, 10, 15)
        mock_db_session.query().filter().all.return_value = [
            MagicMock(amount_in_myr=Decimal("250"))
        ]

        with patch.object(
            prediction_service,
            "get_historical_monthly_spending",
            return_value=historical,
        ):
            result = prediction_service.predict_category_monthly_spending(
                "Food", 2025, 10
            )

        assert result["method"] == expected_method
        assert "predicted_total" in result
        assert "confidence" in result

    @patch("app.services.prediction_service.datetime")
    def test_prediction_includes_budget_fields(
        self, mock_datetime, prediction_service, mock_db_session
    ):
        mock_datetime.now.return_value = datetime(2025, 10, 15)
        mock_db_session.query().filter().all.return_value = [
            MagicMock(amount_in_myr=Decimal("400"))
        ]

        with patch.object(
            prediction_service, "get_historical_monthly_spending", return_value=[]
        ):
            result = prediction_service.predict_category_monthly_spending(
                "Food", 2025, 10
            )

        assert "budget_limit" in result
        assert "will_exceed" in result

    @patch("app.services.prediction_service.datetime")
    @pytest.mark.parametrize("current_day,expected_days", [(1, 1), (15, 15), (31, 31)])
    def test_days_calculation(
        self,
        mock_datetime,
        prediction_service,
        mock_db_session,
        current_day,
        expected_days,
    ):
        mock_datetime.now.return_value = datetime(2025, 10, current_day)
        mock_db_session.query().filter().all.return_value = []

        with patch.object(
            prediction_service, "get_historical_monthly_spending", return_value=[]
        ):
            result = prediction_service.predict_category_monthly_spending(
                "Food", 2025, 10
            )

        assert result["days_passed"] == expected_days


class TestPredictWithExpSmoothing:

    @pytest.mark.parametrize(
        "historical,expected",
        [
            ([400.0, 450.0, 420.0, 480.0, 460.0, 440.0], (350, 550)),  # Valid range
            ([400.0, 450.0], (0, 1000)),  # Two values
            ([400.0], 400.0),  # Single value
            ([], 0),  # Empty
        ],
    )
    @pytest.mark.filterwarnings(
        "ignore::statsmodels.tools.sm_exceptions.ConvergenceWarning"
    )
    def test_smoothing_variations(self, prediction_service, historical, expected):
        result = prediction_service.predict_with_exponential_smoothing(historical)

        if isinstance(expected, tuple):
            assert expected[0] < result < expected[1]
        else:
            assert result == expected

    def test_smoothing_error_fallback(self, prediction_service):
        with patch(
            "app.services.prediction_service.SimpleExpSmoothing",
            side_effect=Exception("Error"),
        ):
            result = prediction_service.predict_with_exponential_smoothing(
                [100.0, 100.0, 100.0]
            )
        assert result == 100.0


class TestGetBudgetPredictions:

    @patch("app.services.prediction_service.datetime")
    def test_returns_all_budgets_sorted_by_usage(
        self, mock_datetime, prediction_service, mock_db_session
    ):
        """Test that all budgeted categories are returned, sorted by usage percentage."""
        mock_datetime.now.return_value = datetime(2025, 10, 15)

        # Mock categories
        cat1, cat2, cat3 = MagicMock(), MagicMock(), MagicMock()
        cat1.name = "Food"
        cat2.name = "Shopping"
        cat3.name = "Transport"

        mock_db_session.query().filter().all.return_value = [cat1, cat2, cat3]

        # Mock predict_category_monthly_spending to return different predictions
        def mock_predict(category_name, year, month):
            predictions = {
                "Food": {
                    "predicted_total": Decimal("450"),
                    "budget_limit": Decimal("500"),
                    "will_exceed": False,
                },
                "Shopping": {
                    "predicted_total": Decimal("480"),
                    "budget_limit": Decimal("400"),
                    "will_exceed": True,
                },
                "Transport": {
                    "predicted_total": Decimal("100"),
                    "budget_limit": Decimal("200"),
                    "will_exceed": False,
                },
            }
            return predictions.get(category_name, {})

        with patch.object(
            prediction_service,
            "predict_category_monthly_spending",
            side_effect=mock_predict,
        ):
            result = prediction_service.get_budget_predictions(2025, 10)

        # Now returns ALL budgeted categories (Shopping 120%, Food 90%, Transport 50%)
        assert len(result) == 3
        assert (
            result[0]["category_name"] == "Shopping"
        )  # Sorted by usage (highest first)
        assert result[1]["category_name"] == "Food"
        assert result[2]["category_name"] == "Transport"
        assert all("predicted_usage_pct" in p for p in result)


class TestGetSpendingRecommendation:

    @patch("app.services.prediction_service.datetime")
    @pytest.mark.parametrize(
        "budget_limit,will_exceed,expected_has_budget",
        [
            (Decimal("500"), True, True),
            (None, False, False),
        ],
    )
    def test_recommendations(
        self,
        mock_datetime,
        prediction_service,
        mock_db_session,
        budget_limit,
        will_exceed,
        expected_has_budget,
    ):
        mock_datetime.now.return_value = datetime(2025, 10, 15)

        prediction = {
            "current_spending": Decimal("300"),
            "budget_limit": budget_limit,
            "will_exceed": will_exceed,
            "daily_rate_current": Decimal("20"),
            "days_remaining": 16,
        }

        with patch.object(
            prediction_service,
            "predict_category_monthly_spending",
            return_value=prediction,
        ):
            result = prediction_service.get_spending_recommendation("Food", 2025, 10)

        assert result["has_budget"] == expected_has_budget
        assert "message" in result


class TestCalculateConfidence:

    @pytest.mark.parametrize(
        "days_passed,historical_count,expected",
        [
            (10, 6, "high"),
            (5, 3, "medium"),
            (2, 1, "low"),
            (0, 0, "low"),
            (7, 6, "high"),
            (3, 6, "high"),
            (10, 2, "medium"),
        ],
    )
    def test_confidence_levels(
        self, prediction_service, days_passed, historical_count, expected
    ):
        assert (
            prediction_service.calculate_confidence(days_passed, historical_count)
            == expected
        )


class TestGetCategorySpending:

    @pytest.mark.parametrize(
        "transactions,expected",
        [
            (
                [
                    MagicMock(amount_in_myr=Decimal("100")),
                    MagicMock(amount_in_myr=Decimal("150")),
                ],
                Decimal("250"),
            ),
            ([], Decimal("0")),
        ],
    )
    def test_category_spending(
        self, prediction_service, mock_db_session, transactions, expected
    ):
        mock_db_session.query().filter().all.return_value = transactions
        assert prediction_service.get_category_spending("Food", 2025, 10) == expected


class TestGetHistoricalMonthlySpending:

    def test_chronological_order(self, prediction_service, mock_db_session):
        mock_db_session.query().filter().all.side_effect = [
            [MagicMock(amount_in_myr=Decimal("300"))],
            [MagicMock(amount_in_myr=Decimal("350"))],
            [MagicMock(amount_in_myr=Decimal("400"))],
        ]
        result = prediction_service.get_historical_monthly_spending("Food", 2025, 10, 3)

        assert result == [400.0, 350.0, 300.0]  # Oldest to most recent

    @pytest.mark.parametrize("lookback", [1, 3, 6, 12])
    def test_lookback_count(self, prediction_service, mock_db_session, lookback):
        mock_db_session.query().filter().all.return_value = []
        result = prediction_service.get_historical_monthly_spending(
            "Food", 2025, 10, lookback
        )

        assert len(result) == lookback
