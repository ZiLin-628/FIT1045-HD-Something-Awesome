# database/models.py

import enum
from decimal import Decimal

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database.base import Base


class TransactionType(enum.Enum):
    """
    Enum representing types of transactions.

    Attributes:
        EXPENSE: Represents an expense transaction.
        INCOME: Represents an income transaction.
    """

    EXPENSE = "expense"
    INCOME = "income"


class BudgetPeriod(enum.Enum):
    """
    Enum representing budget period types.

    Attributes:
        WEEKLY: Budget resets every week.
        MONTHLY: Budget resets every month.
        YEARLY: Budget resets every year.
    """

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Category(Base):
    """
    Table epresents a category for transactions

     Attributes:
        id (int): Primary key.
        name (str): Name of the category.
        type (TransactionType): Type of transaction (expense or income).
        transactions (list[Transaction]): Related transactions.
        budgets (list[Budget]): Related budget entries.
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(SqlEnum(TransactionType), nullable=False)

    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship(
        "Budget", back_populates="category", cascade="all, delete-orphan"
    )


class Account(Base):
    """
    Table represent a account in a money tracker program

     Attributes:
        id (int): Primary key.
        account_name (str): Name for the account.
        balance (Decimal): Current balance of the account.
        transactions (list[Transaction]): List of related transactions.
    """

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    account_name = Column(String(100), unique=True, nullable=False)
    balance = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    transactions = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )


class Transaction(Base):
    """
    Table represents a transaction record.

    Attributes:
        id (int): Primary key.
        datetime (datetime): When the transaction happen.
        transaction_type (TransactionType): Transaction type.
        amount (Decimal): Original amount in the transaction currency.
        currency (str): Currency code (e.g., MYR, USD).
        amount_in_myr (Decimal): Amount converted to MYR.
        exchange_rate (Decimal): Conversion rate at transaction time.
        description (str): Optional transaction description.
        account_id (int): Foreign key to Account.
        category_id (int): Foreign key to Category.
    """

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=False)
    transaction_type = Column(SqlEnum(TransactionType), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="MYR")
    amount_in_myr = Column(Numeric(12, 2), nullable=False)
    exchange_rate = Column(Numeric(10, 6), nullable=False, default=Decimal("1.0"))
    description = Column(String(255), nullable=True)

    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )

    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")


class ExchangeRate(Base):
    """
    Table represents an exchange rate record between currencies.

    Attributes:
        id (int): Primary key.
        from_currency (str): Source currency.
        to_currency (str): Target currency.
        rate (Decimal): Exchange rate.
        last_updated (datetime): Last time the rate was updated.
    """

    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True)
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)  # Always "MYR"
    rate = Column(Numeric(12, 6), nullable=False)
    last_updated = Column(DateTime, nullable=False)


class Budget(Base):
    """Table represent a budget for a category

    Attributes:
        id (int): Primary key.
        category_id (int): Foreign key to Category.
        limit_amount (Decimal): Budget limit in MYR.
        period (BudgetPeriod): Type of budget period.
        start_date (datetime): When the budget period start.
    """

    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    limit_amount = Column(Numeric(12, 2), nullable=False)
    period = Column(SqlEnum(BudgetPeriod), nullable=False)
    start_date = Column(DateTime, nullable=False)

    category = relationship("Category", back_populates="budgets")


class Goal(Base):
    """Table representing a financial goal

    Attributes:
        id (int): Primary key.
        name (str): Goal name.
        description (str): Optional goal description.
        target_amount (Decimal): Target amount in MYR.
        initial_balance (Decimal): Balance when goal was created.
        deadline (date): Target date to achieve goal.
        account_id (int): Optional foreign key to Account (if linked).
        is_completed (bool): Whether goal is completed.
        created_at (datetime): When goal was created.
    """

    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    target_amount = Column(Numeric(15, 2), nullable=False)
    initial_balance = Column(Numeric(15, 2), nullable=False, default=0)
    deadline = Column(DateTime, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    is_completed = Column(Integer, default=0)  # SQLite: 0 = False, 1 = True
    created_at = Column(DateTime, nullable=False)

    account = relationship("Account", backref="goals")
