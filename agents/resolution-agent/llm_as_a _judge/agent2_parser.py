"""
Parser for Agent 2 Console Output
Extracts structured data from Agent 2's text-based resolution output
"""

import re
from typing import Dict, List, Any, Optional


class Agent2OutputParser:
    """
    Parse Agent 2's console output into structured format
    """
    
    def parse_console_output(self, console_text: str) -> Dict[str, Any]:
        """
        Parse Agent 2's console output
        
        Args:
            console_text: Raw console output from Agent 2
            
        Returns:
            Structured dictionary with solver data
        """
        
        # Extract conflict ID and details
        conflict_id = self._extract_conflict_id(console_text)
        conflict_type = self._extract_conflict_type(console_text)
        severity = self._extract_severity(console_text)
        trains = self._extract_trains(console_text)
        stations = self._extract_stations(console_text)
        
        # Extract solver results
        solver_results = self._extract_solver_results(console_text)
        
        # Extract best solution details
        best_solver, solution_details = self._extract_best_solution(console_text)
        
        return {
            'conflict': {
                'id': conflict_id,
                'type': conflict_type,
                'severity': severity,
                'trains': trains,
                'stations': stations
            },
            'solver_results': solver_results,
            'best_solution': {
                'solver': best_solver,
                **solution_details
            }
        }
    
    def _extract_conflict_id(self, text: str) -> Optional[str]:
        """Extract conflict ID like [c3f29257]"""
        match = re.search(r'\[([a-f0-9-]+)\]', text)
        return match.group(1) if match else None
    
    def _extract_conflict_type(self, text: str) -> str:
        """Extract conflict type (e.g., HEADWAY)"""
        match = re.search(r'\] ([A-Z_]+) \(severity', text)
        return match.group(1) if match else "UNKNOWN"
    
    def _extract_severity(self, text: str) -> float:
        """Extract severity score"""
        match = re.search(r'severity: ([\d.]+)', text)
        return float(match.group(1)) if match else 0.0
    
    def _extract_trains(self, text: str) -> List[str]:
        """Extract train IDs"""
        match = re.search(r'Trains: ([^\n]+)', text)
        if match:
            trains_str = match.group(1)
            return [t.strip() for t in trains_str.split(',')]
        return []
    
    def _extract_stations(self, text: str) -> List[str]:
        """Extract station names"""
        match = re.search(r'Stations: ([^\n]+)', text)
        if match:
            stations_str = match.group(1)
            return [s.strip() for s in stations_str.split(',')]
        return []
    
    def _extract_solver_results(self, text: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract all solver results from DEBUG section
        """
        results = {}
        
        # Find all solver lines like: "- greedy: fitness=0.499, actions=2, delay=5.8min"
        solver_pattern = r'- ([a-z_]+):\s+fitness=([\d.]+),\s+actions=(\d+),\s+delay=([\d.]+)min'
        
        for match in re.finditer(solver_pattern, text):
            solver_name = match.group(1)
            fitness = float(match.group(2))
            actions = int(match.group(3))
            delay = float(match.group(4))
            
            results[solver_name] = {
                'fitness': fitness,
                'num_actions': actions,
                'total_delay_min': delay
            }
        
        return results
    
    def _extract_best_solution(self, text: str) -> tuple:
        """Extract the best solution details"""
        
        # Extract solver name
        solver_match = re.search(r'Solver: ([a-z_]+)', text)
        solver_name = solver_match.group(1) if solver_match else "unknown"
        
        # Extract metrics
        fitness_match = re.search(r'Overall Fitness: ([\d.]+)', text)
        delay_match = re.search(r'Total Delay: ([\d.]+) min', text)
        was_delay_match = re.search(r'was ([\d.]+) min', text)
        improvement_match = re.search(r'→ \+?([-\d.]+)%', text)
        passenger_match = re.search(r'Passenger Impact: (\d+)', text)
        propagation_match = re.search(r'Propagation Depth: (\d+)', text)
        smoothness_match = re.search(r'Recovery Smoothness: ([\d.]+)', text)
        
        # Extract actions
        actions = self._extract_actions(text)
        
        solution_details = {
            'fitness': float(fitness_match.group(1)) if fitness_match else 0.0,
            'total_delay_min': float(delay_match.group(1)) if delay_match else 0.0,
            'original_delay_min': float(was_delay_match.group(1)) if was_delay_match else 0.0,
            'improvement_pct': float(improvement_match.group(1)) if improvement_match else 0.0,
            'passenger_impact': int(passenger_match.group(1)) if passenger_match else 0,
            'propagation_depth': int(propagation_match.group(1)) if propagation_match else 0,
            'recovery_smoothness': float(smoothness_match.group(1)) if smoothness_match else 0.0,
            'actions': actions,
            'num_actions': len(actions)
        }
        
        return solver_name, solution_details
    
    def _extract_actions(self, text: str) -> List[str]:
        """Extract action steps"""
        actions = []
        
        # Find lines after "Actions for" that are numbered
        action_pattern = r'\d+\.\s+(.+?)(?:\s{2,}|$)'
        
        # Find the actions section
        actions_section_match = re.search(r'Actions for [^:]+:(.*?)(?:\n\n|$)', text, re.DOTALL)
        if actions_section_match:
            actions_text = actions_section_match.group(1)
            
            for match in re.finditer(action_pattern, actions_text):
                action_text = match.group(1).strip()
                if action_text and not action_text.startswith('['):
                    actions.append(action_text)
        
        return actions


# =========================
# Example Usage
# =========================

def example_parse_agent2_output():
    """
    Example: Parse Agent 2's console output
    """
    
    console_output = """
=== CONFLICT LOADED ===
 [c3f29257] HEADWAY (severity: 0.95)
  Trains: REG_33003, REG_3053
  Stations: MILANO ROGOREDO, PAVIA
  Delays: REG_33003: 2.2min, REG_3053: 2.2min
============================================================
RESOLVING: [c3f29257] HEADWAY (severity: 0.95)
  Trains: REG_33003, REG_3053
  Stations: MILANO ROGOREDO, PAVIA
  Delays: REG_33003: 2.2min, REG_3053: 2.2min
============================================================
  [DEBUG] Running all solvers...
    - greedy: fitness=0.499, actions=2, delay=5.8min
    - lns: fitness=0.559, actions=2, delay=5.0min
    - simulated_annealing: fitness=0.693, actions=2, delay=4.2min
    - nsga2: fitness=0.536, actions=1, delay=5.0min
    - genetic_algorithm: fitness=0.697, actions=2, delay=4.2min
🚆 RESOLUTION PLAN (Solver: genetic_algorithm)
   Overall Fitness: 0.6972
   Total Delay: 4.20 min (was 4.33 min) → +3.1%
   Passenger Impact: 1259
   Propagation Depth: 0
   Recovery Smoothness: 0.976
   Actions for HEADWAY conflict:
   1. Speed up REG_33003 by 12% to increase gap ahead      
   2. Slow REG_3053 by 4% to let leading train pull away   
"""
    
    parser = Agent2OutputParser()
    parsed = parser.parse_console_output(console_output)
    
    print("="*70)
    print("PARSED AGENT 2 OUTPUT")
    print("="*70 + "\n")
    
    print("Conflict:")
    print(f"  ID: {parsed['conflict']['id']}")
    print(f"  Type: {parsed['conflict']['type']}")
    print(f"  Severity: {parsed['conflict']['severity']}")
    print(f"  Trains: {', '.join(parsed['conflict']['trains'])}")
    print(f"  Stations: {', '.join(parsed['conflict']['stations'])}")
    
    print("\nSolver Results:")
    for solver, metrics in parsed['solver_results'].items():
        print(f"  {solver}: fitness={metrics['fitness']:.3f}, delay={metrics['total_delay_min']:.1f}min")
    
    print("\nBest Solution:")
    best = parsed['best_solution']
    print(f"  Solver: {best['solver']}")
    print(f"  Fitness: {best['fitness']:.3f}")
    print(f"  Delay: {best['total_delay_min']:.1f}min (was {best['original_delay_min']:.1f}min)")
    print(f"  Improvement: {best['improvement_pct']:.1f}%")
    print(f"  Actions:")
    for i, action in enumerate(best['actions'], 1):
        print(f"    {i}. {action}")
    
    print("\n" + "="*70)
    
    import json
    print("\nJSON Output:")
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    example_parse_agent2_output()
