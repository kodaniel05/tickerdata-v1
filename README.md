# TickerData

TickerData is a stock analysis project that retrieves market data from Yahoo Finance and calculates useful stock statistics.

The project includes:

* Python stock analysis
* Django backend API
* Next.js frontend
* CSV data export
* Yahoo Finance data through `yfinance`

## Requirements

Install:

* Python 3.13+
* Node.js
* npm
* Git

Check your versions:

```bash
python3 --version
node --version
npm --version
git --version
```

## Clone the Repository

```bash
git clone <REPOSITORY_URL>
cd tickerdata
```

If you forked the repository, clone your fork instead.

## Python Setup

Create a virtual environment:

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Update pip:

```bash
python -m pip install --upgrade pip
```

Install the Python dependencies:

```bash
python -m pip install django pandas yfinance
```

Check for dependency problems:

```bash
python -m pip check
```

## Run the Backend

```bash
cd backend
python manage.py check
python manage.py test stocks
python manage.py runserver
```

The backend will normally run at:

```text
http://127.0.0.1:8000
```

Example stock API request:

```text
http://127.0.0.1:8000/api/stocks/AAPL/
```

You can also test it with:

```bash
curl http://127.0.0.1:8000/api/stocks/AAPL/
```

## Run the Frontend

Open another terminal:

```bash
cd tickerdata/frontend
npm ci
npm run dev
```

Open:

```text
http://localhost:3000
```

## Original Python Scripts

The original command-line scripts are still included.

### Download stock data to CSV

```bash
python fetchdata.py
```

### Stock Analyzer

```bash
python StockAnalyzer.py
```

### Static Stock Analyzer

```bash
python StockAnalyzerStatic.py
```

The newer stock analysis code is located in:

```text
backend/stocks/services/
```

## Updating the Project

Before updating, check for local changes:

```bash
git status
```

Pull the newest code:

```bash
git pull
```

Update Python packages if necessary:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
```

Update frontend dependencies:

```bash
cd frontend
npm ci
```

Then verify everything still works:

```bash
cd ../backend
python manage.py check
python manage.py test stocks
```

## Useful Commands

Backend:

```bash
cd backend
python manage.py runserver
python manage.py test stocks
```

Frontend:

```bash
cd frontend
npm run dev
npm run lint
npm run build
```

Git:

```bash
git status
git pull
git add .
git commit -m "your message"
git push
```

## Troubleshooting

### `python` or `python3` not found

Install Python and make sure it is added to your system PATH.

### `ModuleNotFoundError`

Make sure the virtual environment is active, then run:

```bash
python -m pip install django pandas yfinance
```

### `npm` not found

Install Node.js, which includes npm.

### Frontend dependencies are missing

```bash
cd frontend
npm ci
```

### Start over with the Python environment

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install django pandas yfinance
```

## Documentation

Additional information about the stock calculations and development work is in:

```text
docs/METRICS.md
docs/ENGINEERING_LOG.md
```

## Disclaimer

TickerData is an educational project and should not be considered financial or investment advice.
