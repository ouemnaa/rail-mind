# Backend Integration Tests

This directory contains tests for the backend API endpoints.

## Running Tests

```bash
# From the backend/integration directory
cd backend/integration

# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_resolve_endpoint.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## Test Files

- `test_resolve_endpoint.py` - Tests for `/api/conflicts/resolve` endpoint
