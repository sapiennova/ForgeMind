# ForgeMind - Industrial Machine Health Platform

**Early-stage development. Current status: Foundation Phase**

## Project Overview

ForgeMind is being redeveloped as an Industrial Machine Health Platform for predictive maintenance, sensor integration, and machine health monitoring across manufacturing environments.

The repository currently contains:
- A minimal FastAPI backend foundation
- Historical ML projects from an academic/internship program (preserved as-is)

## Current Development Status

**Foundation Phase** - Basic FastAPI backend with health check endpoint. Ready for gradual feature development.

## Quick Start

### Prerequisites
- Python 3.9+
- Works in GitHub Codespaces (no local installation required)

### Backend Setup
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run the API
uvicorn backend.app.main:app --reload

# Test the API
curl http://localhost:8000/health
```

### Testing
```bash
# Run pytest
pytest tests/
```

## Repository Structure

```
forgemind/
├── backend/           # FastAPI backend (current phase)
│   └── requirements.txt # Backend dependencies
├── tests/             # Test suite
├── project_6_rul_prediction/      # [Historical] LSTM RUL prediction
├── project_11_manufacturing_output/ # [Historical] Manufacturing forecasting
├── requirements.txt   # Historical ML project dependencies
├── README.md          # This file
└── .gitignore
```

## Historical Projects

The repository preserves two ML projects developed during an industrial internship:

- **Project 6**: Predicting Remaining Useful Life (RUL) of Turbofan Engines using LSTM
- **Project 11**: Predicting Output in a Multi-Stage Manufacturing Process using XGBoost & Random Forest

These are not currently integrated into the platform and serve as historical reference implementations.

## Development Roadmap

The full platform will eventually include:
- Machine and sensor data integration
- Sensor health monitoring
- Anomaly detection
- Failure prediction
- RUL calculation
- Maintenance scheduling
- Industrial protocol support
- Web dashboard

## Contributing

See DEVELOPMENT.md for development guidelines (future).

## License

[License to be defined]
