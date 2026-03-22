# OTC-X Market Intelligence Platform

Professional Swiss OTC market analytics platform with Streamlit dashboard and automated data pipeline.

## 📁 Repository Structure

```
OTC-X/
├── backend/                    # Backend data pipeline
│   ├── operations/            # Pipeline modules
│   │   ├── soft_crawl.py     # Fetch securities from API
│   │   ├── fetcher.py        # Download trade data
│   │   ├── build_master_parquet.py  # Consolidate data
│   │   └── metrics.py        # Compute liquidity metrics
│   ├── data/                 # Data storage
│   │   ├── securities.csv    # Securities metadata
│   │   ├── trades/           # Raw trade CSVs
│   │   ├── master_trades.parquet  # Consolidated trades
│   │   └── daily_metrics.parquet  # Computed metrics
│   ├── logs/                 # Pipeline logs
│   └── run_backend.py        # Backend orchestrator
├── frontend/                  # Frontend modules (Phase 3)
├── tests/                     # Test suite
│   ├── test_operations.py    # Backend tests
│   └── test_frontend.py      # Frontend tests
├── app.py                     # Streamlit dashboard (to be modularized)
├── run_frontend.py            # Frontend entry point
├── run.py                     # Main task runner
└── requirements.txt           # Python dependencies
```

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running the Application

Using the task runner (recommended):

```bash
# Run the backend data pipeline
python run.py backend

# Launch the Streamlit dashboard
python run.py frontend

# Run the test suite
python run.py test

# Show help
python run.py help
```

Direct execution:

```bash
# Backend pipeline
python backend/run_backend.py

# Frontend dashboard
streamlit run app.py

# Tests
pytest tests/ -v
```

## 🏗️ Architecture

### Backend Data Pipeline

4-stage automated pipeline:

1. **Valor Extraction**: Fetch securities from OTC-X API
2. **Trade Data Retrieval**: Download trade history for each security
3. **Data Consolidation**: Build master parquet files
4. **Metrics Engine**: Compute liquidity metrics and anomaly scores

### Frontend Dashboard

Professional Streamlit dashboard with:
- Market overview and KPI cards
- Interactive charts (Plotly)
- Correlation analysis
- Anomaly detection
- Real-time data visualization

## 🧪 Testing

Comprehensive test suite with 24+ tests covering:
- Backend operations (unit tests)
- Data pipeline integrity (integration tests)
- Frontend structure (structure tests)

Run tests:
```bash
pytest tests/ -v
```

## 📊 Data Flow

```
OTC-X API → soft_crawl.py → securities.csv
                 ↓
OTC-X API → fetcher.py → trades/*.csv
                 ↓
trades/*.csv → build_master_parquet.py → master_trades.parquet
                 ↓
master_trades.parquet → metrics.py → daily_metrics.parquet
                 ↓
daily_metrics.parquet → app.py → Streamlit Dashboard
```

## 🛠️ Development

### Project Status

- ✅ Phase 1: Analysis & Testing Strategy (Complete)
- ✅ Phase 2: Repository Restructure & Naming (Complete)
- 🔄 Phase 3: Frontend Modularization (In Progress)
- ⏳ Phase 4: Path Handling & Integrity (Pending)
- ⏳ Phase 5: Code Quality & OOP Evaluation (Pending)

### Contributing

This project follows professional software engineering practices:
- Dynamic path resolution for environment independence
- Comprehensive test coverage
- Modular architecture
- Clear separation of concerns

## 📝 License

Proprietary - OTC-X Market Intelligence Platform
