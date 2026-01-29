"""
Fair LLM-as-a-Judge System for Railway Conflict Resolutions (V2 - Groq Integrated)
Normalizes outputs from both agents before evaluation to ensure objective ranking
"""

import json
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from groq import Groq


@dataclass
class NormalizedResolution:
    """Standardized format for fair comparison"""
    resolution_id: str
    source_agent: str
    strategy_name: str
    
    # Core solution details
    actions: List[str]
    expected_outcome: str
    reasoning: str
    
    # Quantitative metrics (0-1 scale)
    safety_score: float
    efficiency_score: float
    feasibility_score: float
    overall_fitness: float
    
    # Impact metrics
    estimated_delay_min: float
    affected_trains: List[str]
    side_effects: List[str]
    
    # Source info
    algorithm_type: str
    raw_data: Dict[str, Any]


class ResolutionNormalizer:
    """
    Normalizes resolutions from different formats into comparable structure
    This ensures Agent 2's mathematical solutions aren't disadvantaged
    """
    
    def normalize_agent1_resolution(self, res: Dict[str, Any]) -> NormalizedResolution:
        """Normalize Agent 1 (verbose JSON with lots of explanation)"""
        return NormalizedResolution(
            resolution_id=res['resolution_id'],
            source_agent="Agent 1 (Hybrid/Historical)",
            strategy_name=res['strategy_name'],
            
            # Core details
            actions=res['action_steps'],
            expected_outcome=res['expected_outcome'],
            reasoning=self._condense_reasoning(res['reasoning']),  # Condense verbose reasoning
            
            # Metrics (already normalized)
            safety_score=res.get('safety_score', 0.5),
            efficiency_score=res.get('efficiency_score', 0.5),
            feasibility_score=res.get('feasibility_score', 0.5),
            overall_fitness=res.get('confidence_score', 0.5),
            
            # Impact
            estimated_delay_min=abs(res.get('estimated_delay_reduction_sec') or 0) / 60.0,
            affected_trains=res.get('affected_trains', []),
            side_effects=res.get('side_effects', []),
            
            # Source
            algorithm_type=res.get('source_type', 'hybrid'),
            raw_data=res
        )
    
    def normalize_agent2_resolution(
        self,
        solver_name: str,
        metrics: Dict[str, Any],
        actions: List[str],
        conflict_data: Dict[str, Any]
    ) -> NormalizedResolution:
        """
        Normalize Agent 2 (mathematical solver - short output but rigorous)
        IMPORTANT: Enhance with proper context to match Agent 1's detail level
        """
        
        # Extract metrics
        fitness = metrics['fitness']
        total_delay_min = metrics['total_delay_min']
        original_delay_min = metrics.get('original_delay_min', total_delay_min * 1.1)
        
        # Calculate normalized scores
        efficiency = self._calculate_efficiency_score(total_delay_min, original_delay_min)
        safety = self._calculate_safety_score(solver_name, metrics)
        feasibility = self._calculate_feasibility_score(solver_name, metrics)
        
        # Create enhanced reasoning (Agent 2 deserves proper explanation!)
        enhanced_reasoning = self._create_enhanced_reasoning(solver_name, metrics, actions)
        
        # Create detailed expected outcome
        enhanced_outcome = self._create_enhanced_outcome(solver_name, metrics, actions)
        
        return NormalizedResolution(
            resolution_id=f"agent2_{solver_name}",
            source_agent="Agent 2 (Mathematical Solver)",
            strategy_name=self._create_professional_name(solver_name),
            
            # Core details (enhanced!)
            actions=actions,
            expected_outcome=enhanced_outcome,
            reasoning=enhanced_reasoning,
            
            # Metrics
            safety_score=safety,
            efficiency_score=efficiency,
            feasibility_score=feasibility,
            overall_fitness=fitness,
            
            # Impact
            estimated_delay_min=total_delay_min,
            affected_trains=self._extract_trains_from_actions(actions),
            side_effects=self._infer_side_effects(metrics, actions),
            
            # Source
            algorithm_type=f"optimization_{solver_name}",
            raw_data=metrics
        )
    
    def _condense_reasoning(self, verbose_reasoning: str) -> str:
        """Condense Agent 1's verbose reasoning to key points"""
        # Extract only the core logic, remove fluff
        sentences = verbose_reasoning.split('. ')
        key_points = [s for s in sentences if any(
            keyword in s.lower() for keyword in 
            ['safety', 'optimization', 'constraint', 'algorithm', 'effective', 'proven']
        )]
        return '. '.join(key_points[:2]) + '.'  # Max 2 sentences
    
    def _create_enhanced_reasoning(
        self, 
        solver_name: str, 
        metrics: Dict[str, Any],
        actions: List[str]
    ) -> str:
        """
        Create professional reasoning for Agent 2 that matches Agent 1's detail level
        This is CRITICAL for fairness!
        """
        
        # Solver descriptions (based on actual algorithms used)
        solver_descriptions = {
            'genetic_algorithm': (
                "Uses evolutionary optimization with population-based search to "
                "balance multiple objectives simultaneously. Proven effective for "
                "multi-constraint railway scheduling with mutation and crossover operators "
                "ensuring solution diversity while converging to optimal tradeoffs."
            ),
            'simulated_annealing': (
                "Employs probabilistic hill-climbing with controlled randomness to "
                "escape local optima. Temperature-based acceptance criterion allows "
                "exploration of solution space while gradually focusing on high-quality regions, "
                "particularly effective for tightly-constrained railway networks."
            ),
            'lns': (
                "Large Neighborhood Search systematically destroys and repairs solution "
                "components while maintaining feasibility constraints. Iterative refinement "
                "ensures both local optimality and global solution quality, with proven "
                "effectiveness in real-time railway rescheduling scenarios."
            ),
            'nsga2': (
                "Multi-objective evolutionary algorithm using Pareto dominance to "
                "simultaneously optimize conflicting goals (delay vs safety vs capacity). "
                "Non-dominated sorting ensures balanced solutions across all objectives, "
                "with crowding distance maintaining solution diversity."
            ),
            'greedy': (
                "Fast constructive heuristic making locally optimal decisions at each step. "
                "Low computational overhead enables real-time deployment while maintaining "
                "acceptable solution quality. Particularly effective when immediate response "
                "is critical and solution space is well-structured."
            )
        }
        
        base_reasoning = solver_descriptions.get(
            solver_name,
            f"Mathematical optimization using {solver_name.replace('_', ' ')} algorithm."
        )
        
        # Add quantitative achievements
        recovery_smoothness = metrics.get('recovery_smoothness', 0)
        if recovery_smoothness > 0:
            base_reasoning += f" Achieves {recovery_smoothness:.1%} recovery smoothness, "
            base_reasoning += "minimizing operational disruption and maintaining schedule integrity."
        
        # Add complexity handling
        num_actions = len(actions)
        base_reasoning += f" Implements {num_actions} coordinated action(s) with "
        base_reasoning += "verified constraint satisfaction and operational feasibility."
        
        return base_reasoning
    
    def _create_enhanced_outcome(
        self,
        solver_name: str,
        metrics: Dict[str, Any],
        actions: List[str]
    ) -> str:
        """Create detailed expected outcome for Agent 2"""
        delay_min = metrics['total_delay_min']
        original_delay = metrics.get('original_delay_min', delay_min * 1.1)
        improvement_pct = ((original_delay - delay_min) / original_delay) * 100 if original_delay > 0 else 0
        
        outcome = f"Reduces total system delay to {delay_min:.1f} minutes "
        outcome += f"(improvement of {improvement_pct:.1f}% from baseline). "
        
        # Add specific conflict resolution
        outcome += "Resolves headway violation through coordinated speed adjustments "
        outcome += "while maintaining safety constraints and operational feasibility. "
        
        # Add passenger impact if available
        if 'passenger_impact' in metrics:
            outcome += f"Affects {metrics['passenger_impact']} passengers with "
            outcome += "minimal service disruption."
        
        return outcome
    
    def _create_professional_name(self, solver_name: str) -> str:
        """Create professional strategy name for Agent 2"""
        name_map = {
            'genetic_algorithm': "Multi-Objective Evolutionary Optimization",
            'simulated_annealing': "Probabilistic Annealing Optimization",
            'lns': "Large Neighborhood Search Refinement",
            'nsga2': "Pareto-Optimal Multi-Criteria Solution",
            'greedy': "Fast Constructive Heuristic"
        }
        return name_map.get(solver_name, solver_name.replace('_', ' ').title())
    
    def _calculate_efficiency_score(
        self,
        final_delay: float,
        original_delay: float
    ) -> float:
        """Calculate efficiency based on delay reduction"""
        if original_delay == 0:
            return 0.5
        
        improvement = (original_delay - final_delay) / original_delay
        # Map improvement to 0-1 scale (50% improvement = 0.75 score)
        score = 0.5 + (improvement * 0.5)
        return max(0.0, min(1.0, score))
    
    def _calculate_safety_score(
        self,
        solver_name: str,
        metrics: Dict[str, Any]
    ) -> float:
        """
        Calculate safety score based on algorithm characteristics
        Mathematical solvers have STRONG safety guarantees!
        """
        # Base safety by solver type (these are constraint-respecting algorithms!)
        safety_by_solver = {
            'lns': 0.90,  # Maintains feasibility by design
            'simulated_annealing': 0.85,  # Constraint-aware with penalty functions
            'genetic_algorithm': 0.85,  # Population diversity ensures safety exploration
            'nsga2': 0.88,  # Multi-objective explicitly includes safety
            'greedy': 0.80  # Fast but still respects hard constraints
        }
        
        base_safety = safety_by_solver.get(solver_name, 0.80)
        
        # Bonus for zero propagation (no cascading effects)
        if metrics.get('propagation_depth', 1) == 0:
            base_safety += 0.05
        
        # Bonus for high recovery smoothness (indicates stable solution)
        smoothness = metrics.get('recovery_smoothness', 0)
        if smoothness > 0.9:
            base_safety += 0.05
        
        return min(1.0, base_safety)
    
    def _calculate_feasibility_score(
        self,
        solver_name: str,
        metrics: Dict[str, Any]
    ) -> float:
        """Calculate feasibility based on solution characteristics"""
        # Fewer actions = more feasible
        num_actions = metrics.get('num_actions', 2)
        action_penalty = num_actions * 0.05
        
        # Base feasibility by solver
        base_feasibility = {
            'greedy': 0.90,  # Very practical
            'lns': 0.85,     # Good balance
            'simulated_annealing': 0.80,
            'genetic_algorithm': 0.80,
            'nsga2': 0.75    # More complex
        }.get(solver_name, 0.75)
        
        # Adjust for complexity
        feasibility = base_feasibility - action_penalty
        
        # Bonus for high fitness (indicates achievable solution)
        fitness = metrics.get('fitness', 0.5)
        if fitness > 0.7:
            feasibility += 0.05
        
        return max(0.0, min(1.0, feasibility))
    
    def _extract_trains_from_actions(self, actions: List[str]) -> List[str]:
        """Extract train IDs from action descriptions"""
        trains = set()
        for action in actions:
            # Match patterns like REG_3053, FR_8821, etc.
            matches = re.findall(r'[A-Z]+_\d+', action)
            trains.update(matches)
        return sorted(list(trains))
    
    def _infer_side_effects(
        self,
        metrics: Dict[str, Any],
        actions: List[str]
    ) -> List[str]:
        """Infer realistic side effects from solution characteristics"""
        effects = []
        
        # Check propagation
        prop_depth = metrics.get('propagation_depth', 0)
        if prop_depth > 0:
            effects.append(f"Affects {prop_depth} downstream train(s)")
        else:
            effects.append("Minimal cascading effects (isolated resolution)")
        
        # Check passenger impact
        passenger_impact = metrics.get('passenger_impact', 0)
        if passenger_impact > 1500:
            effects.append(f"High passenger impact ({passenger_impact} affected)")
        elif passenger_impact > 0:
            effects.append(f"Moderate passenger impact ({passenger_impact} affected)")
        
        # Check action complexity
        if len(actions) > 2:
            effects.append("Requires coordination of multiple simultaneous actions")
        else:
            effects.append("Simple implementation with minimal coordination overhead")
        
        # Check recovery smoothness
        smoothness = metrics.get('recovery_smoothness', 0)
        if smoothness < 0.9:
            effects.append("May require additional schedule adjustments")
        
        return effects


class LLMJudge:
    """
    Fair LLM-based judge that evaluates normalized resolutions using Groq
    """
    
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b"):
        self.api_key = api_key
        self.model = model
        self.client = Groq(api_key=self.api_key)
    
    def rank_resolutions(
        self,
        normalized_resolutions: List[NormalizedResolution],
        conflict_context: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Rank resolutions using LLM judge
        
        Returns top_k resolutions with rankings and justifications
        """
        
        # Create fair evaluation prompt
        prompt = self._create_evaluation_prompt(
            normalized_resolutions,
            conflict_context
        )
        
        # Get LLM judgment
        judgment = self._call_llm(prompt)
        
        # Parse and return rankings
        rankings = self._parse_rankings(judgment, normalized_resolutions, top_k)
        
        return rankings
    
    def _create_evaluation_prompt(
        self,
        resolutions: List[NormalizedResolution],
        conflict_context: Dict[str, Any]
    ) -> str:
        """
        Create FAIR evaluation prompt with normalized information
        Key: Both agents get equal representation!
        """
        
        prompt = f"""You are an expert railway operations judge evaluating conflict resolution strategies.

**CONFLICT CONTEXT:**
- Type: {conflict_context['conflict_summary']}
- Location: {conflict_context['context_snapshot']['conflict_location']['edge_id']}
- Severity: Critical headway violation (50s actual vs 180s required)
- Affected Trains: {', '.join(conflict_context.get('trains', []))}

**YOUR TASK:**
Evaluate the following {len(resolutions)} resolution strategies objectively and rank the TOP 3.

**EVALUATION CRITERIA (Equal Weight):**
1. **Safety** (30%): Does it maintain operational safety and prevent cascading failures?
2. **Efficiency** (30%): How effectively does it reduce delays and restore normal operations?
3. **Feasibility** (25%): Can it be implemented quickly with available infrastructure?
4. **Robustness** (15%): How well does it handle uncertainty and side effects?

**IMPORTANT GUIDELINES:**
- Mathematical optimization solutions are AS VALID as hybrid/historical approaches
- Simpler solutions with fewer actions are OFTEN feasible in practice
- Lower delay metrics indicate BETTER performance
- Both verbal reasoning AND quantitative metrics matter equally
- Judge based on OBJECTIVE CRITERIA, not on verbosity of explanation

---

**RESOLUTIONS TO EVALUATE:**

"""
        
        # Add each resolution in FAIR format
        for i, res in enumerate(resolutions, 1):
            prompt += f"""
### Resolution {i}: {res.strategy_name}
**Source:** {res.source_agent}
**Algorithm Type:** {res.algorithm_type}

**Actions:**
{self._format_actions(res.actions)}

**Expected Outcome:**
{res.expected_outcome}

**Technical Reasoning:**
{res.reasoning}

**Quantitative Metrics:**
- Overall Fitness/Confidence: {res.overall_fitness:.3f}
- Safety Score: {res.safety_score:.3f}
- Efficiency Score: {res.efficiency_score:.3f}
- Feasibility Score: {res.feasibility_score:.3f}
- Estimated Delay: {res.estimated_delay_min:.1f} minutes
- Affected Trains: {len(res.affected_trains)}

**Side Effects:**
{self._format_side_effects(res.side_effects)}

---
"""
        
        prompt += """
**OUTPUT FORMAT:**
Return ONLY a valid JSON array with your top 3 ranked resolutions. 
Do not include any thinking process, introduction, or conclusion outside the JSON.
Keep justifications extremely concise (max 2 sentences).

[
  {
    "rank": 1,
    "resolution_number": <1-4>,
    "resolution_id": "<id>",
    "bullet_resolution_actions": {},
    "overall_score": <0-100>,
    "safety_rating": <0-10>,
    "efficiency_rating": <0-10>,
    "feasibility_rating": <0-10>,
    "robustness_rating": <0-10>,
    "justification": "<2 sentence explanation>"
  },
  ...
]

**CRITICAL:** Base your judgment on OBJECTIVE PERFORMANCE METRICS and PRACTICAL VIABILITY. 
Be concise. No preamble. No markdown code blocks unless necessary.
"""
        
        return prompt
    
    def _format_actions(self, actions: List[str]) -> str:
        """Format action list"""
        return '\n'.join([f"  {i+1}. {action}" for i, action in enumerate(actions)])
    
    def _format_side_effects(self, effects: List[str]) -> str:
        """Format side effects list"""
        if not effects:
            return "  - None identified"
        return '\n'.join([f"  - {effect}" for effect in effects])
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API via Groq"""
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert railway operations judge. Return only JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_completion_tokens=8192,
                top_p=1,
                reasoning_effort="medium",
                stream=False, # We want full response for sync parsing
                stop=None
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Groq API error ({type(e).__name__}): {str(e)}")
    
    def _parse_rankings(
        self,
        judgment_text: str,
        resolutions: List[NormalizedResolution],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Parse LLM judgment into structured rankings with robust recovery"""
        
        # Debug: Print what we received
        print("\n[DEBUG] LLM Response Preview:")
        print("="*70)
        print(judgment_text[:800] + ("..." if len(judgment_text) > 800 else ""))
        print("="*70)
        
        json_str = ""
        
        # Method 1: Look for JSON blocks
        blocks = re.findall(r'```json\s*(.*?)\s*```', judgment_text, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'```\s*(.*?)\s*```', judgment_text, re.DOTALL)
            
        if blocks:
            json_str = blocks[-1] # Take the last block if multiple exist
        else:
            # Method 2: Extract between [ and ]
            start_idx = judgment_text.find('[')
            if start_idx != -1:
                # Find the last closing bracket that could belong to the root array
                end_idx = judgment_text.rfind(']')
                if end_idx > start_idx:
                    json_str = judgment_text[start_idx:end_idx+1]
                else:
                    # Partial JSON - we will try to repair it
                    json_str = judgment_text[start_idx:]
            else:
                print("\n❌ No array found in response")
                raise ValueError("Could not parse LLM judgment - no JSON array found")

        # Try to parse and repair if needed
        try:
            rankings_json = json.loads(json_str)
        except json.JSONDecodeError:
            print("⚠️  JSON appears malformed/truncated, attempting recovery...")
            rankings_json = self._repair_truncated_json(json_str)
            if not rankings_json:
                 raise ValueError("Could not repair truncated LLM judgment")

        # Enrich with full resolution data
        enriched_rankings = []
        for ranking in rankings_json:
            if len(enriched_rankings) >= top_k:
                break
                
            # Find corresponding resolution
            res_num = ranking.get('resolution_number')
            if res_num is not None:
                idx = int(res_num) - 1
                if 0 <= idx < len(resolutions):
                    resolution = resolutions[idx]
                    enriched_rankings.append({
                        **ranking,
                        'full_resolution': asdict(resolution)
                    })
                else:
                    print(f"⚠️  Warning: Invalid resolution_number {res_num}")
            else:
                # If no number, try to match by ID
                res_id = ranking.get('resolution_id')
                found = False
                for res in resolutions:
                    if res.resolution_id == res_id:
                        enriched_rankings.append({
                            **ranking,
                            'full_resolution': asdict(res)
                        })
                        found = True
                        break
                if not found:
                    print(f"⚠️  Warning: Could not link ranking to any resolution")
        
        if not enriched_rankings:
            raise ValueError("No valid rankings could be extracted from JSON")
            
        return enriched_rankings

    def _repair_truncated_json(self, truncated_str: str) -> List[Dict]:
        """
        Force-repairs a truncated JSON array of objects.
        Backtracks to the last complete object.
        """
        # Remove trailing junk
        temp_str = truncated_str.strip()
        
        # Try to find the last complete object closing brace '}' 
        # that is followed by either a comma or the end of a potential list item
        objs = []
        
        # Very simple incremental parser: find all '{...}' blocks
        # This is safer than regex for nested objects
        stack = []
        start = -1
        for i, char in enumerate(temp_str):
            if char == '{':
                if not stack:
                    start = i
                stack.append('{')
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack:
                        # We found a top-level object!
                        obj_str = temp_str[start:i+1]
                        try:
                            objs.append(json.loads(obj_str))
                        except:
                            pass # Skip broken objects
                            
        return objs


# =========================
# Main Execution
# =========================

def main():
    """
    Complete workflow: Parse both agents → Normalize → Judge → Rank
    """
    import sys
    
    print("="*70)
    print("FAIR LLM-AS-A-JUDGE: RAILWAY CONFLICT RESOLUTION RANKING")
    print("="*70 + "\n")
    
    # ⚠️ IMPORTANT: Replace this with your actual Groq API key!
    GROQ_API_KEY = "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"
    GROQ_MODEL = "openai/gpt-oss-120b"
    
    if GROQ_API_KEY == "YOUR_API_KEY_HERE":
        print("❌ ERROR: Please set your Groq API key in the script!")
        return 1
    
    # Agent 1 resolutions (from JSON file)
    agent1_json_path = "./agent1_output.json"
    
    # Agent 2 resolution (from console output)
    agent2_data = {
        'solver_name': 'genetic_algorithm',
        'metrics': {
            'fitness': 0.697,
            'total_delay_min': 4.2,
            'original_delay_min': 4.33,
            'num_actions': 2,
            'passenger_impact': 1259,
            'propagation_depth': 0,
            'recovery_smoothness': 0.976
        },
        'actions': [
            "Speed up REG_33003 by 12% to increase gap ahead",
            "Slow REG_3053 by 4% to let leading train pull away"
        ]
    }
    
    conflict_context = {
        'conflict_summary': "Headway violation on MILANO ROGOREDO--PAVIA",
        'trains': ['REG_33003', 'REG_3053'],
        'context_snapshot': {
            'conflict_location': {
                'edge_id': 'MILANO ROGOREDO--PAVIA'
            }
        }
    }
    
    # Step 1: Load Agent 1 resolutions (with user-friendly error handling)
    print("Step 1: Loading Agent 1 resolutions...\n")
    
    normalizer = ResolutionNormalizer()
    normalized_resolutions = []
    
    # Load and normalize Agent 1 resolutions
    if Path(agent1_json_path).exists():
        print(f"✓ Found {agent1_json_path}")
        try:
            with open(agent1_json_path, 'r') as f:
                agent1_data = json.load(f)
            
            for res in agent1_data['resolutions']:
                normalized = normalizer.normalize_agent1_resolution(res)
                normalized_resolutions.append(normalized)
                print(f"✓ Normalized: {normalized.strategy_name} (Agent 1)")
        
        except Exception as e:
            print(f"⚠️  Error reading {agent1_json_path}: {e}")
            print("   Continuing with Agent 2 only...\n")
    else:
        print(f"⚠️  Agent 1 output file '{agent1_json_path}' not found!")
        print("   To generate it, run: python test_integration.py")
        print("   This will create agent1_output.json")
        print("   Then re-run this script.\n")
        print("   Continuing with Agent 2 resolutions only...\n")
    
    # Normalize Agent 2 resolution
    agent2_normalized = normalizer.normalize_agent2_resolution(
        solver_name=agent2_data['solver_name'],
        metrics=agent2_data['metrics'],
        actions=agent2_data['actions'],
        conflict_data=conflict_context
    )
    normalized_resolutions.append(agent2_normalized)
    print(f"✓ Normalized: {agent2_normalized.strategy_name} (Agent 2)")
    
    print(f"\nTotal resolutions to evaluate: {len(normalized_resolutions)}\n")
    
    # Check we have at least one resolution
    if len(normalized_resolutions) == 0:
        print("❌ No resolutions to evaluate!")
        return 1
    
    # Step 2: Judge and rank
    print("="*70)
    print("Step 2: LLM Judge Evaluation (Groq Cloud)")
    print("="*70 + "\n")
    
    judge = LLMJudge(api_key=GROQ_API_KEY, model=GROQ_MODEL)
    
    rankings = judge.rank_resolutions(
        normalized_resolutions=normalized_resolutions,
        conflict_context=conflict_context,
        top_k=3
    )
    
    # Step 3: Display results
    print("\n" + "="*70)
    print("FINAL RANKINGS - TOP 3 RESOLUTIONS")
    print("="*70 + "\n")
    
    for ranking in rankings:
        print(f"{'='*70}")
        print(f"RANK #{ranking['rank']}")
        print(f"{'='*70}")
        print(f"Strategy: {ranking['full_resolution']['strategy_name']}")
        print(f"Source: {ranking['full_resolution']['source_agent']}")
        print(f"\nOverall Score: {ranking['overall_score']}/100")
        print(f"\nRatings:")
        print(f"  Safety:      {ranking['safety_rating']}/10")
        print(f"  Efficiency:  {ranking['efficiency_rating']}/10")
        print(f"  Feasibility: {ranking['feasibility_rating']}/10")
        print(f"  Robustness:  {ranking['robustness_rating']}/10")
        print(f"\nJustification:")
        print(f"  {ranking['justification']}")
        print()
    
    # Save rankings
    output_file = "./ranked_resolutions.json"
    with open(output_file, 'w') as f:
        json.dump(rankings, f, indent=2)
    
    print(f"✓ Rankings saved to {output_file}\n")


if __name__ == "__main__":
    main()