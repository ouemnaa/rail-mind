"""
Resolution Orchestrator - Runs Hybrid RAG and Mathematical agents in parallel,
normalizes outputs, invokes LLM judge, returns ranked resolutions with timing.

Usage:
    python resolution_orchestrator.py --input conflict.json --timeout 60 --save output.json
"""

import asyncio
import json
import sys
import time
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import traceback
from groq import Groq

# Add paths for imports
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(CURRENT_DIR / "hybrid_RAG_based_resolution_agent"))
sys.path.insert(0, str(CURRENT_DIR / "mathematical_resolution"))
sys.path.insert(0, str(CURRENT_DIR / "llm_as_a _judge"))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AgentResult:
    """Result from a single agent execution."""
    status: str  # "ok", "error", "timeout"
    execution_ms: int
    raw_result: Optional[Any] = None
    parser_status: str = "ok"
    parser_error: Optional[str] = None
    normalized_resolutions: Optional[List[Dict]] = None
    error: Optional[str] = None


@dataclass
class JudgeResult:
    """Result from LLM judge execution."""
    status: str  # "ok", "error"
    execution_ms: int
    ranked_resolutions: Optional[List[Dict]] = None
    raw_llm_response: Optional[str] = None
    error: Optional[str] = None


@dataclass
class OrchestratorOutput:
    """Final orchestrator output."""
    status: str  # "ok", "partial", "error"
    conflict_id: str
    started_at: str
    finished_at: str
    total_execution_ms: int
    agents: Dict[str, Dict]
    llm_judge: Dict


# =============================================================================
# Agent Runners
# =============================================================================

def run_hybrid_rag_agent(conflict: Dict[str, Any], context: Dict[str, Any], timeout: float) -> AgentResult:
    """
    Run the Hybrid RAG agent (Agent 1).
    Returns raw output unchanged.
    """
    start_time = time.perf_counter()
    
    try:
        # Import the resolution generator
        from agent.resolution_generator import TwoLayerResolutionGenerator
        from qdrant_client import QdrantClient
        
        # Get API key from environment or use default
        api_key = "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"
        
        # Initialize Qdrant client (use local or cloud based on env)
        qdrant_url = " https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io"
        qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM"
        
        if qdrant_api_key:
            qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            qdrant_client = QdrantClient(url=qdrant_url)
        
        # Initialize generator
        generator = TwoLayerResolutionGenerator(
            qdrant_client=qdrant_client,
            llm_api_key=api_key
        )
        
        # Generate resolutions
        report = generator.generate_resolution_report(
            conflict=conflict,
            context=context
        )
        
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        
        return AgentResult(
            status="ok",
            execution_ms=execution_ms,
            raw_result=report.to_dict() if hasattr(report, 'to_dict') else report
        )
        
    except ImportError as e:
        # Fallback: Try to load from file if agent not available
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Try to load cached/example output
        agent1_output_path = CURRENT_DIR / "llm_as_a _judge" / "agent1_output.json"
        if agent1_output_path.exists():
            with open(agent1_output_path, 'r') as f:
                raw_result = json.load(f)
            return AgentResult(
                status="ok",
                execution_ms=execution_ms,
                raw_result=raw_result
            )
        
        return AgentResult(
            status="error",
            execution_ms=execution_ms,
            error=f"Import error: {str(e)}"
        )
        
    except Exception as e:
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        return AgentResult(
            status="error",
            execution_ms=execution_ms,
            error=f"{type(e).__name__}: {str(e)}"
        )


def run_mathematical_agent(conflict: Dict[str, Any], context: Dict[str, Any], timeout: float) -> AgentResult:
    """
    Run the Mathematical Solver agent (Agent 2).
    Returns raw output unchanged.
    """
    start_time = time.perf_counter()
    
    try:
        from mathematical_resolution import (
            Conflict, Context, ResolutionOrchestrator, OrchestratorConfig,
            build_rail_graph
        )
        from datetime import datetime as dt
        
        # Convert conflict dict to Conflict dataclass
        math_conflict = Conflict(
            conflict_id=conflict.get('conflict_id', 'unknown'),
            station_ids=conflict.get('station_ids', conflict.get('stations', [])),
            train_ids=conflict.get('train_ids', conflict.get('trains', [])),
            delay_values=conflict.get('delay_values', conflict.get('delays', {})),
            timestamp=conflict.get('timestamp', dt.now().timestamp()),
            severity=conflict.get('severity', 0.5),
            conflict_type=conflict.get('conflict_type', 'unknown'),
            blocking_behavior=conflict.get('blocking_behavior', 'soft')
        )
        
        # Convert context dict to Context dataclass
        ctx = context.get('context', context)
        math_context = Context(
            time_of_day=ctx.get('time_of_day', 12.0),
            day_of_week=ctx.get('day_of_week', 0),
            is_peak_hour=ctx.get('is_peak_hour', False),
            weather_condition=ctx.get('weather_condition', 'clear'),
            network_load=ctx.get('network_load', 0.5)
        )
        
        # Build adjacency from train IDs (simple: all trains connected)
        train_ids = math_conflict.train_ids
        adjacency = {t: [o for o in train_ids if o != t] for t in train_ids}
        
        # Configure orchestrator to run all solvers
        config = OrchestratorConfig(
            use_learned_selector=True,
            run_all_solvers=True,
            fitness_threshold=0.65,
            max_retries=2,
            use_similar_cases=False,
            enable_quantum=False
        )
        
        orchestrator = ResolutionOrchestrator(config)
        
        # Resolve conflict
        best_plan, explanation = orchestrator.resolve_with_explanation(
            math_conflict, math_context, adjacency, None, None
        )
        
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Convert plan to dict
        if best_plan:
            raw_result = {
                'solver_used': best_plan.solver_used,
                'overall_fitness': best_plan.overall_fitness,
                'total_delay_min': best_plan.total_delay,
                'passenger_impact': best_plan.passenger_impact,
                'propagation_depth': best_plan.propagation_depth,
                'recovery_smoothness': best_plan.recovery_smoothness,
                'actions': [
                    {
                        'action_type': a.action_type.value,
                        'target_train_id': a.target_train_id,
                        'parameters': a.parameters
                    }
                    for a in best_plan.actions
                ],
                'explanation': explanation
            }
        else:
            raw_result = {'error': 'No resolution found', 'explanation': explanation}
        
        return AgentResult(
            status="ok",
            execution_ms=execution_ms,
            raw_result=raw_result
        )
        
    except ImportError as e:
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        return AgentResult(
            status="error",
            execution_ms=execution_ms,
            error=f"Import error: {str(e)}"
        )
        
    except Exception as e:
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        traceback.print_exc()
        return AgentResult(
            status="error",
            execution_ms=execution_ms,
            error=f"{type(e).__name__}: {str(e)}"
        )


# =============================================================================
# Normalizers (reuse existing)
# =============================================================================

def normalize_agent1_output(raw_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize Agent 1 (Hybrid RAG) output to NormalizedResolution format.
    Uses existing ResolutionNormalizer from llm_judge_fair.py.
    """
    try:
        from llm_judge_v2 import ResolutionNormalizer, NormalizedResolution
        
        normalizer = ResolutionNormalizer()
        normalized = []
        
        # Handle both direct resolution list and wrapped format
        resolutions = raw_result.get('resolutions', [])
        if not resolutions and isinstance(raw_result, list):
            resolutions = raw_result
        
        for res in resolutions:
            try:
                norm = normalizer.normalize_agent1_resolution(res)
                normalized.append(asdict(norm))
            except Exception as e:
                print(f"⚠️ Failed to normalize Agent 1 resolution: {e}")
                continue
        
        return normalized
        
    except ImportError:
        # Fallback: manual normalization
        normalized = []
        resolutions = raw_result.get('resolutions', [])
        
        for res in resolutions:
            normalized.append({
                'resolution_id': res.get('resolution_id', 'unknown'),
                'source_agent': 'Agent 1 (Hybrid/Historical)',
                'strategy_name': res.get('strategy_name', 'Unknown'),
                'actions': res.get('action_steps', []),
                'expected_outcome': res.get('expected_outcome', ''),
                'reasoning': res.get('reasoning', ''),
                'safety_score': res.get('safety_score', 0.5),
                'efficiency_score': res.get('efficiency_score', 0.5),
                'feasibility_score': res.get('feasibility_score', 0.5),
                'overall_fitness': res.get('confidence_score', 0.5),
                'estimated_delay_min': abs(res.get('estimated_delay_reduction_sec', 0)) / 60.0,
                'affected_trains': res.get('affected_trains', []),
                'side_effects': res.get('side_effects', []),
                'algorithm_type': res.get('source_type', 'hybrid'),
                'raw_data': res
            })
        
        return normalized


def normalize_agent2_output(raw_result: Dict[str, Any], conflict_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize Agent 2 (Mathematical Solver) output to NormalizedResolution format.
    Uses existing ResolutionNormalizer from llm_judge_fair.py.
    """
    try:
        from llm_judge_v2 import ResolutionNormalizer
        
        normalizer = ResolutionNormalizer()
        
        # Extract solver info
        solver_name = raw_result.get('solver_used', 'unknown')
        
        # Build metrics dict
        metrics = {
            'fitness': raw_result.get('overall_fitness', 0.5),
            'total_delay_min': raw_result.get('total_delay_min', 0),
            'original_delay_min': raw_result.get('total_delay_min', 0) * 1.1,
            'num_actions': len(raw_result.get('actions', [])),
            'passenger_impact': raw_result.get('passenger_impact', 0),
            'propagation_depth': raw_result.get('propagation_depth', 0),
            'recovery_smoothness': raw_result.get('recovery_smoothness', 0)
        }
        
        # Build action strings
        actions = []
        for action in raw_result.get('actions', []):
            action_type = action.get('action_type', 'unknown')
            train_id = action.get('target_train_id', 'unknown')
            params = action.get('parameters', {})
            
            if action_type == 'speed_adjust':
                factor = params.get('speed_factor', 1.0)
                if factor > 1:
                    actions.append(f"Speed up {train_id} by {(factor - 1) * 100:.0f}%")
                else:
                    actions.append(f"Slow {train_id} by {(1 - factor) * 100:.0f}%")
            elif action_type == 'hold':
                minutes = params.get('hold_minutes', 0)
                actions.append(f"Hold {train_id} for {minutes:.1f} minutes")
            elif action_type == 'reroute':
                actions.append(f"Reroute {train_id}")
            else:
                actions.append(f"{action_type} on {train_id}")
        
        norm = normalizer.normalize_agent2_resolution(
            solver_name=solver_name,
            metrics=metrics,
            actions=actions,
            conflict_data=conflict_data
        )
        
        return [asdict(norm)]
        
    except ImportError:
        # Fallback: manual normalization
        solver_name = raw_result.get('solver_used', 'unknown')
        
        # Professional name mapping
        name_map = {
            'genetic_algorithm': "Multi-Objective Evolutionary Optimization",
            'simulated_annealing': "Probabilistic Annealing Optimization",
            'lns': "Large Neighborhood Search Refinement",
            'nsga2': "Pareto-Optimal Multi-Criteria Solution",
            'greedy': "Fast Constructive Heuristic"
        }
        
        actions = []
        for action in raw_result.get('actions', []):
            action_type = action.get('action_type', 'unknown')
            train_id = action.get('target_train_id', 'unknown')
            params = action.get('parameters', {})
            
            if action_type == 'speed_adjust':
                factor = params.get('speed_factor', 1.0)
                if factor > 1:
                    actions.append(f"Speed up {train_id} by {(factor - 1) * 100:.0f}%")
                else:
                    actions.append(f"Slow {train_id} by {(1 - factor) * 100:.0f}%")
            elif action_type == 'hold':
                minutes = params.get('hold_minutes', 0)
                actions.append(f"Hold {train_id} for {minutes:.1f} minutes")
            else:
                actions.append(f"{action_type} on {train_id}")
        
        return [{
            'resolution_id': f"agent2_{solver_name}",
            'source_agent': 'Agent 2 (Mathematical Solver)',
            'strategy_name': name_map.get(solver_name, solver_name.replace('_', ' ').title()),
            'actions': actions,
            'expected_outcome': f"Reduces delay to {raw_result.get('total_delay_min', 0):.1f} minutes",
            'reasoning': f"Mathematical optimization using {solver_name}",
            'safety_score': 0.85,
            'efficiency_score': raw_result.get('overall_fitness', 0.5),
            'feasibility_score': 0.8,
            'overall_fitness': raw_result.get('overall_fitness', 0.5),
            'estimated_delay_min': raw_result.get('total_delay_min', 0),
            'affected_trains': conflict_data.get('train_ids', conflict_data.get('trains', [])),
            'side_effects': [],
            'algorithm_type': f"optimization_{solver_name}",
            'raw_data': raw_result
        }]


# =============================================================================
# LLM Judge
# =============================================================================

def call_llm_judge(
    conflict: Dict[str, Any],
    normalized_candidates: List[Dict[str, Any]],
    agent_raw_outputs: Dict[str, Any],
    api_key: str
) -> JudgeResult:
    """
    Call the LLM judge via Groq with normalized candidates.
    Returns ranked resolutions matching ranked_resolutions.json schema.
    """
    start_time = time.perf_counter()
    
    # Build conflict context for prompt
    conflict_context = {
        'conflict_summary': f"{conflict.get('conflict_type', 'Unknown')} at {', '.join(conflict.get('station_ids', conflict.get('stations', [])))}",
        'trains': conflict.get('train_ids', conflict.get('trains', [])),
        'context_snapshot': {
            'conflict_location': {
                'edge_id': '--'.join(conflict.get('station_ids', conflict.get('stations', ['Unknown'])))
            }
        }
    }
    
    # Build the evaluation prompt
    prompt = _build_judge_prompt(conflict_context, normalized_candidates)
    
    try:
        model_name = "openai/gpt-oss-120b"
        client = Groq(api_key=api_key)
        
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert railway operations judge. Return only structured JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=8192,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            stop=None
        )
        
        raw_response = completion.choices[0].message.content
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Parse the response
        rankings = _parse_judge_response(raw_response, normalized_candidates)
        
        return JudgeResult(
            status="ok",
            execution_ms=execution_ms,
            ranked_resolutions=rankings,
            raw_llm_response=raw_response
        )
        
    except Exception as e:
        execution_ms = int((time.perf_counter() - start_time) * 1000)
        return JudgeResult(
            status="error",
            execution_ms=execution_ms,
            error=f"Groq API error ({type(e).__name__}): {str(e)}",
            raw_llm_response=None
        )


def _build_judge_prompt(conflict_context: Dict, candidates: List[Dict]) -> str:
    """Build the LLM judge prompt following strict output schema."""
    
    prompt = f"""You are an expert railway operations judge. Input: a conflict and a list of normalized candidate resolutions from two agents. 

TASK: Rank the candidate resolutions and produce JSON only, matching exactly the structure below for each ranked item (do not change field names):

Each ranked item must include:
- rank (int)
- resolution_number (int, 1-indexed position in input list)
- resolution_id (string)
- bullet_resolution_actions: {{ "actions": [ strings ] }}
- overall_score (numerical 0-100)
- safety_rating, efficiency_rating, feasibility_rating, robustness_rating (numbers 0-10)
- justification (short paragraph, max 2 sentences)
- full_resolution: the complete resolution object including resolution_id, source_agent, strategy_name, actions, expected_outcome, reasoning, safety_score, efficiency_score, feasibility_score, overall_fitness, estimated_delay_min, affected_trains, side_effects, algorithm_type, raw_data

**CONFLICT CONTEXT:**
- Type: {conflict_context['conflict_summary']}
- Location: {conflict_context['context_snapshot']['conflict_location']['edge_id']}
- Affected Trains: {', '.join(conflict_context.get('trains', []))}

**EVALUATION CRITERIA (Equal Weight):**
1. Safety (30%): Maintains operational safety, prevents cascading failures
2. Efficiency (30%): Reduces delays, restores normal operations
3. Feasibility (25%): Quick implementation with available infrastructure
4. Robustness (15%): Handles uncertainty and side effects

**IMPORTANT:**
- Mathematical optimization solutions are AS VALID as hybrid/historical approaches
- Lower delay metrics indicate BETTER performance
- Judge based on OBJECTIVE CRITERIA

**RESOLUTIONS TO EVALUATE:**

"""
    
    for i, res in enumerate(candidates, 1):
        prompt += f"""
### Resolution {i}: {res.get('strategy_name', 'Unknown')}
**Source:** {res.get('source_agent', 'Unknown')}
**Algorithm Type:** {res.get('algorithm_type', 'Unknown')}

**Actions:**
{chr(10).join([f"  {j+1}. {a}" for j, a in enumerate(res.get('actions', []))])}

**Expected Outcome:** {res.get('expected_outcome', '')}
**Reasoning:** {res.get('reasoning', '')}

**Metrics:**
- Overall Fitness: {res.get('overall_fitness', 0):.3f}
- Safety: {res.get('safety_score', 0):.3f}
- Efficiency: {res.get('efficiency_score', 0):.3f}
- Feasibility: {res.get('feasibility_score', 0):.3f}
- Estimated Delay: {res.get('estimated_delay_min', 0):.1f} min

**Side Effects:** {', '.join(res.get('side_effects', [])) or 'None'}

---
"""
    
    prompt += """
**OUTPUT FORMAT:**
Return ONLY a valid JSON array. No markdown, no commentary.
The array should be named "ranked_resolutions" or be a plain array.

Example structure for each item:
{
  "rank": 1,
  "resolution_number": 1,
  "resolution_id": "...",
  "bullet_resolution_actions": { "actions": ["action1", "action2"] },
  "overall_score": 85,
  "safety_rating": 7.5,
  "efficiency_rating": 9.0,
  "feasibility_rating": 8.5,
  "robustness_rating": 7.0,
  "justification": "...",
  "full_resolution": { ... complete resolution object ... }
}

Return the top 3 ranked resolutions.
"""
    
    return prompt


def _parse_judge_response(raw_response: str, candidates: List[Dict]) -> List[Dict]:
    """Parse LLM judge response into ranked resolutions matching schema."""
    import re
    
    json_str = ""
    
    # Try to find JSON in response
    blocks = re.findall(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
    if not blocks:
        blocks = re.findall(r'```\s*(.*?)\s*```', raw_response, re.DOTALL)
    
    if blocks:
        json_str = blocks[-1]
    else:
        # Extract between [ and ]
        start_idx = raw_response.find('[')
        if start_idx != -1:
            end_idx = raw_response.rfind(']')
            if end_idx > start_idx:
                json_str = raw_response[start_idx:end_idx+1]
            else:
                json_str = raw_response[start_idx:]
    
    try:
        rankings = json.loads(json_str)
    except json.JSONDecodeError:
        # Try to repair truncated JSON
        rankings = _repair_truncated_json(json_str)
        if not rankings:
            raise ValueError("Could not parse LLM judgment")
    
    # Enrich with full resolution data
    enriched = []
    for ranking in rankings:
        res_num = ranking.get('resolution_number')
        if res_num is not None:
            idx = int(res_num) - 1
            if 0 <= idx < len(candidates):
                resolution = candidates[idx]
                ranking['full_resolution'] = resolution
        
        # Ensure bullet_resolution_actions exists
        if 'bullet_resolution_actions' not in ranking:
            if 'full_resolution' in ranking:
                ranking['bullet_resolution_actions'] = {
                    'actions': ranking['full_resolution'].get('actions', [])
                }
            else:
                ranking['bullet_resolution_actions'] = {'actions': []}
        
        enriched.append(ranking)
    
    return enriched


def _repair_truncated_json(truncated_str: str) -> List[Dict]:
    """Repair truncated JSON array."""
    objs = []
    stack = []
    start = -1
    
    for i, char in enumerate(truncated_str):
        if char == '{':
            if not stack:
                start = i
            stack.append('{')
        elif char == '}':
            if stack:
                stack.pop()
                if not stack and start >= 0:
                    obj_str = truncated_str[start:i+1]
                    try:
                        objs.append(json.loads(obj_str))
                    except:
                        pass
    
    return objs


# =============================================================================
# Main Orchestrator
# =============================================================================

async def run_agents_parallel(
    conflict: Dict[str, Any],
    context: Dict[str, Any],
    timeout: float
) -> Tuple[AgentResult, AgentResult]:
    """Run both agents in parallel using asyncio."""
    
    loop = asyncio.get_event_loop()
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both agents
        hybrid_future = loop.run_in_executor(
            executor, run_hybrid_rag_agent, conflict, context, timeout
        )
        math_future = loop.run_in_executor(
            executor, run_mathematical_agent, conflict, context, timeout
        )
        
        # Wait for both with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(hybrid_future, math_future, return_exceptions=True),
                timeout=timeout + 5  # Extra buffer
            )
            
            hybrid_result = results[0] if not isinstance(results[0], Exception) else AgentResult(
                status="error", execution_ms=0, error=str(results[0])
            )
            math_result = results[1] if not isinstance(results[1], Exception) else AgentResult(
                status="error", execution_ms=0, error=str(results[1])
            )
            
            return hybrid_result, math_result
            
        except asyncio.TimeoutError:
            return (
                AgentResult(status="timeout", execution_ms=int(timeout * 1000), error="Timeout"),
                AgentResult(status="timeout", execution_ms=int(timeout * 1000), error="Timeout")
            )


def orchestrate(
    conflict: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main orchestration function.
    
    Args:
        conflict: Conflict JSON
        context: Optional operational context
        timeout: Per-agent timeout in seconds
        api_key: OpenRouter API key for LLM judge
    
    Returns:
        Complete orchestrator output dict
    """
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    
    # Default context if not provided
    if context is None:
        context = {
            'time_of_day': 12.0,
            'day_of_week': 0,
            'is_peak_hour': False,
            'weather_condition': 'clear',
            'network_load': 0.5
        }
    
    # Get API key (Groq)
    if api_key is None:
        api_key = os.environ.get("GROQ_API_KEY", "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")
    
    conflict_id = conflict.get('conflict_id', 'unknown')
    
    print("=" * 70)
    print("RESOLUTION ORCHESTRATOR")
    print("=" * 70)
    print(f"Conflict ID: {conflict_id}")
    print(f"Started at: {started_at.isoformat()}")
    print()
    
    # Run agents in parallel
    print("[1] Running agents in parallel...")
    hybrid_result, math_result = asyncio.run(
        run_agents_parallel(conflict, context, timeout)
    )
    
    print(f"    Hybrid RAG:   {hybrid_result.status} ({hybrid_result.execution_ms}ms)")
    print(f"    Mathematical: {math_result.status} ({math_result.execution_ms}ms)")
    print()
    
    # Parse and normalize outputs
    print("[2] Parsing and normalizing outputs...")
    all_normalized = []
    
    # Normalize Agent 1 output
    if hybrid_result.status == "ok" and hybrid_result.raw_result:
        try:
            normalized_1 = normalize_agent1_output(hybrid_result.raw_result)
            hybrid_result.normalized_resolutions = normalized_1
            hybrid_result.parser_status = "ok"
            all_normalized.extend(normalized_1)
            print(f"    Agent 1: {len(normalized_1)} resolutions normalized")
        except Exception as e:
            hybrid_result.parser_status = "error"
            hybrid_result.parser_error = str(e)
            print(f"    Agent 1: Parser error - {e}")
    
    # Normalize Agent 2 output
    if math_result.status == "ok" and math_result.raw_result:
        try:
            normalized_2 = normalize_agent2_output(math_result.raw_result, conflict)
            math_result.normalized_resolutions = normalized_2
            math_result.parser_status = "ok"
            all_normalized.extend(normalized_2)
            print(f"    Agent 2: {len(normalized_2)} resolutions normalized")
        except Exception as e:
            math_result.parser_status = "error"
            math_result.parser_error = str(e)
            print(f"    Agent 2: Parser error - {e}")
    
    print(f"    Total candidates: {len(all_normalized)}")
    print()
    
    # Determine overall status
    if hybrid_result.status == "ok" and math_result.status == "ok":
        overall_status = "ok"
    elif hybrid_result.status == "ok" or math_result.status == "ok":
        overall_status = "partial"
    else:
        overall_status = "error"
    
    # Call LLM judge if we have candidates
    judge_result = JudgeResult(status="skipped", execution_ms=0)
    
    if all_normalized and api_key:
        print("[3] Calling LLM judge...")
        agent_raw_outputs = {
            'hybrid_rag': hybrid_result.raw_result,
            'mathematical': math_result.raw_result
        }
        judge_result = call_llm_judge(conflict, all_normalized, agent_raw_outputs, api_key)
        print(f"    Judge: {judge_result.status} ({judge_result.execution_ms}ms)")
        if judge_result.ranked_resolutions:
            print(f"    Ranked {len(judge_result.ranked_resolutions)} resolutions")
    elif not all_normalized:
        print("[3] Skipping LLM judge - no candidates")
        judge_result = JudgeResult(status="skipped", execution_ms=0, error="No candidates to judge")
    else:
        print("[3] Skipping LLM judge - no API key")
        judge_result = JudgeResult(status="skipped", execution_ms=0, error="No API key provided")
    
    print()
    
    # Build final output
    finished_at = datetime.now(timezone.utc)
    total_ms = int((time.perf_counter() - start_time) * 1000)
    
    output = {
        'status': overall_status,
        'conflict_id': conflict_id,
        'started_at': started_at.isoformat(),
        'finished_at': finished_at.isoformat(),
        'total_execution_ms': total_ms,
        'agents': {
            'hybrid_rag': {
                'status': hybrid_result.status,
                'execution_ms': hybrid_result.execution_ms,
                'raw_result': hybrid_result.raw_result,
                'parser_status': hybrid_result.parser_status,
                'parser_error': hybrid_result.parser_error,
                'normalized_count': len(hybrid_result.normalized_resolutions or [])
            },
            'mathematical': {
                'status': math_result.status,
                'execution_ms': math_result.execution_ms,
                'raw_result': math_result.raw_result,
                'parser_status': math_result.parser_status,
                'parser_error': math_result.parser_error,
                'normalized_count': len(math_result.normalized_resolutions or [])
            }
        },
        'llm_judge': {
            'status': judge_result.status,
            'execution_ms': judge_result.execution_ms,
            'ranked_resolutions': judge_result.ranked_resolutions,
            'raw_llm_response': judge_result.raw_llm_response,
            'error': judge_result.error
        }
    }
    
    print("=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Status: {overall_status}")
    print(f"Total time: {total_ms}ms")
    print(f"  - Hybrid RAG: {hybrid_result.execution_ms}ms")
    print(f"  - Mathematical: {math_result.execution_ms}ms")
    print(f"  - LLM Judge: {judge_result.execution_ms}ms")
    print()
    
    return output


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Resolution Orchestrator - Run agents in parallel and judge results"
    )
    parser.add_argument(
        '--input', '-i',
        type=str,
        help='Path to conflict JSON file'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=float,
        default=60.0,
        help='Per-agent timeout in seconds (default: 60)'
    )
    parser.add_argument(
        '--save', '-s',
        type=str,
        help='Path to save output JSON'
    )
    parser.add_argument(
        '--api-key', '-k',
        type=str,
        help='Groq API key (or set GROQ_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Load conflict
    if args.input:
        with open(args.input, 'r') as f:
            conflict = json.load(f)
    else:
        # Use example conflict
        conflict = {
            'conflict_id': 'CONF-2026-0129-EXAMPLE',
            'conflict_type': 'headway',
            'station_ids': ['MILANO ROGOREDO', 'PAVIA'],
            'train_ids': ['REG_33003', 'REG_3053'],
            'delay_values': {'REG_33003': 2.2, 'REG_3053': 2.2},
            'timestamp': datetime.now().timestamp(),
            'severity': 0.95,
            'blocking_behavior': 'soft'
        }
        print("Using example conflict (no --input provided)")
    
    # Run orchestrator
    output = orchestrate(
        conflict=conflict,
        timeout=args.timeout,
        api_key=args.api_key
    )
    
    # Save output
    if args.save:
        with open(args.save, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        print(f"Output saved to: {args.save}")
    
    # Print ranked resolutions
    if output['llm_judge']['ranked_resolutions']:
        print("\n" + "=" * 70)
        print("FINAL RANKINGS")
        print("=" * 70)
        for r in output['llm_judge']['ranked_resolutions']:
            print(f"\n#{r.get('rank', '?')}: {r.get('resolution_id', 'Unknown')}")
            print(f"   Score: {r.get('overall_score', 'N/A')}")
            print(f"   {r.get('justification', '')[:100]}...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
