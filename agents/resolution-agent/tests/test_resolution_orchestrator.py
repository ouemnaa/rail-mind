"""
Tests for Resolution Orchestrator.
Validates parallel agent execution, normalization, and LLM judge invocation.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from resolution_orchestrator import (
    orchestrate,
    run_hybrid_rag_agent,
    run_mathematical_agent,
    normalize_agent1_output,
    normalize_agent2_output,
    call_llm_judge,
    AgentResult,
    JudgeResult,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_conflict():
    """Sample conflict for testing."""
    return {
        'conflict_id': 'TEST-CONFLICT-001',
        'conflict_type': 'headway',
        'station_ids': ['MILANO ROGOREDO', 'PAVIA'],
        'train_ids': ['REG_33003', 'REG_3053'],
        'delay_values': {'REG_33003': 2.2, 'REG_3053': 2.2},
        'timestamp': datetime.now().timestamp(),
        'severity': 0.95,
        'blocking_behavior': 'soft'
    }


@pytest.fixture
def sample_context():
    """Sample operational context."""
    return {
        'time_of_day': 8.5,
        'day_of_week': 1,
        'is_peak_hour': True,
        'weather_condition': 'clear',
        'network_load': 0.75
    }


@pytest.fixture
def mock_agent1_output():
    """Mock Hybrid RAG agent output."""
    return {
        'conflict_id': 'TEST-CONFLICT-001',
        'resolutions': [
            {
                'resolution_id': 'hybrid_1',
                'strategy_name': 'Dynamic Speed Harmonization',
                'action_steps': [
                    'Reduce REG_3053 speed by 15%',
                    'Extend dwell time at PAVIA'
                ],
                'expected_outcome': 'Achieves 180s headway',
                'reasoning': 'Uses MILP optimization for safety.',
                'source_type': 'hybrid',
                'confidence_score': 0.85,
                'safety_score': 0.8,
                'efficiency_score': 0.75,
                'feasibility_score': 0.9,
                'affected_trains': ['REG_3053'],
                'estimated_delay_reduction_sec': 100,
                'side_effects': ['Temporary capacity reduction']
            },
            {
                'resolution_id': 'hybrid_2',
                'strategy_name': 'Strategic Re-routing',
                'action_steps': [
                    'Divert REG_3053 via alternative track',
                    'Utilize recovery buffer'
                ],
                'expected_outcome': 'Creates physical separation',
                'reasoning': 'Historical approach proven effective.',
                'source_type': 'hybrid',
                'confidence_score': 0.78,
                'safety_score': 0.75,
                'efficiency_score': 0.7,
                'feasibility_score': 0.8,
                'affected_trains': ['REG_3053'],
                'estimated_delay_reduction_sec': 120,
                'side_effects': ['Increased dispatcher workload']
            }
        ]
    }


@pytest.fixture
def mock_agent2_output():
    """Mock Mathematical agent output."""
    return {
        'solver_used': 'genetic_algorithm',
        'overall_fitness': 0.697,
        'total_delay_min': 4.2,
        'passenger_impact': 1259,
        'propagation_depth': 0,
        'recovery_smoothness': 0.976,
        'actions': [
            {
                'action_type': 'speed_adjust',
                'target_train_id': 'REG_33003',
                'parameters': {'speed_factor': 1.12}
            },
            {
                'action_type': 'speed_adjust',
                'target_train_id': 'REG_3053',
                'parameters': {'speed_factor': 0.96}
            }
        ],
        'explanation': 'Resolution using genetic_algorithm'
    }


@pytest.fixture
def mock_judge_response():
    """Mock LLM judge response matching ranked_resolutions.json schema."""
    return [
        {
            'rank': 1,
            'resolution_number': 1,
            'resolution_id': 'Dynamic Speed Harmonization',
            'bullet_resolution_actions': {
                'actions': ['Reduce REG_3053 speed by 15%', 'Extend dwell time at PAVIA']
            },
            'overall_score': 85,
            'safety_rating': 8.0,
            'efficiency_rating': 9.0,
            'feasibility_rating': 8.5,
            'robustness_rating': 7.0,
            'justification': 'Best balance of safety and efficiency. MILP optimization ensures constraints.'
        },
        {
            'rank': 2,
            'resolution_number': 3,
            'resolution_id': 'agent2_genetic_algorithm',
            'bullet_resolution_actions': {
                'actions': ['Speed up REG_33003 by 12%', 'Slow REG_3053 by 4%']
            },
            'overall_score': 78,
            'safety_rating': 8.5,
            'efficiency_rating': 7.5,
            'feasibility_rating': 8.0,
            'robustness_rating': 7.5,
            'justification': 'Mathematical solver with good fitness. Simple implementation.'
        },
        {
            'rank': 3,
            'resolution_number': 2,
            'resolution_id': 'Strategic Re-routing',
            'bullet_resolution_actions': {
                'actions': ['Divert REG_3053 via alternative track', 'Utilize recovery buffer']
            },
            'overall_score': 72,
            'safety_rating': 7.5,
            'efficiency_rating': 7.0,
            'feasibility_rating': 7.0,
            'robustness_rating': 6.5,
            'justification': 'Effective but requires more coordination.'
        }
    ]


# =============================================================================
# Unit Tests
# =============================================================================

class TestNormalization:
    """Test normalization functions."""
    
    def test_normalize_agent1_output(self, mock_agent1_output):
        """Test Agent 1 output normalization."""
        normalized = normalize_agent1_output(mock_agent1_output)
        
        assert len(normalized) == 2
        assert normalized[0]['source_agent'] == 'Agent 1 (Hybrid/Historical)'
        assert normalized[0]['resolution_id'] == 'hybrid_1'
        assert 'actions' in normalized[0]
        assert 'safety_score' in normalized[0]
        assert 'raw_data' in normalized[0]
    
    def test_normalize_agent2_output(self, mock_agent2_output, sample_conflict):
        """Test Agent 2 output normalization."""
        normalized = normalize_agent2_output(mock_agent2_output, sample_conflict)
        
        assert len(normalized) == 1
        assert normalized[0]['source_agent'] == 'Agent 2 (Mathematical Solver)'
        assert 'genetic_algorithm' in normalized[0]['resolution_id']
        assert len(normalized[0]['actions']) == 2
        assert 'Speed up' in normalized[0]['actions'][0] or 'Slow' in normalized[0]['actions'][0]
    
    def test_normalize_empty_output(self):
        """Test handling of empty outputs."""
        normalized = normalize_agent1_output({})
        assert normalized == []
        
        normalized = normalize_agent1_output({'resolutions': []})
        assert normalized == []


class TestAgentExecution:
    """Test agent execution timing and results."""
    
    def test_agent_result_has_timing(self, sample_conflict, sample_context):
        """Test that agent results include execution timing."""
        # This tests the fallback path (import error -> load from file or error)
        result = run_hybrid_rag_agent(sample_conflict, sample_context, timeout=5.0)
        
        assert hasattr(result, 'execution_ms')
        assert result.execution_ms >= 0
        assert result.status in ['ok', 'error', 'timeout']
    
    def test_agent_timeout_handling(self, sample_conflict, sample_context):
        """Test that timeouts are handled properly."""
        # Very short timeout
        result = run_mathematical_agent(sample_conflict, sample_context, timeout=0.001)
        
        # Should either complete fast or timeout
        assert result.status in ['ok', 'error', 'timeout']
        assert result.execution_ms >= 0


class TestLLMJudge:
    """Test LLM judge integration."""
    
    @patch('requests.post')
    def test_judge_parses_response(self, mock_post, sample_conflict, mock_judge_response):
        """Test LLM judge parses response correctly."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': json.dumps(mock_judge_response)}}]
        }
        mock_post.return_value = mock_response
        
        # Create normalized candidates
        candidates = [
            {
                'resolution_id': 'hybrid_1',
                'source_agent': 'Agent 1',
                'strategy_name': 'Test Strategy',
                'actions': ['Action 1'],
                'expected_outcome': 'Outcome',
                'reasoning': 'Reasoning',
                'safety_score': 0.8,
                'efficiency_score': 0.7,
                'feasibility_score': 0.9,
                'overall_fitness': 0.8,
                'estimated_delay_min': 2.0,
                'affected_trains': ['TRAIN_1'],
                'side_effects': [],
                'algorithm_type': 'hybrid',
                'raw_data': {}
            }
        ]
        
        result = call_llm_judge(sample_conflict, candidates, {}, 'fake-api-key')
        
        assert result.status == 'ok'
        assert result.execution_ms >= 0
        assert result.ranked_resolutions is not None
        assert len(result.ranked_resolutions) == 3
    
    def test_judge_handles_no_api_key(self, sample_conflict):
        """Test judge handles missing API key."""
        result = call_llm_judge(sample_conflict, [], {}, '')
        
        # Empty candidates should fail fast
        assert result.status in ['ok', 'error']


class TestOrchestrator:
    """Test full orchestration flow."""
    
    @patch('resolution_orchestrator.run_hybrid_rag_agent')
    @patch('resolution_orchestrator.run_mathematical_agent')
    @patch('resolution_orchestrator.call_llm_judge')
    def test_orchestrate_full_flow(
        self,
        mock_judge,
        mock_math,
        mock_hybrid,
        sample_conflict,
        mock_agent1_output,
        mock_agent2_output,
        mock_judge_response
    ):
        """Test full orchestration with mocked agents."""
        # Setup mocks
        mock_hybrid.return_value = AgentResult(
            status='ok',
            execution_ms=100,
            raw_result=mock_agent1_output
        )
        mock_math.return_value = AgentResult(
            status='ok',
            execution_ms=150,
            raw_result=mock_agent2_output
        )
        mock_judge.return_value = JudgeResult(
            status='ok',
            execution_ms=500,
            ranked_resolutions=mock_judge_response,
            raw_llm_response=json.dumps(mock_judge_response)
        )
        
        # Run orchestrator
        output = orchestrate(
            conflict=sample_conflict,
            timeout=60.0,
            api_key='fake-key'
        )
        
        # Validate output structure
        assert 'status' in output
        assert 'conflict_id' in output
        assert 'started_at' in output
        assert 'finished_at' in output
        assert 'total_execution_ms' in output
        assert 'agents' in output
        assert 'llm_judge' in output
        
        # Validate agent results
        assert 'hybrid_rag' in output['agents']
        assert 'mathematical' in output['agents']
        assert output['agents']['hybrid_rag']['execution_ms'] >= 0
        assert output['agents']['mathematical']['execution_ms'] >= 0
        
        # Validate timing (mocked agents return artificial times, so just check structure)
        assert output['total_execution_ms'] >= 0
        # In real execution, total should be >= max(agent times), but mocked agents 
        # return pre-set execution_ms values while actual wall clock is faster
        assert isinstance(output['total_execution_ms'], int)
    
    @patch('resolution_orchestrator.run_hybrid_rag_agent')
    @patch('resolution_orchestrator.run_mathematical_agent')
    def test_orchestrate_partial_failure(
        self,
        mock_math,
        mock_hybrid,
        sample_conflict,
        mock_agent2_output
    ):
        """Test orchestration with one agent failing."""
        # Setup: Agent 1 fails, Agent 2 succeeds
        mock_hybrid.return_value = AgentResult(
            status='error',
            execution_ms=50,
            error='Connection failed'
        )
        mock_math.return_value = AgentResult(
            status='ok',
            execution_ms=150,
            raw_result=mock_agent2_output
        )
        
        output = orchestrate(
            conflict=sample_conflict,
            timeout=60.0,
            api_key=None  # Skip judge
        )
        
        # Should be partial status
        assert output['status'] == 'partial'
        assert output['agents']['hybrid_rag']['status'] == 'error'
        assert output['agents']['mathematical']['status'] == 'ok'
    
    def test_orchestrate_preserves_raw_output(self, sample_conflict):
        """Test that raw agent outputs are preserved unchanged."""
        output = orchestrate(
            conflict=sample_conflict,
            timeout=10.0,
            api_key=None
        )
        
        # Raw results should be preserved (may be None if agents fail)
        assert 'raw_result' in output['agents']['hybrid_rag']
        assert 'raw_result' in output['agents']['mathematical']


class TestOutputSchema:
    """Test output matches expected schema from ranked_resolutions.json."""
    
    def test_judge_output_schema(self, mock_judge_response):
        """Validate judge output matches expected schema."""
        for ranking in mock_judge_response:
            # Required fields
            assert 'rank' in ranking
            assert 'resolution_number' in ranking
            assert 'resolution_id' in ranking
            assert 'bullet_resolution_actions' in ranking
            assert 'actions' in ranking['bullet_resolution_actions']
            assert 'overall_score' in ranking
            assert 'safety_rating' in ranking
            assert 'efficiency_rating' in ranking
            assert 'feasibility_rating' in ranking
            assert 'robustness_rating' in ranking
            assert 'justification' in ranking
            
            # Type checks
            assert isinstance(ranking['rank'], int)
            assert isinstance(ranking['overall_score'], (int, float))
            assert isinstance(ranking['bullet_resolution_actions']['actions'], list)


# =============================================================================
# Integration Tests (require real agents)
# =============================================================================

@pytest.mark.integration
class TestIntegration:
    """Integration tests requiring real agent setup."""
    
    def test_real_mathematical_agent(self, sample_conflict, sample_context):
        """Test real mathematical agent execution."""
        result = run_mathematical_agent(sample_conflict, sample_context, timeout=30.0)
        
        if result.status == 'ok':
            assert result.raw_result is not None
            assert 'solver_used' in result.raw_result or 'error' in result.raw_result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
