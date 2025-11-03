# Money Tracker

A personal finance management application built with Python and Streamlit help to track income and expenses, manage accounts and categories, set financial goals, and generate insightful predictions and summaries.

- [Money Tracker](#money-tracker)
  - [Features](#features)
    - [Transaction Management](#transaction-management)
    - [Filtering](#filtering)
    - [Account Management](#account-management)
    - [Category Management](#category-management)
    - [Budget Management](#budget-management)
    - [Predictions](#predictions)
    - [Goal Tracking](#goal-tracking)
    - [Summaries](#summaries)
    - [Data Management](#data-management)
  - [Installation](#installation)
    - [Step 1: Clone or Download the Repository](#step-1-clone-or-download-the-repository)
    - [Step 2: Create Virtual Environment](#step-2-create-virtual-environment)
    - [Step 3: Install Dependencies](#step-3-install-dependencies)
    - [Step 4: Initialize Database](#step-4-initialize-database)
    - [Step 5: Running the Application](#step-5-running-the-application)
  - [Testing](#testing)

## Features

**Streamlit-based Web GUI**: Interactive, user-friendly web interface accessible via browser for all operations.

**Multi-Currency System**: Support for multiple currencies with automatic conversion to MYR using Currency API. Exchange rates cached for 1 hours.

### Transaction Management

-   **Add Transactions**: Record income and expenses transaction with details
-   **Edit Transactions**: Modify existing transaction details
-   **Delete Transactions**: Remove unwanted transactions with confirmation
-   **View All Transactions**: Display all transactions in a formatted, sortable table
-   **Export Transaction**: Export and download the (filtered) transactions into csv file

### Filtering

-   **Filter by Category**: View all transactions for a specific category
-   **Filter by Account**: See transactions from a particular account
-   **Filter by Type**: View all income transactions or expense transactions
-   **Combined Filters**: Apply multiple filters simultaneously for detailed analysis

### Account Management

-   **Create Accounts**: Set up multiple accounts with initial balances
-   **View Accounts**: See all accounts with their current balances
-   **Edit Accounts**: Modify existing account names
-   **Delete Accounts**: Remove accounts with confirmation

### Category Management

-   **View Categories**: View all income and expense category
-   **Add Categories**: Create custom categories for both income and expenses
-   **Edit Categories**: Rename existing categories
-   **Delete Categories**: Remove unused categories with confirmation

### Budget Management

-   **Set Budgets**: Create monthly budgets for expense categories only
-   **Budget Tracking**: Monitor spending against budget limits with real-time usage percentage
-   **Budget Alerts**: Visual warnings when approaching (>80%) or exceeding (>100%) budget limits
-   **Budget Analysis**: View detailed utilization percentages, spent amounts, and remaining amounts
-   **Edit Budgets**: Adjust budget amounts and periods
-   **Delete Budgets**: Remove budgets with confirmation

### Predictions

-   **Category Spending Prediction**: Uses exponential smoothing algorithm to forecast future spending based on historical patterns
-   **Prediction Methods**: Automatically selects between exponential smoothing, simple average, or current pace
-   **Historical Analysis**: Compares current spending with historical averages

### Goal Tracking

-   **Create Financial Goals**: Set savings targets with deadlines and optional account linking
-   **Progress Visualization**: Progress bars with percentage completion and income/expense breakdown
-   **Goal Status**: Automatic status tracking (on track, behind, achieved, overdue, completed)
-   **Smart Recommendations**: Daily, weekly, and monthly savings targets based on remaining time
-   **Mark Complete**: Mark goals as completed when achieved
-   **Edit Goals**: Modify goal details
-   **Delete Goals**: Remove a specific goal with confirmation



### Summaries

-   **Daily Summary**: Total income, expenses, and net balance for any specific day
-   **Weekly Summary**: Total income, expenses, and net balance for any week with category breakdowns
-   **Monthly Summary**: Total income, expenses, and net balance for any month
-   **Expense Breakdown**: Expenses by category over date ranges with pie charts
-   **Income Breakdown**: Income by category over date ranges with pie charts


### Data Management

-   **SQLite Database**: Relational database storage using SQLAlchemy ORM
-   **Auto-save**: All changes automatically save to database with transaction management
-   **Backup System**: Timestamped backups stored in `backups/` directory using SQLite's backup API
-   **Data Persistence**: All data preserved between sessions with foreign key constraints
-   **Comprehensive Logging**: Detailed logging with millisecond timestamps in `log/` directory

## Installation

### Step 1: Clone or Download the Repository

```bash
git clone https://github.com/ZiLin-628/FIT1045-HD-Something-Awesome.git

cd FIT1045-HD-Something-Awesome
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate
```

### Step 3: Install Dependencies

Install all required Python packages using pip:

```bash
pip install -r requirements.txt
```

### Step 4: Initialize Database

```bash
python database_setup.py
```

### Step 5: Running the Application

To start the Money Tracker program:

```bash
streamlit run main.py
```

## Testing

The project includes comprehensive unit tests for all services:

```bash
# Run all tests
pytest
```

