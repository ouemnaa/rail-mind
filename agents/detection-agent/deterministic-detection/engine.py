"""
Conflict Detection Engine
Orchestrates rule evaluation and emits conflict events.
"""

import json
from typing import List, Dict, Optional, Callable
from datetime import datetime

from models import Conflict, ConflictSeverity
from state_tracker import StateTracker, NetworkState
from rules import ALL_RULES, ConflictRule


class ConflictEmitter:
    """
    Handles emission of conflict events.
    Supports multiple output channels (console, JSON, callbacks).
    """
    
    def __init__(self, enable_console: bool = True, json_file: Optional[str] = None):
        self.enable_console = enable_console
        self.json_file = json_file
        self.callbacks: List[Callable[[Conflict], None]] = []
        self.conflict_history: List[Conflict] = []
        
        # Deduplication: track recent conflicts to avoid spam
        self._recent_conflicts: Dict[str, datetime] = {}
        self._dedup_window_seconds = 600  # Increased to 10 mins to avoid re-emitting same event
    
    def register_callback(self, callback: Callable[[Conflict], None]) -> None:
        """Register a callback to be invoked on each conflict."""
        self.callbacks.append(callback)
    
    def _should_emit(self, conflict: Conflict) -> bool:
        """Check if conflict should be emitted (deduplication)."""
        # Create a signature for deduplication
        sig = f"{conflict.conflict_type.value}|{conflict.node_id}|{conflict.edge_id}|{','.join(sorted(conflict.involved_trains))}"
        
        last_seen = self._recent_conflicts.get(sig)
        if last_seen:
            elapsed = (conflict.timestamp - last_seen).total_seconds()
            if elapsed < self._dedup_window_seconds:
                return False
        
        self._recent_conflicts[sig] = conflict.timestamp
        return True
    
    def emit(self, conflict: Conflict) -> None:
        """Emit a single conflict."""
        if not self._should_emit(conflict):
            return
        
        self.conflict_history.append(conflict)
        
        # Console output
        if self.enable_console:
            self._log_to_console(conflict)
        
        # JSON file
        if self.json_file:
            self._append_to_json(conflict)
        
        # Callbacks
        for callback in self.callbacks:
            try:
                callback(conflict)
            except Exception as e:
                print(f"[Emitter] Callback error: {e}")
    
    def emit_batch(self, conflicts: List[Conflict]) -> None:
        """Emit multiple conflicts."""
        for conflict in conflicts:
            self.emit(conflict)
    
    def _log_to_console(self, conflict: Conflict) -> None:
        """Log conflict to console with formatting."""
        severity_colors = {
            ConflictSeverity.LOW: "\033[94m",      # Blue
            ConflictSeverity.MEDIUM: "\033[93m",   # Yellow
            ConflictSeverity.HIGH: "\033[91m",     # Red
            ConflictSeverity.CRITICAL: "\033[95m", # Magenta
        }
        reset = "\033[0m"
        color = severity_colors.get(conflict.severity, "")
        
        location = conflict.node_id or conflict.edge_id or "network"
        trains = ", ".join(conflict.involved_trains[:3])
        if len(conflict.involved_trains) > 3:
            trains += f" (+{len(conflict.involved_trains) - 3} more)"
        
        print(
            f"{color}[{conflict.severity.value.upper()}]{reset} "
            f"{conflict.conflict_type.value} @ {location} | "
            f"Trains: {trains or 'N/A'} | "
            f"{conflict.explanation[:80]}..."
        )
    
    def _append_to_json(self, conflict: Conflict) -> None:
        """Append conflict to JSON file."""
        try:
            with open(self.json_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(conflict.to_dict()) + "\n")
        except Exception as e:
            print(f"[Emitter] JSON write error: {e}")
    
    def get_statistics(self) -> Dict:
        """Get conflict statistics."""
        stats = {
            "total": len(self.conflict_history),
            "by_severity": {},
            "by_type": {},
        }
        
        for conflict in self.conflict_history:
            sev = conflict.severity.value
            typ = conflict.conflict_type.value
            stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
            stats["by_type"][typ] = stats["by_type"].get(typ, 0) + 1
        
        return stats


class DetectionEngine:
    """
    Main conflict detection engine.
    Orchestrates state tracking, rule evaluation, and conflict emission.
    """
    
    def __init__(
        self,
        state_tracker: StateTracker,
        rules: Optional[List[ConflictRule]] = None,
        emitter: Optional[ConflictEmitter] = None
    ):
        self.state_tracker = state_tracker
        self.rules = rules or ALL_RULES
        self.emitter = emitter or ConflictEmitter()
        
        self._evaluation_count = 0
        self._total_conflicts_detected = 0
    
    def evaluate_all_rules(self) -> List[Conflict]:
        """
        Evaluate all rules against current state.
        Returns list of detected conflicts.
        """
        self._evaluation_count += 1
        all_conflicts: List[Conflict] = []
        
        for rule in self.rules:
            try:
                conflicts = rule.evaluate(self.state_tracker.state)
                all_conflicts.extend(conflicts)
            except Exception as e:
                print(f"[Engine] Rule {rule.rule_id} failed: {e}")
        
        self._total_conflicts_detected += len(all_conflicts)
        
        # Emit all conflicts
        self.emitter.emit_batch(all_conflicts)
        
        return all_conflicts
    
    def evaluate_single_rule(self, rule_id: str) -> List[Conflict]:
        """Evaluate a specific rule by ID."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                conflicts = rule.evaluate(self.state_tracker.state)
                self.emitter.emit_batch(conflicts)
                return conflicts
        
        print(f"[Engine] Rule not found: {rule_id}")
        return []
    
    def tick(self, new_time: datetime) -> List[Conflict]:
        """
        Advance time and evaluate rules.
        This is the main entry point for real-time detection.
        """
        self.state_tracker.update_time(new_time)
        return self.evaluate_all_rules()
    
    def get_state_snapshot(self) -> Dict:
        """Get current network state snapshot."""
        return self.state_tracker.get_snapshot()
    
    def get_statistics(self) -> Dict:
        """Get engine statistics."""
        return {
            "evaluation_count": self._evaluation_count,
            "total_conflicts_detected": self._total_conflicts_detected,
            "rules_active": len(self.rules),
            "conflict_stats": self.emitter.get_statistics()
        }
    
    def list_rules(self) -> List[Dict]:
        """List all active rules."""
        return [
            {"rule_id": r.rule_id, "description": r.description}
            for r in self.rules
        ]
