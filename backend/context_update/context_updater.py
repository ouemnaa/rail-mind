"""
Context Updater: Action-to-Parameter Translator

This system interprets resolution actions and updates the network context
while STRICTLY preserving the original JSON structure.

CRITICAL: Never add or remove fields - only update values!
"""

import json
import copy
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests


# =========================
# Action Interpreter
# =========================

class ActionToParameterInterpreter:
    """
    Uses LLM to interpret natural language actions and translate them
    into specific parameter updates for the context file.
    """
    
    def __init__(
        self,
        llm_api_key: str,
        llm_model: str = "tngtech/deepseek-r1t2-chimera:free"
    ):
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_url = "https://openrouter.ai/api/v1/chat/completions"
    
    def interpret_actions(
        self,
        actions: List[str],
        context: Dict[str, Any],
        affected_trains: List[str],
        resolution_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Interpret actions and return parameter update instructions.
        
        Args:
            actions: List of action strings from bullet_resolution_actions
            context: Current network context
            affected_trains: Trains mentioned in the resolution
            resolution_metadata: Additional context (strategy_name, etc.)
        
        Returns:
            Dictionary of parameter updates
        """
        
        # Build context summary for LLM
        context_summary = self._build_context_summary(context)
        
        # Create interpretation prompt
        prompt = self._build_interpretation_prompt(
            actions=actions,
            context_summary=context_summary,
            affected_trains=affected_trains,
            resolution_metadata=resolution_metadata
        )
        
        # Get LLM interpretation
        try:
            response = self._call_llm(prompt)
            updates = self._parse_update_instructions(response)
            return updates
        
        except Exception as e:
            print(f"⚠️ LLM interpretation failed: {e}")
            # Fallback to rule-based interpretation
            return self._fallback_interpretation(actions, affected_trains, context)
    
    def _build_context_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Build a concise summary of the context for the LLM"""
        
        summary = {
            "total_trains": len(context.get("trains", [])),
            "total_rails": len(context.get("rails", [])),
            "total_stations": len(context.get("stations", [])),
            "available_fields": {
                "train_fields": ["train_id", "train_type", "route_id", "route"],
                "rail_fields": [
                    "source", "target", "edge_type", "distance_km", 
                    "travel_time_min", "capacity", "current_load", 
                    "direction", "min_headway_sec", "max_speed_kmh", 
                    "reroutable", "priority_access", "risk_profile", 
                    "historical_incidents"
                ],
                "route_stop_fields": [
                    "station_name", "station_order", "lat", "lon", 
                    "distance_from_previous_km"
                ]
            }
        }
        
        return summary
    
    def _build_interpretation_prompt(
        self,
        actions: List[str],
        context_summary: Dict[str, Any],
        affected_trains: List[str],
        resolution_metadata: Dict[str, Any]
    ) -> str:
        """Build the LLM prompt for action interpretation"""
        
        prompt = f"""You are a railway operations expert. Interpret the following resolution actions and translate them into specific parameter updates for the network context.

RESOLUTION STRATEGY: {resolution_metadata.get('strategy_name', 'Unknown')}

ACTIONS TO IMPLEMENT:
{json.dumps(actions, indent=2)}

AFFECTED TRAINS: {', '.join(affected_trains)}

NETWORK CONTEXT STRUCTURE:
{json.dumps(context_summary, indent=2)}

YOUR TASK:
For each action, identify which parameters in the context need to be updated and by how much.

CRITICAL RULES:
1. You can ONLY modify VALUES of existing fields
2. You CANNOT add new fields
3. You CANNOT remove fields
4. All changes must be to existing parameters in the context structure

AVAILABLE PARAMETERS TO MODIFY:

For TRAINS:
- route (can modify route stops, but keep same fields)

For RAILS (edges between stations):
- travel_time_min: Increase/decrease travel time
- current_load: Change number of trains on edge
- min_headway_sec: Adjust minimum separation time
- max_speed_kmh: Set speed restrictions
- capacity: Modify capacity (rarely changed)
- risk_profile: Update risk level ("low", "medium", "high")

For ROUTE STOPS:
- distance_from_previous_km: Adjust if rerouting

INTERPRETATION RULES:
- "reduce speed by X%" → Decrease max_speed_kmh on relevant rails
- "extend dwell time" → Increase travel_time_min at that station's rail
- "speed restriction" → Decrease max_speed_kmh
- "reschedule" → Adjust travel_time_min
- "priority to train X" → May affect current_load or min_headway_sec
- "activate MILP/optimization" → This is a control action, may affect multiple parameters
- "implement ETCS" → This is infrastructure, may affect max_speed_kmh enforcement

Return ONLY a JSON object with this structure:
{{
  "train_updates": [
    {{
      "train_id": "REG_3053",
      "updates": {{
        "field": "route",
        "operation": "keep_same",
        "reason": "No routing changes needed"
      }}
    }}
  ],
  "rail_updates": [
    {{
      "source": "MILANO ROGOREDO",
      "target": "PAVIA",
      "updates": [
        {{
          "field": "max_speed_kmh",
          "operation": "multiply",
          "value": 0.85,
          "reason": "Reduce speed by 15% for REG_3053"
        }},
        {{
          "field": "travel_time_min",
          "operation": "multiply",
          "value": 1.15,
          "reason": "Increased travel time due to speed reduction"
        }}
      ]
    }}
  ],
  "global_updates": [
    {{
      "description": "Overall strategy implementation notes",
      "affects": "System-wide parameters if any"
    }}
  ]
}}

Operations allowed: "set", "multiply", "add", "subtract", "keep_same"

Focus on the DIRECT parameter changes needed to implement these actions.
Be specific about which rails (source→target) are affected.
"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call OpenRouter API"""
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Context Updater"
        }
        
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,  # Low temperature for consistent interpretation
            "max_tokens": 3072
        }
        
        response = requests.post(
            self.llm_url,
            headers=headers,
            json=payload,
            timeout=120
        )
        
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        
        # Remove markdown fences
        if content.startswith("```"):
            content = content.split("```")[1]
            content = content.replace("json", "").strip()
        
        return content
    
    def _parse_update_instructions(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into update instructions"""
        try:
            updates = json.loads(response)
            return updates
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse LLM response: {e}")
            print(f"Response: {response[:500]}")
            return {"train_updates": [], "rail_updates": [], "global_updates": []}
    
    def _fallback_interpretation(
        self,
        actions: List[str],
        affected_trains: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rule-based fallback interpretation when LLM fails"""
        
        updates = {
            "train_updates": [],
            "rail_updates": [],
            "global_updates": []
        }
        
        # Simple keyword-based rules
        for action in actions:
            action_lower = action.lower()
            
            # Speed reduction
            if "reduce speed" in action_lower or "speed reduction" in action_lower:
                # Find percentage if mentioned
                import re
                match = re.search(r'(\d+)[-\s]*%', action)
                reduction = float(match.group(1)) / 100 if match else 0.15
                
                updates["global_updates"].append({
                    "description": f"Apply {reduction*100}% speed reduction",
                    "parameter": "max_speed_kmh",
                    "operation": "multiply",
                    "value": 1 - reduction
                })
            
            # Dwell time / delay
            if "dwell time" in action_lower or "extend" in action_lower:
                updates["global_updates"].append({
                    "description": "Extend dwell time",
                    "parameter": "travel_time_min",
                    "operation": "add",
                    "value": 1.5  # Add 1.5 minutes
                })
            
            # Speed restriction
            if "speed restriction" in action_lower or "limit speed" in action_lower:
                updates["global_updates"].append({
                    "description": "Apply speed restriction",
                    "parameter": "max_speed_kmh",
                    "operation": "set",
                    "value": 80  # Default restriction to 80 km/h
                })
        
        return updates


# =========================
# Context Updater
# =========================

class ContextUpdater:
    """
    Applies parameter updates to the context file while preserving structure
    """
    
    def __init__(self, interpreter: ActionToParameterInterpreter):
        self.interpreter = interpreter
    
    def update_context(
        self,
        resolution: Dict[str, Any],
        original_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update context based on resolution actions.
        
        Args:
            resolution: The chosen resolution (with bullet_resolution_actions)
            original_context: The current network context
        
        Returns:
            Updated context with same structure
        """
        
        # Deep copy to avoid modifying original
        updated_context = copy.deepcopy(original_context)
        
        # Extract action information
        actions = resolution.get("bullet_resolution_actions", {}).get("actions", [])
        affected_trains = resolution.get("full_resolution", {}).get("affected_trains", [])
        
        resolution_metadata = {
            "strategy_name": resolution.get("resolution_id", "Unknown"),
            "estimated_delay_min": resolution.get("full_resolution", {}).get("estimated_delay_min", 0)
        }
        
        print(f"\n🔄 Updating context for resolution: {resolution_metadata['strategy_name']}")
        print(f"   Actions to implement: {len(actions)}")
        print(f"   Affected trains: {', '.join(affected_trains)}")
        
        # Get parameter update instructions from LLM
        update_instructions = self.interpreter.interpret_actions(
            actions=actions,
            context=original_context,
            affected_trains=affected_trains,
            resolution_metadata=resolution_metadata
        )
        
        # Apply updates
        self._apply_updates(updated_context, update_instructions, affected_trains)
        
        # Validate structure hasn't changed
        self._validate_structure(original_context, updated_context)
        
        return updated_context
    
    def _apply_updates(
        self,
        context: Dict[str, Any],
        instructions: Dict[str, Any],
        affected_trains: List[str]
    ):
        """Apply the update instructions to the context"""
        
        # Apply rail updates
        for rail_update in instructions.get("rail_updates", []):
            self._apply_rail_update(context, rail_update)
        
        # Apply train updates
        for train_update in instructions.get("train_updates", []):
            self._apply_train_update(context, train_update)
        
        # Apply global updates (affects multiple rails/trains)
        for global_update in instructions.get("global_updates", []):
            self._apply_global_update(context, global_update, affected_trains)
    
    def _apply_rail_update(self, context: Dict[str, Any], rail_update: Dict[str, Any]):
        """Update a specific rail"""
        
        source = rail_update.get("source")
        target = rail_update.get("target")
        
        # Find the rail
        for rail in context.get("rails", []):
            if rail["source"] == source and rail["target"] == target:
                
                # Apply each field update
                for update in rail_update.get("updates", []):
                    field = update["field"]
                    operation = update["operation"]
                    value = update.get("value")
                    
                    if field in rail:
                        rail[field] = self._apply_operation(
                            rail[field], operation, value
                        )
                        print(f"   ✓ Updated {source}→{target}: {field} = {rail[field]}")
    
    def _apply_train_update(self, context: Dict[str, Any], train_update: Dict[str, Any]):
        """Update a specific train"""
        
        train_id = train_update.get("train_id")
        
        # Find the train
        for train in context.get("trains", []):
            if train["train_id"] == train_id:
                
                updates = train_update.get("updates", {})
                # For now, we mainly keep route same or modify stops
                # Route structure modifications would go here if needed
                print(f"   ✓ Checked train {train_id}")
    
    def _apply_global_update(
        self,
        context: Dict[str, Any],
        global_update: Dict[str, Any],
        affected_trains: List[str]
    ):
        """Apply updates that affect multiple rails or trains"""
        
        parameter = global_update.get("parameter")
        operation = global_update.get("operation")
        value = global_update.get("value")
        
        if not parameter:
            return
        
        # Find rails used by affected trains
        affected_rails = self._find_rails_for_trains(context, affected_trains)
        
        # Apply to each affected rail
        for rail in affected_rails:
            if parameter in rail:
                old_value = rail[parameter]
                rail[parameter] = self._apply_operation(old_value, operation, value)
                print(f"   ✓ Global update {rail['source']}→{rail['target']}: {parameter} = {rail[parameter]}")
    
    def _find_rails_for_trains(
        self,
        context: Dict[str, Any],
        train_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Find all rails that affected trains use"""
        
        affected_rails = []
        
        # Get routes for affected trains
        for train in context.get("trains", []):
            if train["train_id"] in train_ids:
                route = train.get("route", [])
                
                # Get consecutive station pairs
                for i in range(len(route) - 1):
                    source = route[i]["station_name"]
                    target = route[i + 1]["station_name"]
                    
                    # Find corresponding rail
                    for rail in context.get("rails", []):
                        if (rail["source"] == source and rail["target"] == target) or \
                           (rail["target"] == source and rail["source"] == target):
                            if rail not in affected_rails:
                                affected_rails.append(rail)
        
        return affected_rails
    
    def _apply_operation(self, current_value: Any, operation: str, new_value: Any) -> Any:
        """Apply an operation to a value"""
        
        if operation == "set":
            return new_value
        
        elif operation == "multiply":
            if isinstance(current_value, (int, float)):
                return current_value * new_value
            return current_value
        
        elif operation == "add":
            if isinstance(current_value, (int, float)):
                return current_value + new_value
            return current_value
        
        elif operation == "subtract":
            if isinstance(current_value, (int, float)):
                return current_value - new_value
            return current_value
        
        elif operation == "keep_same":
            return current_value
        
        else:
            print(f"⚠️ Unknown operation: {operation}")
            return current_value
    
    def _validate_structure(self, original: Dict[str, Any], updated: Dict[str, Any]):
        """Validate that structure hasn't changed"""
        
        # Check top-level keys
        original_keys = set(original.keys())
        updated_keys = set(updated.keys())
        
        if original_keys != updated_keys:
            raise ValueError(f"Structure changed! Keys differ: {original_keys ^ updated_keys}")
        
        # Check trains structure
        if len(original.get("trains", [])) != len(updated.get("trains", [])):
            raise ValueError("Number of trains changed!")
        
        for orig_train, upd_train in zip(original["trains"], updated["trains"]):
            if set(orig_train.keys()) != set(upd_train.keys()):
                raise ValueError(f"Train {orig_train.get('train_id')} structure changed!")
        
        # Check rails structure
        if len(original.get("rails", [])) != len(updated.get("rails", [])):
            raise ValueError("Number of rails changed!")
        
        for orig_rail, upd_rail in zip(original["rails"], updated["rails"]):
            if set(orig_rail.keys()) != set(upd_rail.keys()):
                raise ValueError(f"Rail {orig_rail.get('source')}→{orig_rail.get('target')} structure changed!")
        
        print("   ✓ Structure validation passed")


# =========================
# Main System
# =========================

class ResolutionContextUpdater:
    """
    Main system that takes a resolution and updates the context
    """
    
    def __init__(self, llm_api_key: str, llm_model: str = "tngtech/deepseek-r1t2-chimera:free"):
        self.interpreter = ActionToParameterInterpreter(llm_api_key, llm_model)
        self.updater = ContextUpdater(self.interpreter)
    
    def apply_resolution(
        self,
        resolution_file: str,
        context_file: str,
        output_file: str
    ):
        """
        Apply a resolution to the context and save updated context.
        
        Args:
            resolution_file: Path to resolution JSON
            context_file: Path to current context JSON
            output_file: Path to save updated context
        """
        
        print(f"\n{'='*70}")
        print("RESOLUTION CONTEXT UPDATER")
        print(f"{'='*70}\n")
        
        # Load resolution
        with open(resolution_file, "r") as f:
            resolution = json.load(f)
        
        print(f"✓ Loaded resolution: {resolution.get('resolution_id', 'Unknown')}")
        print(f"  Rank: {resolution.get('rank', 'N/A')}")
        print(f"  Overall Score: {resolution.get('overall_score', 'N/A')}")
        
        # Load context
        with open(context_file, "r") as f:
            context = json.load(f)
        
        print(f"✓ Loaded context: {len(context.get('trains', []))} trains, {len(context.get('rails', []))} rails")
        
        # Update context
        updated_context = self.updater.update_context(resolution, context)
        
        # Save updated context
        with open(output_file, "w") as f:
            json.dump(updated_context, f, indent=2)
        
        print(f"\n✅ Updated context saved to: {output_file}")
        print(f"\n{'='*70}\n")
        
        return updated_context


# =========================
# Example Usage
# =========================

def main():
    """
    Example usage of the context updater
    """
    
    # Configuration
    OPENROUTER_API_KEY = "sk-or-v1-YOUR-API-KEY"  # Replace with your key
    
    # File paths
    RESOLUTION_FILE = "chosen_resolution.json"  # Your resolution JSON
    CONTEXT_FILE = "lombardy_simulation_data.json"  # Current context
    OUTPUT_FILE = "updated_context.json"  # Where to save updated context
    
    # Initialize system
    updater = ResolutionContextUpdater(
        llm_api_key=OPENROUTER_API_KEY,
        llm_model="tngtech/deepseek-r1t2-chimera:free"
    )
    
    # Apply resolution
    updated_context = updater.apply_resolution(
        resolution_file=RESOLUTION_FILE,
        context_file=CONTEXT_FILE,
        output_file=OUTPUT_FILE
    )
    
    print("✓ Context update complete!")


if __name__ == "__main__":
    main()
