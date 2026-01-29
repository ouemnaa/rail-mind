"""
Integration tests for the /api/conflicts/resolve endpoint.

Run with:
    cd backend/integration
    pytest tests/test_resolve_endpoint.py -v
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# Sample test data
SAMPLE_CONFLICT = {
    "conflict_id": "TEST-CONF-001",
    "conflict_type": "headway",
    "station_ids": ["MILANO CENTRALE", "MILANO ROGOREDO"],
    "train_ids": ["REG_001", "FR_002"],
    "delay_values": {"REG_001": 2.5, "FR_002": 1.8},
    "timestamp": 1706500000,
    "severity": 0.75,
    "blocking_behavior": "soft"
}

SAMPLE_DETECTION = {
    "conflict_id": "DET-001",
    "source": "detection",
    "conflict_type": "edge_capacity_overflow",
    "severity": "high",
    "probability": 1.0,
    "location": "MILANO CENTRALE--PAVIA",
    "location_type": "edge",
    "involved_trains": ["REG_2816", "FR_9703"],
    "explanation": "Edge overload detected",
    "timestamp": "2026-01-29T10:00:00",
    "resolution_suggestions": ["Hold trains", "Reroute"]
}

MOCK_ORCHESTRATOR_OUTPUT = {
    "status": "ok",
    "conflict_id": "TEST-CONF-001",
    "started_at": "2026-01-29T10:00:00+00:00",
    "finished_at": "2026-01-29T10:00:05+00:00",
    "total_execution_ms": 5000,
    "agents": {
        "hybrid_rag": {
            "status": "ok",
            "execution_ms": 100,
            "raw_result": {"resolutions": []},
            "parser_status": "ok",
            "parser_error": None,
            "normalized_count": 2
        },
        "mathematical": {
            "status": "ok",
            "execution_ms": 3000,
            "raw_result": {"solver_used": "genetic_algorithm"},
            "parser_status": "ok",
            "parser_error": None,
            "normalized_count": 1
        }
    },
    "llm_judge": {
        "status": "ok",
        "execution_ms": 1500,
        "ranked_resolutions": [
            {
                "rank": 1,
                "resolution_id": "hybrid_1",
                "resolution_number": 1,
                "overall_score": 85,
                "safety_rating": 8.0,
                "efficiency_rating": 9.0,
                "feasibility_rating": 8.5,
                "robustness_rating": 7.0,
                "justification": "Best overall solution"
            }
        ],
        "raw_llm_response": "...",
        "error": None
    }
}


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    
    # Mock the IntegrationEngine to avoid full initialization
    with patch('unified_api.IntegrationEngine') as mock_engine:
        mock_instance = MagicMock()
        mock_engine.return_value = mock_instance
        mock_instance.initialize.return_value = None
        
        from unified_api import app
        client = TestClient(app)
        yield client


@pytest.fixture
def mock_orchestrator():
    """Mock the orchestrator module."""
    with patch('unified_api._run_orchestrator_sync') as mock:
        mock.return_value = MOCK_ORCHESTRATOR_OUTPUT
        yield mock


class TestResolveEndpoint:
    """Tests for /api/conflicts/resolve endpoint."""
    
    def test_resolve_with_conflict_json(self, test_client, mock_orchestrator):
        """Test resolving with direct conflict JSON."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={"conflict": SAMPLE_CONFLICT, "timeout": 30}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "filepath" in data
        assert "output" in data
        assert data["output"]["status"] in ["ok", "partial", "error"]
        assert "agents" in data["output"]
        assert "hybrid_rag" in data["output"]["agents"]
        assert "mathematical" in data["output"]["agents"]
    
    def test_resolve_with_detection(self, test_client, mock_orchestrator):
        """Test resolving with detection format (auto-converted)."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={"detection": SAMPLE_DETECTION}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_resolve_missing_conflict(self, test_client):
        """Test error when no conflict provided."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={}
        )
        
        assert response.status_code == 400
        assert "No conflict provided" in response.json()["detail"]
    
    def test_resolve_file_not_found(self, test_client):
        """Test error when filename doesn't exist."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={"filename": "nonexistent_file.json"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_resolve_path_traversal_blocked(self, test_client):
        """Test that path traversal is blocked."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={"filename": "../../../etc/passwd"}
        )
        
        # Should only use the filename part, not the path
        assert response.status_code == 404  # File won't exist
    
    def test_resolve_rate_limiting(self, test_client, mock_orchestrator):
        """Test rate limiting works."""
        # Make multiple rapid requests
        for i in range(6):
            response = test_client.post(
                "/api/conflicts/resolve",
                json={"conflict": SAMPLE_CONFLICT}
            )
            
            if i < 5:
                assert response.status_code == 200
            else:
                # 6th request should be rate limited
                assert response.status_code == 429
                assert "Rate limit" in response.json()["detail"]
    
    def test_resolve_output_saved(self, test_client, mock_orchestrator, tmp_path):
        """Test that orchestrator output is saved to file."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={"conflict": SAMPLE_CONFLICT}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check filepath is returned
        assert "filepath" in data
        assert "orchestrator_" in data["filepath"]
        assert data["filename"].endswith(".json")
    
    def test_resolve_with_api_key_header(self, test_client, mock_orchestrator):
        """Test passing API key via Authorization header."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={"conflict": SAMPLE_CONFLICT},
            headers={"Authorization": "Bearer test-api-key-123"}
        )
        
        assert response.status_code == 200
    
    def test_resolve_with_api_key_body(self, test_client, mock_orchestrator):
        """Test passing API key in request body."""
        response = test_client.post(
            "/api/conflicts/resolve",
            json={
                "conflict": SAMPLE_CONFLICT,
                "llm_api_key": "test-api-key-456"
            }
        )
        
        assert response.status_code == 200


class TestConversionFunctions:
    """Tests for detection-to-conflict conversion."""
    
    def test_convert_detection_format(self):
        """Test converting detection to orchestrator format."""
        from unified_api import _convert_detection_to_orchestrator_format
        
        converted = _convert_detection_to_orchestrator_format(SAMPLE_DETECTION)
        
        assert "conflict_id" in converted
        assert "conflict_type" in converted
        assert converted["conflict_type"] == "edge_capacity_overflow"
        assert "station_ids" in converted
        assert "train_ids" in converted
        assert converted["train_ids"] == ["REG_2816", "FR_9703"]
        assert "severity" in converted
        assert 0 <= converted["severity"] <= 1
    
    def test_convert_detection_preserves_original(self):
        """Test that original detection is preserved in converted format."""
        from unified_api import _convert_detection_to_orchestrator_format
        
        converted = _convert_detection_to_orchestrator_format(SAMPLE_DETECTION)
        
        assert "original_detection" in converted
        assert converted["original_detection"] == SAMPLE_DETECTION


class TestOutputListEndpoints:
    """Tests for orchestrator output listing endpoints."""
    
    def test_list_outputs(self, test_client):
        """Test listing orchestrator outputs."""
        response = test_client.get("/api/conflicts/resolve/outputs")
        
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "files" in data
        assert isinstance(data["files"], list)
    
    def test_get_output_not_found(self, test_client):
        """Test getting non-existent output file."""
        response = test_client.get("/api/conflicts/resolve/output/nonexistent.json")
        
        assert response.status_code == 404


class TestHealthAndRoot:
    """Tests for health and root endpoints."""
    
    def test_root_includes_resolve_endpoint(self, test_client):
        """Test that root endpoint documents resolve API."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "resolution_api" in data or "/api/conflicts/resolve" in str(data)
    
    def test_health_endpoint(self, test_client):
        """Test health endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
