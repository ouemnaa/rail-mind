"""
All mathematical models for rail network conflict resolution.
- Delay propagation equations
- Multi-objective fitness function
- Optimization algorithms (Greedy, LNS, SA, NSGA-II)
"""
import numpy as np
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass
import random
import math

from .data_structures import Conflict, Context, Resolution, ResolutionPlan, ActionType


# =============================================================================
# DELAY PROPAGATION MODEL
# =============================================================================

@dataclass
class DelayParams:
    """Parameters for delay propagation equations."""
    weather_penalty: Dict[str, float] = None
    absorption_rate: float = 0.1  # fraction of delay absorbed per stop
    min_dwell_time: float = 1.0   # minutes
    max_dwell_time: float = 5.0
    
    def __post_init__(self):
        if self.weather_penalty is None:
            self.weather_penalty = {
                "clear": 0.0,
                "rain": 0.05,
                "snow": 0.15,
                "fog": 0.08
            }


class DelayPropagation:
    """
    Delay propagation model based on the equations:
    
    arrival_delay[i+1] = max(0, departure_delay[i] + run_delta + weather_penalty)
    departure_delay[i+1] = max(0, arrival_delay[i+1] - absorption + dwell_delta)
    
    Where:
    - run_delta: deviation from scheduled running time
    - weather_penalty: additional delay due to weather
    - absorption: delay absorbed at station (buffer time)
    - dwell_delta: deviation from scheduled dwell time
    """
    
    def __init__(self, params: Optional[DelayParams] = None):
        self.params = params or DelayParams()
    
    def propagate_single_train(
        self,
        initial_delay: float,
        num_stops: int,
        weather: str,
        run_deltas: Optional[List[float]] = None,
        dwell_deltas: Optional[List[float]] = None
    ) -> Tuple[List[float], List[float]]:
        """
        Propagate delay for a single train through its stops.
        
        Returns:
            arrival_delays: delay at arrival for each stop
            departure_delays: delay at departure for each stop
        """
        if run_deltas is None:
            run_deltas = [0.0] * num_stops
        if dwell_deltas is None:
            dwell_deltas = [0.0] * num_stops
            
        weather_pen = self.params.weather_penalty.get(weather, 0.0)
        absorption = self.params.absorption_rate * initial_delay
        
        arrival_delays = [initial_delay]
        departure_delays = [initial_delay]
        
        for i in range(num_stops - 1):
            # Arrival at next stop
            arr_delay = max(0, departure_delays[-1] + run_deltas[i] + weather_pen)
            arrival_delays.append(arr_delay)
            
            # Departure from next stop
            dep_delay = max(0, arr_delay - absorption + dwell_deltas[i])
            departure_delays.append(dep_delay)
            
            # Update absorption (decreases as delay decreases)
            absorption = self.params.absorption_rate * dep_delay
        
        return arrival_delays, departure_delays
    
    def propagate_network(
        self,
        conflict: Conflict,
        resolutions: List[Resolution],
        context: Context,
        adjacency: Dict[str, List[str]]  # train_id -> connected train_ids
    ) -> Dict[str, float]:
        """
        Propagate delays through the network considering resolutions.
        
        Key principle: Actions should REDUCE total delay, not increase it.
        HOLD: Sacrifice this train's time to free resources → benefit other trains more
        SPEED_ADJUST: Reduce this train's delay directly
        REROUTE: Move train to different path, may add time but frees resources
        CANCEL: Zero delay for this train, free resources
        """
        # Apply resolution effects
        modified_delays = dict(conflict.delay_values)
        
        # Track cumulative cascade benefits to prevent over-reduction
        cascade_benefits = {train: 0.0 for train in conflict.train_ids}
        
        # Conflict-specific benefit multipliers
        is_headway = conflict.conflict_type == "headway"
        is_capacity = conflict.conflict_type == "capacity"
        
        for res in resolutions:
            train_id = res.target_train_id
            if train_id not in modified_delays:
                continue
                
            if res.action_type == ActionType.HOLD:
                # Hold: sacrifice time on this train to free platform/capacity
                hold_time = res.parameters.get("hold_minutes", 2.0)
                modified_delays[train_id] = max(0, modified_delays[train_id] + hold_time)
                
                # For HEADWAY conflicts: holding the trailing train directly solves the problem
                # The leading train can now proceed without conflict
                if is_headway and train_id in adjacency:
                    for connected in adjacency[train_id]:
                        if connected in modified_delays and modified_delays[connected] > 0:
                            # Headway: holding trailing gives 80% benefit to leading (conflict resolved)
                            potential_reduction = hold_time * 0.8
                            max_benefit = conflict.delay_values.get(connected, 0) * 0.6
                            allowed_reduction = min(
                                potential_reduction,
                                max_benefit - cascade_benefits.get(connected, 0),
                                modified_delays[connected]
                            )
                            if allowed_reduction > 0:
                                modified_delays[connected] -= allowed_reduction
                                cascade_benefits[connected] = cascade_benefits.get(connected, 0) + allowed_reduction
                
                # For other conflicts: moderate cascade
                elif train_id in adjacency:
                    for connected in adjacency[train_id]:
                        if connected in modified_delays and modified_delays[connected] > 0:
                            potential_reduction = hold_time * 0.3
                            max_benefit = conflict.delay_values.get(connected, 0) * 0.3
                            allowed_reduction = min(
                                potential_reduction,
                                max_benefit - cascade_benefits.get(connected, 0),
                                modified_delays[connected]
                            )
                            if allowed_reduction > 0:
                                modified_delays[connected] -= allowed_reduction
                                cascade_benefits[connected] += allowed_reduction
                
            elif res.action_type == ActionType.SPEED_ADJUST:
                # Speed adjustment: can be speedup (>1.0) or strategic slowdown (<1.0)
                speed_factor = res.parameters.get("speed_factor", 1.0)
                if speed_factor > 1.0:
                    # Speedup: reduce this train's delay
                    # 1.05x speed → save 5% of delay, 1.10x → save 10%, etc.
                    reduction = modified_delays[train_id] * (speed_factor - 1.0) * 0.8
                    modified_delays[train_id] = max(0, modified_delays[train_id] - reduction)
                elif speed_factor < 1.0:
                    # Strategic slowdown: sacrifice this train to reduce congestion for others
                    # This train gets MORE delay, but connected trains benefit
                    slowdown_penalty = modified_delays[train_id] * (1.0 - speed_factor)
                    modified_delays[train_id] = modified_delays[train_id] + slowdown_penalty
                    
                    # Slowdown reduces congestion → helps connected trains (like HOLD but smaller effect)
                    if train_id in adjacency:
                        for connected in adjacency[train_id]:
                            if connected in modified_delays and modified_delays[connected] > 0:
                                # Slowdown gives ~20% benefit to connected trains (less than HOLD's 30%)
                                potential_reduction = slowdown_penalty * 0.20
                                max_benefit = conflict.delay_values.get(connected, 0) * 0.3
                                allowed_reduction = min(
                                    potential_reduction,
                                    max_benefit - cascade_benefits.get(connected, 0),
                                    modified_delays[connected]
                                )
                                if allowed_reduction > 0:
                                    modified_delays[connected] -= allowed_reduction
                                    cascade_benefits[connected] = cascade_benefits.get(connected, 0) + allowed_reduction
                
            elif res.action_type == ActionType.CANCEL:
                # Cancelled train: zero delay, but frees platform/capacity
                modified_delays[train_id] = 0
                # Strong benefit to connected trains
                if train_id in adjacency:
                    for connected in adjacency[train_id]:
                        if connected in modified_delays:
                            # Cancellation frees ~40% of capacity, reducing others' delays
                            modified_delays[connected] = max(0, modified_delays[connected] * 0.6)
                
            elif res.action_type == ActionType.REROUTE:
                # Reroute: send train on alternate path
                # alternate_route=1 is first alternate (usually +1-2 min), 2 is second, etc.
                # Rerouting can INCREASE travel time but FREES resources for others
                alternate_route = res.parameters.get("alternate_route", 1)
                
                # Alternate routes typically add 1-3 minutes but free up the main line
                reroute_penalty = alternate_route * 1.5  # 1.5 min per alternate level
                modified_delays[train_id] = max(0, modified_delays[train_id] + reroute_penalty)
                
                # BUT: freeing the main route helps other trains significantly
                if train_id in adjacency:
                    for connected in adjacency[train_id]:
                        if connected in modified_delays and modified_delays[connected] > 0:
                            # Reroute frees ~40% of capacity benefit
                            potential_reduction = reroute_penalty * 0.8  # High benefit for freeing line
                            max_benefit = conflict.delay_values.get(connected, 0) * 0.4
                            allowed_reduction = min(
                                potential_reduction,
                                max_benefit - cascade_benefits.get(connected, 0),
                                modified_delays[connected]
                            )
                            if allowed_reduction > 0:
                                modified_delays[connected] -= allowed_reduction
                                cascade_benefits[connected] = cascade_benefits.get(connected, 0) + allowed_reduction
                
            elif res.action_type == ActionType.PLATFORM_CHANGE:
                # Platform change: minimal delay effect in current model
                # (In reality, might help but we model it as mostly neutral)
                pass
        
        # Very weak residual cascade for any remaining unresolved delays
        final_delays = dict(modified_delays)
        
        return final_delays


# =============================================================================
# ACTION VALIDATION
# =============================================================================

class ActionValidator:
    """
    Validates and post-processes resolution actions.
    Ensures actions are logically consistent with conflict type.
    """
    
    @staticmethod
    def validate_and_fix(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        Validate actions and fix any logical inconsistencies.
        Applies conflict-type-specific rules.
        """
        validated = []
        
        for res in resolutions:
            fixed_res = ActionValidator._validate_single(res, conflict)
            if fixed_res:
                validated.append(fixed_res)
        
        # Apply conflict-type-specific fixes
        validated = ActionValidator._apply_conflict_rules(validated, conflict)
        
        # Ensure at least one action
        if not validated and conflict.train_ids:
            validated = ActionValidator._create_default_action(conflict)
        
        return validated
    
    @staticmethod
    def _apply_conflict_rules(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        Apply conflict-type-specific validation rules.
        Safety-critical conflicts (collision, track, platform) get mandatory separation.
        """
        if conflict.conflict_type == "headway":
            return ActionValidator._fix_headway_actions(resolutions, conflict)
        elif conflict.conflict_type == "capacity":
            return ActionValidator._fix_capacity_actions(resolutions, conflict)
        elif conflict.conflict_type in ("track", "collision", "route_conflict"):
            return ActionValidator._fix_collision_risk_actions(resolutions, conflict)
        elif conflict.conflict_type == "platform":
            return ActionValidator._fix_platform_actions(resolutions, conflict)
        elif conflict.conflict_type == "signal":
            return ActionValidator._fix_signal_actions(resolutions, conflict)
        return resolutions
    
    @staticmethod
    def _fix_headway_actions(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        PREVENT headway violation before trains get too close.
        
        Detection agent predicts trains will violate minimum headway.
        Prevention: Create speed differential so gap INCREASES over time.
        - Speed up leading train (pulls away)
        - Slow down trailing train (falls back)
        - Or hold trailing train briefly to create initial gap
        """
        if len(conflict.train_ids) < 2:
            return resolutions
        
        # Check if we already have a proper separation action
        has_hold = any(r.action_type == ActionType.HOLD for r in resolutions)
        has_reroute = any(r.action_type == ActionType.REROUTE for r in resolutions)
        has_slowdown = any(
            r.action_type == ActionType.SPEED_ADJUST and 
            r.parameters.get("speed_factor", 1.0) <= 0.96  # Real slowdown (includes 5% = 0.95)
            for r in resolutions
        )
        
        if has_hold or has_reroute or has_slowdown:
            # Already have separation - just clean up the actions
            return [r for r in resolutions if not (
                r.action_type == ActionType.SPEED_ADJUST and 
                abs(r.parameters.get("speed_factor", 1.0) - 1.0) < 0.01  # Remove no-op speed adjustments
            )]
        
        # No separation action - we need to add HOLD for one train
        # Pick the second train in the list (arbitrary but consistent)
        # In real scenario, this would be the trailing train based on actual timing
        train_to_hold = conflict.train_ids[1] if len(conflict.train_ids) > 1 else conflict.train_ids[0]
        train_to_speed = conflict.train_ids[0]
        
        fixed = []
        held_train = False
        sped_train = False
        
        for res in resolutions:
            if res.target_train_id == train_to_hold:
                if not held_train:
                    # Force HOLD on this train
                    fixed.append(Resolution(
                        action_type=ActionType.HOLD,
                        target_train_id=train_to_hold,
                        parameters={"hold_minutes": 2.5}
                    ))
                    held_train = True
                # Skip any other actions for this train
            elif res.target_train_id == train_to_speed:
                if not sped_train:
                    # Keep or add speedup for the other train
                    if res.action_type == ActionType.SPEED_ADJUST:
                        speed = res.parameters.get("speed_factor", 1.0)
                        if speed >= 1.0:
                            fixed.append(res)
                        else:
                            fixed.append(Resolution(
                                action_type=ActionType.SPEED_ADJUST,
                                target_train_id=train_to_speed,
                                parameters={"speed_factor": 1.10}
                            ))
                    else:
                        fixed.append(Resolution(
                            action_type=ActionType.SPEED_ADJUST,
                            target_train_id=train_to_speed,
                            parameters={"speed_factor": 1.10}
                        ))
                    sped_train = True
            else:
                fixed.append(res)
        
        # Ensure we have both actions
        if not held_train:
            fixed.append(Resolution(
                action_type=ActionType.HOLD,
                target_train_id=train_to_hold,
                parameters={"hold_minutes": 2.5}
            ))
        if not sped_train:
            fixed.append(Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id=train_to_speed,
                parameters={"speed_factor": 1.10}
            ))
        
        return fixed
    
    @staticmethod
    def _fix_capacity_actions(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        PREVENT capacity overload or weather-related incidents.
        
        Detection agent predicts track segment will exceed safe capacity
        or weather conditions will make normal speed unsafe.
        Prevention: Reduce speed BEFORE entering stressed segment.
        - Slowdown = more time between trains on segment
        - Reroute = remove train from segment entirely
        """
        fixed = []
        trains_handled = set()
        
        for res in resolutions:
            train_id = res.target_train_id
            
            if res.action_type == ActionType.SPEED_ADJUST:
                speed = res.parameters.get("speed_factor", 1.0)
                if speed > 0.95:  # Any speed >= 0.95 should become slowdown
                    fixed.append(Resolution(
                        action_type=ActionType.SPEED_ADJUST,
                        target_train_id=train_id,
                        parameters={"speed_factor": 0.88}  # Slow down 12%
                    ))
                else:
                    fixed.append(res)  # Already slowing down
                trains_handled.add(train_id)
                
            elif res.action_type == ActionType.REROUTE:
                # Reroute is good - takes train off stressed track
                fixed.append(res)
                trains_handled.add(train_id)
                
            elif res.action_type == ActionType.HOLD:
                # Hold is acceptable - wait for conditions to improve
                fixed.append(res)
                trains_handled.add(train_id)
                
            elif res.action_type == ActionType.PLATFORM_CHANGE:
                # Platform change doesn't help with weather stress!
                # Convert to slowdown instead
                fixed.append(Resolution(
                    action_type=ActionType.SPEED_ADJUST,
                    target_train_id=train_id,
                    parameters={"speed_factor": 0.88}
                ))
                trains_handled.add(train_id)
            else:
                fixed.append(res)
                trains_handled.add(train_id)
        
        # Ensure all trains have slowdown action
        for train_id in conflict.train_ids:
            if train_id not in trains_handled:
                fixed.append(Resolution(
                    action_type=ActionType.SPEED_ADJUST,
                    target_train_id=train_id,
                    parameters={"speed_factor": 0.88}
                ))
        
        return fixed
    
    @staticmethod
    def _fix_collision_risk_actions(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        PREVENT track/collision/route_conflict before they occur.
        
        SAFETY CRITICAL: Detection agent has PREDICTED a potential collision.
        Resolution must PREVENT it by ensuring trains never occupy same space.
        
        Strategy: Act early to create separation:
        - Reroute lower-priority train to different path (best: no conflict at all)
        - Hold lower-priority train until path is clear (delays but prevents)
        - Slow both trains to create timing gap at conflict point
        """
        if len(conflict.train_ids) < 2:
            # Single train - just slow down for safety
            return [Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id=conflict.train_ids[0],
                parameters={"speed_factor": 0.85}  # Significant slowdown
            )]
        
        # Check if we already have a safe separation
        has_hold = any(r.action_type == ActionType.HOLD for r in resolutions)
        has_reroute = any(r.action_type == ActionType.REROUTE for r in resolutions)
        has_cancel = any(r.action_type == ActionType.CANCEL for r in resolutions)
        
        if has_hold or has_reroute or has_cancel:
            # Already safe - ensure no train is speeding up
            fixed = []
            for res in resolutions:
                if res.action_type == ActionType.SPEED_ADJUST:
                    speed = res.parameters.get("speed_factor", 1.0)
                    if speed > 1.0:
                        # No speedup allowed in collision risk!
                        fixed.append(Resolution(
                            action_type=ActionType.SPEED_ADJUST,
                            target_train_id=res.target_train_id,
                            parameters={"speed_factor": 0.90}
                        ))
                    else:
                        fixed.append(res)
                else:
                    fixed.append(res)
            return fixed
        
        # NO PREVENTION ACTION - must add one!
        # Determine which train to divert based on priority
        train_priorities = {}
        for tid in conflict.train_ids:
            # High-speed trains have priority over regional
            if "FR_" in tid or "AV_" in tid:
                train_priorities[tid] = 3  # High-speed
            elif "IC_" in tid:
                train_priorities[tid] = 2  # Intercity
            else:
                train_priorities[tid] = 1  # Regional
        
        # Sort by priority (lowest priority train should be diverted)
        sorted_trains = sorted(conflict.train_ids, key=lambda t: train_priorities.get(t, 1))
        train_to_divert = sorted_trains[0]  # Lowest priority diverts
        train_priority = sorted_trains[-1] if len(sorted_trains) > 1 else None
        
        fixed = []
        diverted = False
        
        for res in resolutions:
            if res.target_train_id == train_to_divert and not diverted:
                # PREVENTION: Reroute is preferred (completely avoids conflict)
                # Hold is fallback (delays but ensures safety)
                if res.action_type == ActionType.REROUTE:
                    fixed.append(res)  # Keep reroute - best prevention
                else:
                    # Try reroute first, fall back to hold
                    fixed.append(Resolution(
                        action_type=ActionType.REROUTE,
                        target_train_id=train_to_divert,
                        parameters={"alternate_route": 1}  # Use alternate path
                    ))
                diverted = True
            elif res.target_train_id == train_priority:
                # Priority train: slight slowdown creates timing buffer
                if res.action_type == ActionType.SPEED_ADJUST:
                    speed = res.parameters.get("speed_factor", 1.0)
                    if speed > 0.95:
                        fixed.append(Resolution(
                            action_type=ActionType.SPEED_ADJUST,
                            target_train_id=train_priority,
                            parameters={"speed_factor": 0.95}  # Gentle slowdown
                        ))
                    else:
                        fixed.append(res)
                else:
                    fixed.append(res)
            # Skip other actions for train_to_divert
        
        # Ensure prevention action exists
        if not diverted:
            fixed.append(Resolution(
                action_type=ActionType.REROUTE,
                target_train_id=train_to_divert,
                parameters={"alternate_route": 1}
            ))
        
        # Ensure priority train has timing buffer
        if train_priority and not any(r.target_train_id == train_priority for r in fixed):
            fixed.append(Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id=train_priority,
                parameters={"speed_factor": 0.95}
            ))
        
        return fixed
    
    @staticmethod
    def _fix_platform_actions(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        PREVENT platform double-booking before arrival.
        
        Detection agent predicts two trains scheduled for same platform
        at overlapping times. Prevention:
        - Reassign one train to different platform BEFORE arrival
        - Adjust timing so first train departs before second arrives
        """
        if len(conflict.train_ids) < 2:
            return resolutions
        
        # Check if we have a safe resolution
        has_platform_change = any(r.action_type == ActionType.PLATFORM_CHANGE for r in resolutions)
        has_hold = any(r.action_type == ActionType.HOLD for r in resolutions)
        has_reroute = any(r.action_type == ActionType.REROUTE for r in resolutions)
        
        if has_platform_change or has_hold or has_reroute:
            return resolutions  # Already have separation
        
        # No separation - add platform change for second train
        train_to_change = conflict.train_ids[1] if len(conflict.train_ids) > 1 else conflict.train_ids[0]
        
        fixed = list(resolutions)
        fixed.append(Resolution(
            action_type=ActionType.PLATFORM_CHANGE,
            target_train_id=train_to_change,
            parameters={"new_platform": 2}  # Move to alternate platform
        ))
        
        return fixed
    
    @staticmethod
    def _fix_signal_actions(
        resolutions: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """
        PREVENT trains from entering section with signal/interlocking issue.
        
        Detection agent predicts signal conflict or interlocking problem.
        Prevention: Hold ALL approaching trains BEFORE they reach the
        affected section. This is the safest approach - wait for
        signal system to be verified clear.
        """
        fixed = []
        trains_held = set()
        
        for res in resolutions:
            if res.action_type == ActionType.HOLD:
                fixed.append(res)
                trains_held.add(res.target_train_id)
            # Ignore all other actions - signals require stops
        
        # Ensure ALL trains are held
        for train_id in conflict.train_ids:
            if train_id not in trains_held:
                fixed.append(Resolution(
                    action_type=ActionType.HOLD,
                    target_train_id=train_id,
                    parameters={"hold_minutes": 3.0}  # Wait for signal clearance
                ))
        
        return fixed
    
    @staticmethod
    def _create_default_action(conflict: Conflict) -> List[Resolution]:
        """Create default action when none exist."""
        train_id = conflict.train_ids[0]
        delay = conflict.delay_values.get(train_id, 0)
        
        if conflict.conflict_type == "headway":
            return [Resolution(
                action_type=ActionType.HOLD,
                target_train_id=train_id,
                parameters={"hold_minutes": 2.5}
            )]
        elif conflict.conflict_type == "capacity":
            return [Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id=train_id,
                parameters={"speed_factor": 0.88}
            )]
        else:
            return [Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id=train_id,
                parameters={"speed_factor": 1.08 if delay > 2 else 1.0}
            )]
    
    @staticmethod
    def _validate_single(res: Resolution, conflict: Conflict) -> Optional[Resolution]:
        """Validate a single resolution action."""
        action_type = res.action_type
        params = dict(res.parameters)
        
        # Speed adjustment validation
        if action_type == ActionType.SPEED_ADJUST:
            speed = params.get("speed_factor", 1.0)
            # Cap at realistic bounds: 88%-112%
            speed = max(0.88, min(1.12, speed))
            params["speed_factor"] = speed
        
        # Hold validation
        elif action_type == ActionType.HOLD:
            hold_time = params.get("hold_minutes", 2.0)
            # Cap hold time at reasonable bounds
            hold_time = max(0.5, min(10, hold_time))
            params["hold_minutes"] = hold_time
        
        # Reroute validation
        elif action_type == ActionType.REROUTE:
            alt_route = params.get("alternate_route", 1)
            # Ensure valid alternate route index
            alt_route = max(1, min(3, int(alt_route)))
            params["alternate_route"] = alt_route
            
            # Remove invalid time_delta if present (old format)
            params.pop("time_delta", None)
        
        # Platform change validation
        elif action_type == ActionType.PLATFORM_CHANGE:
            platform = params.get("new_platform", 1)
            platform = max(1, min(15, int(platform)))
            params["new_platform"] = platform
        
        return Resolution(
            action_type=action_type,
            target_train_id=res.target_train_id,
            parameters=params
        )
    
    @staticmethod
    def format_action_explanation(res: Resolution, conflict: Conflict) -> str:
        """Generate human-readable explanation of a PREVENTIVE action."""
        train_id = res.target_train_id
        action = res.action_type
        params = res.parameters
        ctype = conflict.conflict_type
        
        # Context-aware explanations based on conflict type
        if action == ActionType.HOLD:
            mins = params.get('hold_minutes', 0)
            if ctype in ("collision", "track", "route_conflict"):
                return f"Hold {train_id} for {mins:.1f}min to prevent path intersection"
            elif ctype == "headway":
                return f"Hold {train_id} for {mins:.1f}min to create safe gap"
            elif ctype == "signal":
                return f"Hold {train_id} for {mins:.1f}min until signal clears"
            else:
                return f"Hold {train_id} for {mins:.1f}min to prevent conflict"
                
        elif action == ActionType.SPEED_ADJUST:
            factor = params.get('speed_factor', 1.0)
            if factor > 1.0:
                pct = (factor - 1.0) * 100
                if ctype == "delay":
                    return f"Speed up {train_id} by {pct:.0f}% to recover schedule"
                elif ctype == "headway":
                    return f"Speed up {train_id} by {pct:.0f}% to increase gap ahead"
                else:
                    return f"Speed up {train_id} by {pct:.0f}%"
            elif factor < 1.0:
                pct = (1.0 - factor) * 100
                if ctype == "capacity":
                    return f"Slow {train_id} by {pct:.0f}% before entering stressed segment"
                elif ctype == "headway":
                    return f"Slow {train_id} by {pct:.0f}% to let leading train pull away"
                elif ctype in ("collision", "track", "route_conflict"):
                    return f"Slow {train_id} by {pct:.0f}% to create timing buffer"
                else:
                    return f"Slow {train_id} by {pct:.0f}% for safety"
            else:
                return f"Maintain speed for {train_id}"
                
        elif action == ActionType.REROUTE:
            alt = params.get('alternate_route', 1)
            if ctype in ("collision", "track", "route_conflict"):
                return f"Divert {train_id} to path {alt} to avoid conflict point"
            elif ctype == "capacity":
                return f"Reroute {train_id} to path {alt} (less congested)"
            else:
                return f"Reroute {train_id} to alternate path {alt}"
                
        elif action == ActionType.PLATFORM_CHANGE:
            plat = params.get('new_platform', 1)
            return f"Reassign {train_id} to platform {plat} before arrival"
            
        elif action == ActionType.CANCEL:
            return f"Cancel {train_id} (last resort - prevents cascade)"
            
        return f"{action.value} on {train_id}"


# =============================================================================
# MULTI-OBJECTIVE FITNESS FUNCTION
# =============================================================================

@dataclass
class FitnessWeights:
    """Context-dependent weights for fitness objectives."""
    delay_weight: float = 0.5       # Increased: prioritize delay reduction
    passenger_weight: float = 0.3   # Reduced
    propagation_weight: float = 0.1 # Reduced
    smoothness_weight: float = 0.1
    
    @classmethod
    def from_context(cls, context: Context) -> 'FitnessWeights':
        """Adjust weights based on operational context."""
        if context.is_peak_hour:
            # Peak: still prioritize delay but consider passengers
            return cls(
                delay_weight=0.45,
                passenger_weight=0.35,
                propagation_weight=0.1,
                smoothness_weight=0.1
            )
        elif context.weather_condition in ("snow", "fog"):
            # Bad weather: prioritize safety (smoothness) and delay
            return cls(
                delay_weight=0.4,
                passenger_weight=0.2,
                propagation_weight=0.15,
                smoothness_weight=0.25
            )
        else:
            return cls()  # defaults


class FitnessEvaluator:
    """
    Multi-objective fitness evaluation.
    
    Objectives:
    1. Total delay minimization
    2. Passenger impact minimization
    3. Propagation depth minimization
    4. Recovery smoothness maximization
    """
    
    def __init__(self, delay_model: DelayPropagation):
        self.delay_model = delay_model
    
    def evaluate(
        self,
        conflict: Conflict,
        resolutions: List[Resolution],
        context: Context,
        adjacency: Dict[str, List[str]],
        passenger_counts: Optional[Dict[str, int]] = None
    ) -> ResolutionPlan:
        """Evaluate a resolution plan and compute fitness."""
        
        # CRITICAL: Validate and fix all resolutions before evaluation
        # This ensures all solvers produce logically consistent actions
        resolutions = ActionValidator.validate_and_fix(resolutions, conflict)
        
        # CRITICAL: Penalize empty solutions (must do something)
        if not resolutions:
            return ResolutionPlan(
                actions=[],
                total_delay=sum(conflict.delay_values.values()),
                passenger_impact=sum(conflict.delay_values.values()) * 300,
                propagation_depth=0,
                recovery_smoothness=0.0,
                overall_fitness=0.0,  # Empty solution always gets 0 fitness
                solver_used=""
            )
        
        # Propagate delays
        final_delays = self.delay_model.propagate_network(
            conflict, resolutions, context, adjacency
        )
        
        # 1. Total delay
        total_delay = sum(final_delays.values())
        
        # 2. Passenger impact
        if passenger_counts:
            passenger_impact = sum(
                final_delays.get(tid, 0) * passenger_counts.get(tid, 100)
                for tid in conflict.train_ids
            )
        else:
            # Estimate: 300 passengers per train (higher to penalize cancel)
            passenger_impact = total_delay * 300

        # Penalty for cancellations (cancelling a train zeroes delay but hurts passengers)
        cancel_penalty_per_train = 12000  # passenger-min penalty per canceled train
        num_cancels = sum(1 for r in resolutions if r.action_type == ActionType.CANCEL)
        passenger_impact += num_cancels * cancel_penalty_per_train

        # Penalty for reroutes (missed connections, confusion)
        reroute_penalty_per_train = 2000
        num_reroutes = sum(1 for r in resolutions if r.action_type == ActionType.REROUTE)
        passenger_impact += num_reroutes * reroute_penalty_per_train
        
        # 3. Propagation depth (for reporting only - not used in fitness)
        # Count how many trains still have significant delays (>3 min) after resolution
        propagation_depth = sum(1 for delay in final_delays.values() if delay > 3.0)
        
        # 4. Recovery smoothness (variance of delays - lower is smoother)
        delays_list = list(final_delays.values())
        if len(delays_list) > 1:
            variance = np.var(delays_list)
            recovery_smoothness = 1.0 / (1.0 + variance)  # higher is better
        else:
            recovery_smoothness = 1.0
        
        # Compute weighted fitness
        weights = FitnessWeights.from_context(context)
        
        # Normalize components with SHARP penalty for delays
        # Use initial delay as baseline - reward reduction, penalize increase
        initial_total = sum(conflict.delay_values.values())
        
        # Very aggressive delay score: linear with bonus for reduction
        # 0% delay = 1.0, 100% of initial = 0.5, 150% = 0.25
        if initial_total > 0:
            delay_ratio = total_delay / initial_total
            # Linear scale with steep penalty: every 1% reduction = 0.5% fitness gain
            delay_score = max(0, 1.0 - (delay_ratio * 0.5))
            # Bonus: if delay is reduced below initial, add extra reward
            if delay_ratio < 1.0:
                reduction_bonus = (1.0 - delay_ratio) * 0.3  # up to 30% bonus for full elimination
                delay_score = min(1.0, delay_score + reduction_bonus)
        else:
            delay_score = 1.0
        
        # Passenger impact normalization (softer)
        norm_passenger = passenger_impact / max(1, passenger_impact + 10000)
        
        overall_fitness = (
            (weights.delay_weight + weights.propagation_weight * 0.5) * delay_score +
            (weights.passenger_weight + weights.propagation_weight * 0.5) * (1 - norm_passenger) +
            weights.smoothness_weight * recovery_smoothness
        )
        
        return ResolutionPlan(
            actions=resolutions,
            total_delay=total_delay,
            passenger_impact=passenger_impact,
            propagation_depth=propagation_depth,
            recovery_smoothness=recovery_smoothness,
            overall_fitness=overall_fitness,
            solver_used=""
        )
    
    @staticmethod
    def pareto_dominates(plan_a: ResolutionPlan, plan_b: ResolutionPlan) -> bool:
        """Check if plan_a Pareto-dominates plan_b (a is better in all objectives)."""
        dominated = (
            plan_a.total_delay <= plan_b.total_delay and
            plan_a.passenger_impact <= plan_b.passenger_impact and
            plan_a.propagation_depth <= plan_b.propagation_depth and
            plan_a.recovery_smoothness >= plan_b.recovery_smoothness
        )
        strictly_better = (
            plan_a.total_delay < plan_b.total_delay or
            plan_a.passenger_impact < plan_b.passenger_impact or
            plan_a.propagation_depth < plan_b.propagation_depth or
            plan_a.recovery_smoothness > plan_b.recovery_smoothness
        )
        return dominated and strictly_better


# =============================================================================
# CONFLICT-TYPE-AWARE ACTION GENERATION
# =============================================================================

class ConflictAwareActionGenerator:
    """
    Generates appropriate actions based on conflict type.
    Ensures logical actions are chosen for each situation.
    """
    
    # Action weights per conflict type (higher = more likely to be chosen)
    ACTION_WEIGHTS = {
        "headway": {
            # Headway violation: trains too close together
            # Solution: HOLD trailing train OR slow it down
            ActionType.HOLD: 0.5,          # Hold trailing train to increase gap
            ActionType.SPEED_ADJUST: 0.35, # Slow down trailing train
            ActionType.REROUTE: 0.1,       # Last resort: reroute one train
            ActionType.PLATFORM_CHANGE: 0.05,
        },
        "delay": {
            # Delay propagation risk: train running late
            # Solution: Speed up if possible, or accept delay
            ActionType.SPEED_ADJUST: 0.6,  # Try to catch up
            ActionType.HOLD: 0.15,         # Hold at station to let others pass
            ActionType.REROUTE: 0.15,      # Take faster alternate route
            ActionType.PLATFORM_CHANGE: 0.1,
        },
        "capacity": {
            # Capacity/weather stress: track at risk
            # Solution: Slow down for safety, reroute to alternate track
            ActionType.SPEED_ADJUST: 0.45, # Slow down for safety
            ActionType.REROUTE: 0.35,      # Use less congested track
            ActionType.HOLD: 0.15,         # Wait for conditions to improve
            ActionType.PLATFORM_CHANGE: 0.05,
        },
        "platform": {
            # Platform conflict: multiple trains need same platform
            # Solution: Platform change, hold one train
            ActionType.PLATFORM_CHANGE: 0.45,
            ActionType.HOLD: 0.35,
            ActionType.REROUTE: 0.15,
            ActionType.SPEED_ADJUST: 0.05,
        },
        "track": {
            # Track occupation conflict
            # Solution: Reroute or hold
            ActionType.REROUTE: 0.4,
            ActionType.HOLD: 0.35,
            ActionType.SPEED_ADJUST: 0.15,
            ActionType.PLATFORM_CHANGE: 0.1,
        },
        "collision": {
            # SAFETY CRITICAL: Potential collision on same track segment
            # Solution: MUST stop one train or reroute
            ActionType.HOLD: 0.5,          # Stop lower priority train
            ActionType.REROUTE: 0.35,      # Reroute to different track
            ActionType.CANCEL: 0.1,        # Cancel as last resort
            ActionType.SPEED_ADJUST: 0.05, # Slow down (not sufficient alone!)
        },
        "route_conflict": {
            # Route/switch conflict: conflicting routes through junction
            # Solution: Hold one, reroute, or modify timing
            ActionType.HOLD: 0.45,
            ActionType.REROUTE: 0.35,
            ActionType.SPEED_ADJUST: 0.15,
            ActionType.PLATFORM_CHANGE: 0.05,
        },
        "signal": {
            # Signal/interlocking failure
            # Solution: ALL trains must stop
            ActionType.HOLD: 0.9,          # Must stop
            ActionType.SPEED_ADJUST: 0.1,  # Slow approach only
        },
    }
    
    # Default weights for unknown conflict types - SAFETY FIRST
    DEFAULT_WEIGHTS = {
        ActionType.HOLD: 0.35,          # When unsure, stop is safest
        ActionType.SPEED_ADJUST: 0.25,
        ActionType.REROUTE: 0.25,
        ActionType.PLATFORM_CHANGE: 0.15,
    }
    
    @classmethod
    def get_action_weights(cls, conflict_type: str) -> Dict[ActionType, float]:
        """Get action probability weights for a conflict type."""
        return cls.ACTION_WEIGHTS.get(conflict_type, cls.DEFAULT_WEIGHTS)
    
    @classmethod
    def choose_action(cls, conflict_type: str) -> ActionType:
        """Randomly choose an action weighted by conflict type."""
        weights = cls.get_action_weights(conflict_type)
        actions = list(weights.keys())
        probs = list(weights.values())
        return random.choices(actions, weights=probs)[0]
    
    @classmethod
    def get_best_action_for_train(
        cls,
        conflict_type: str,
        train_id: str,
        delay: float,
        is_trailing: bool = False,
        is_priority: bool = False
    ) -> Tuple[ActionType, Dict]:
        """
        Get the best action for a specific train based on context.
        
        Args:
            conflict_type: Type of conflict
            train_id: Train identifier
            delay: Current delay in minutes
            is_trailing: True if this is the trailing train in a headway conflict
            is_priority: True if this is a high-priority train (high_speed, intercity)
        
        Returns:
            Tuple of (action_type, parameters)
        """
        if conflict_type == "headway":
            if is_trailing:
                # Trailing train should hold or slow down
                if delay < 3:
                    # Low delay: can afford to hold
                    return ActionType.HOLD, {"hold_minutes": random.uniform(2, 4)}
                else:
                    # Higher delay: slow down slightly instead
                    return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(0.90, 0.95)}
            else:
                # Leading train: try to speed up if delayed, or maintain
                if delay > 2:
                    return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(1.05, 1.10)}
                else:
                    return ActionType.SPEED_ADJUST, {"speed_factor": 1.0}  # Maintain
        
        elif conflict_type == "delay":
            if is_priority and delay > 5:
                # Priority train with significant delay: speed up
                return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(1.08, 1.12)}
            elif delay > 8:
                # Large delay: consider reroute to faster path
                return ActionType.REROUTE, {"alternate_route": 1}
            else:
                # Moderate delay: gentle speedup
                return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(1.03, 1.08)}
        
        elif conflict_type == "capacity":
            # Safety first: slow down or reroute
            if delay > 5:
                return ActionType.REROUTE, {"alternate_route": 1}
            else:
                return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(0.85, 0.92)}
        
        elif conflict_type == "platform":
            if is_priority:
                # Priority train keeps platform, others change
                return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(1.02, 1.08)}
            else:
                return ActionType.PLATFORM_CHANGE, {"new_platform": random.randint(1, 8)}
        
        elif conflict_type in ("track", "collision", "route_conflict"):
            # SAFETY CRITICAL: Must separate trains
            if is_priority:
                # Priority train slows down but continues
                return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(0.85, 0.92)}
            else:
                # Non-priority train MUST stop
                return ActionType.HOLD, {"hold_minutes": random.uniform(4, 6)}
        
        elif conflict_type == "signal":
            # SAFETY CRITICAL: ALL trains must stop on signal failure
            return ActionType.HOLD, {"hold_minutes": random.uniform(3, 5)}
        
        else:
            # Default: SAFETY FIRST - hold when uncertain
            if delay > 6:
                return ActionType.SPEED_ADJUST, {"speed_factor": random.uniform(1.05, 1.10)}
            elif delay > 3:
                return ActionType.HOLD, {"hold_minutes": random.uniform(1.5, 3)}
            else:
                return ActionType.HOLD, {"hold_minutes": random.uniform(1, 2)}


# =============================================================================
# OPTIMIZATION ALGORITHMS
# =============================================================================

class GreedySolver:
    """Greedy baseline solver - conflict-type-aware."""
    
    def __init__(self, evaluator: FitnessEvaluator):
        self.evaluator = evaluator
    
    def solve(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]]
    ) -> ResolutionPlan:
        """Generate conflict-aware greedy resolution."""
        resolutions = []
        
        # Determine priority trains
        priority_trains = set(conflict.priority_trains or [])
        
        # Sort trains by delay (highest first)
        sorted_trains = sorted(
            conflict.delay_values.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # For headway conflicts, identify trailing train(s)
        # (trailing = second train that entered too soon)
        trailing_trains = set()
        if conflict.conflict_type == "headway" and len(sorted_trains) >= 2:
            # Assume lower-delay train is trailing (entered later but too close)
            trailing_trains.add(sorted_trains[-1][0])
        
        for train_id, delay in sorted_trains:
            is_trailing = train_id in trailing_trains
            is_priority = train_id in priority_trains
            
            # Use conflict-aware action selection
            action_type, params = ConflictAwareActionGenerator.get_best_action_for_train(
                conflict_type=conflict.conflict_type,
                train_id=train_id,
                delay=delay,
                is_trailing=is_trailing,
                is_priority=is_priority
            )
            
            # Skip if action wouldn't help (e.g., maintain speed for low delay)
            if action_type == ActionType.SPEED_ADJUST and abs(params.get("speed_factor", 1.0) - 1.0) < 0.02:
                continue
            
            resolutions.append(Resolution(
                action_type=action_type,
                target_train_id=train_id,
                parameters=params
            ))
        
        # Ensure at least one action
        if not resolutions and sorted_trains:
            train_id, delay = sorted_trains[0]
            resolutions.append(Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id=train_id,
                parameters={"speed_factor": 1.05}
            ))
        
        plan = self.evaluator.evaluate(conflict, resolutions, context, adjacency)
        plan.solver_used = "greedy"
        return plan

from .qubo_builder import QUBOBuilder
from .quantum_solver import SimulatedQuantumQUBOSolver

class LargeNeighborhoodSearch:
    """
    Large Neighborhood Search (LNS) solver.
    Iteratively destroys and repairs parts of the solution.
    """
    
    # def __init__(
    #     self,
    #     evaluator: FitnessEvaluator,
    #     max_iterations: int = 100,
    #     destroy_fraction: float = 0.3
    # ):
    #     self.evaluator = evaluator
    #     self.max_iterations = max_iterations
    #     self.destroy_fraction = destroy_fraction
    def __init__(
        self,
        evaluator: FitnessEvaluator,
        max_iterations: int = 100,
        destroy_fraction: float = 0.3,
        enable_quantum: bool = False,
        quantum_min_trains: int = 4,
    ):
        self.evaluator = evaluator
        self.max_iterations = max_iterations
        self.destroy_fraction = destroy_fraction

        self.enable_quantum = enable_quantum
        self.quantum_min_trains = quantum_min_trains

        if enable_quantum:
            self.qubo_builder = QUBOBuilder()
            self.quantum_solver = SimulatedQuantumQUBOSolver()

    def _should_use_quantum(self, destroyed_trains: list) -> bool:
        if not self.enable_quantum:
            return False
        return len(destroyed_trains) >= self.quantum_min_trains

    
    def solve(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]],
        initial_solution: Optional[List[Resolution]] = None
    ) -> ResolutionPlan:
        """Run LNS optimization."""
        
        # Initialize with greedy if no initial solution
        if initial_solution is None:
            greedy = GreedySolver(self.evaluator)
            current_plan = greedy.solve(conflict, context, adjacency)
            current_solution = current_plan.actions
        else:
            current_solution = initial_solution
            current_plan = self.evaluator.evaluate(
                conflict, current_solution, context, adjacency
            )
        
        best_plan = current_plan
        
        for _ in range(self.max_iterations):
            # Destroy: remove fraction of actions
            num_destroy = max(1, int(len(current_solution) * self.destroy_fraction))
            destroyed = list(current_solution)
            
            for _ in range(num_destroy):
                if destroyed:
                    idx = random.randint(0, len(destroyed) - 1)
                    destroyed.pop(idx)
            
            # Repair: add new random actions
            # repaired = list(destroyed)
            # available_trains = [
            #     tid for tid in conflict.train_ids
            #     if not any(r.target_train_id == tid for r in repaired)
            # ]
            
            # for _ in range(num_destroy):
            #     if available_trains:
            #         train_id = random.choice(available_trains)
            #         available_trains.remove(train_id)
                    
            #         action_type = random.choice([
            #             ActionType.HOLD,
            #             ActionType.REROUTE,
            #             ActionType.SPEED_ADJUST,
            #             ActionType.PLATFORM_CHANGE,
            #         ])
            #         params = self._generate_params(action_type)
                    
            #         repaired.append(Resolution(
            #             action_type=action_type,
            #             target_train_id=train_id,
            #             parameters=params
            #         ))
            
            # ------------------------------------
            # Repair step (quantum OR classical)
            # ------------------------------------

            repaired = list(destroyed)

            destroyed_trains = [
                tid for tid in conflict.train_ids
                if not any(r.target_train_id == tid for r in repaired)
            ]

            if self._should_use_quantum(destroyed_trains):
                try:
                    # Candidate actions per train
                    candidate_actions = {
                        tid: ["HOLD", "REROUTE", "SPEED_ADJUST", "PLATFORM_CHANGE"]
                        for tid in destroyed_trains
                    }

                    Q, index_to_var = self.qubo_builder.build(
                        destroyed_trains=destroyed_trains,
                        conflict=conflict,
                        context=context,
                        adjacency=adjacency,
                        candidate_actions=candidate_actions,
                    )

                    bits = self.quantum_solver.solve(Q, num_vars=len(index_to_var))

                    added = 0
                    for idx, bit in bits.items():
                        if bit == 1:
                            train_id, action_str = index_to_var[idx]
                            action_type = ActionType[action_str]

                            repaired.append(
                                Resolution(
                                    action_type=action_type,
                                    target_train_id=train_id,
                                    parameters=self._generate_params(action_type),
                                )
                            )
                            added += 1

                    # If quantum picked nothing, fall back to classical repair
                    if added == 0:
                        repaired = self._classical_repair(
                            repaired, conflict, num_destroy
                        )

                except Exception:
                    # Quantum failed → fall back to classical repair
                    repaired = self._classical_repair(
                        repaired, conflict, num_destroy
                    )

            else:
                repaired = self._classical_repair(
                    repaired, conflict, num_destroy
                )

            # Evaluate new solution
            new_plan = self.evaluator.evaluate(conflict, repaired, context, adjacency)
            
            # Accept if better
            if new_plan.overall_fitness > current_plan.overall_fitness:
                current_solution = repaired
                current_plan = new_plan
                
                if new_plan.overall_fitness > best_plan.overall_fitness:
                    best_plan = new_plan
        
        best_plan.solver_used = "lns"
        return best_plan
    
    
    def _classical_repair(
        self,
        repaired: List[Resolution],
        conflict: Conflict,
        num_destroy: int
    ) -> List[Resolution]:
        """
        Conflict-aware LNS repair logic.
        Uses conflict type to select appropriate actions.
        """

        repaired = list(repaired)

        available_trains = [
            tid for tid in conflict.train_ids
            if not any(r.target_train_id == tid for r in repaired)
        ]

        for _ in range(num_destroy):
            if not available_trains:
                break

            train_id = random.choice(available_trains)
            available_trains.remove(train_id)

            # Use conflict-aware action selection
            delay = conflict.delay_values.get(train_id, 0)
            is_priority = train_id in (conflict.priority_trains or [])
            
            action_type, params = ConflictAwareActionGenerator.get_best_action_for_train(
                conflict_type=conflict.conflict_type,
                train_id=train_id,
                delay=delay,
                is_trailing=False,
                is_priority=is_priority
            )

            repaired.append(
                Resolution(
                    action_type=action_type,
                    target_train_id=train_id,
                    parameters=params,
                )
            )

        return repaired





    def _generate_params(self, action_type: ActionType) -> Dict:
        if action_type == ActionType.HOLD:
            return {"hold_minutes": random.uniform(1, 5)}
        elif action_type == ActionType.SPEED_ADJUST:
            # Realistic speed adjustment: trains can only go 10% faster or 10% slower
            return {"speed_factor": random.uniform(0.90, 1.12)}
        elif action_type == ActionType.REROUTE:
            # Reroute to alternate path (index 0=primary, 1+=alternates)
            return {"alternate_route": random.randint(1, 3)}
        elif action_type == ActionType.PLATFORM_CHANGE:
            return {"new_platform": random.randint(1, 10)}
        else:
            return {}


class SimulatedAnnealing:
    """
    Simulated Annealing solver.
    Explores solution space with temperature-based acceptance.
    """
    
    def __init__(
        self,
        evaluator: FitnessEvaluator,
        initial_temp: float = 100.0,
        cooling_rate: float = 0.995,
        min_temp: float = 0.1
    ):
        self.evaluator = evaluator
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.min_temp = min_temp
    
    def solve(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]]
    ) -> ResolutionPlan:
        """Run simulated annealing optimization."""
        
        # Initialize with greedy
        greedy = GreedySolver(self.evaluator)
        current_plan = greedy.solve(conflict, context, adjacency)
        current_solution = list(current_plan.actions)
        
        best_plan = current_plan
        temperature = self.initial_temp
        
        while temperature > self.min_temp:
            # Generate neighbor
            neighbor = self._mutate(current_solution, conflict)
            neighbor_plan = self.evaluator.evaluate(
                conflict, neighbor, context, adjacency
            )
            
            # Calculate acceptance probability
            delta = neighbor_plan.overall_fitness - current_plan.overall_fitness
            
            if delta > 0:
                # Better solution: always accept
                current_solution = neighbor
                current_plan = neighbor_plan
            else:
                # Worse solution: accept with probability
                prob = math.exp(delta / temperature)
                if random.random() < prob:
                    current_solution = neighbor
                    current_plan = neighbor_plan
            
            # Update best
            if current_plan.overall_fitness > best_plan.overall_fitness:
                best_plan = current_plan
            
            # Cool down
            temperature *= self.cooling_rate
        
        best_plan.solver_used = "simulated_annealing"
        return best_plan
    
    def _mutate(
        self,
        solution: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """Mutate solution by modifying one action (but keep at least 1)."""
        if not solution:
            return solution
        
        mutated = list(solution)
        # Bias: 40% modify, 20% swap, 30% add, 10% remove (keep solutions populated)
        rand = random.random()
        
        if rand < 0.4 and mutated:
            # Modify: change parameters of existing action
            idx = random.randint(0, len(mutated) - 1)
            old = mutated[idx]
            new_type = random.choice([
                ActionType.HOLD,
                ActionType.REROUTE,
                ActionType.SPEED_ADJUST,
                ActionType.PLATFORM_CHANGE,
            ])
            mutated[idx] = Resolution(
                action_type=new_type,
                target_train_id=old.target_train_id,
                parameters=self._random_params(new_type)
            )
        
        elif rand < 0.6 and len(mutated) >= 2:
            # Swap: shuffle action order
            i, j = random.sample(range(len(mutated)), 2)
            mutated[i], mutated[j] = mutated[j], mutated[i]
        
        elif rand < 0.9:
            # Add: add new action if space available
            available = [
                tid for tid in conflict.train_ids
                if not any(r.target_train_id == tid for r in mutated)
            ]
            if available and len(mutated) < len(conflict.train_ids):
                train_id = random.choice(available)
                action_type = random.choice([
                    ActionType.HOLD,
                    ActionType.REROUTE,
                    ActionType.SPEED_ADJUST,
                    ActionType.PLATFORM_CHANGE,
                ])
                mutated.append(Resolution(
                    action_type=action_type,
                    target_train_id=train_id,
                    parameters=self._random_params(action_type)
                ))
        
        else:
            # Remove: only if more than 1 action (keep at least 1)
            if len(mutated) > 1:
                idx = random.randint(0, len(mutated) - 1)
                mutated.pop(idx)
        
        return mutated
    
    def _random_params(self, action_type: ActionType) -> Dict:
        if action_type == ActionType.HOLD:
            return {"hold_minutes": random.uniform(1, 5)}
        elif action_type == ActionType.SPEED_ADJUST:
            # Realistic: 90%-112% of normal speed
            return {"speed_factor": random.uniform(0.90, 1.12)}
        elif action_type == ActionType.REROUTE:
            return {"alternate_route": random.randint(1, 3)}
        elif action_type == ActionType.PLATFORM_CHANGE:
            return {"new_platform": random.randint(1, 10)}
        return {}


class GeneticAlgorithm:
    """
    Standard single-objective Genetic Algorithm.
    Faster than NSGA-II when only optimizing overall fitness.
    
    Encoding: Each individual is a list of Resolution actions.
    Fitness: Overall fitness score (weighted combination of objectives).
    """
    
    def __init__(
        self,
        evaluator: FitnessEvaluator,
        population_size: int = 50,
        generations: int = 80,
        crossover_rate: float = 0.85,
        mutation_rate: float = 0.15,
        elitism: int = 2  # Top N individuals survive unchanged
    ):
        self.evaluator = evaluator
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elitism = elitism
    
    def solve(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]]
    ) -> ResolutionPlan:
        """Run genetic algorithm optimization."""
        
        # Initialize population
        population = self._initialize_population(conflict)
        
        best_plan = None
        best_fitness = -float('inf')
        
        for gen in range(self.generations):
            # Evaluate fitness for all individuals
            fitness_scores = []
            plans = []
            
            for individual in population:
                plan = self.evaluator.evaluate(conflict, individual, context, adjacency)
                plans.append(plan)
                fitness_scores.append(plan.overall_fitness)
                
                if plan.overall_fitness > best_fitness:
                    best_fitness = plan.overall_fitness
                    best_plan = plan
            
            # Selection: Roulette wheel with fitness scaling
            parents = self._selection(population, fitness_scores)
            
            # Create next generation
            next_population = []
            
            # Elitism: keep top performers
            sorted_indices = np.argsort(fitness_scores)[::-1]
            for i in range(self.elitism):
                next_population.append(population[sorted_indices[i]])
            
            # Fill rest with crossover + mutation
            while len(next_population) < self.population_size:
                parent1, parent2 = random.sample(parents, 2)
                
                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2, conflict)
                else:
                    child1, child2 = list(parent1), list(parent2)
                
                child1 = self._mutate(child1, conflict)
                child2 = self._mutate(child2, conflict)
                
                next_population.append(child1)
                if len(next_population) < self.population_size:
                    next_population.append(child2)
            
            population = next_population
        
        best_plan.solver_used = "genetic_algorithm"
        return best_plan
    
    def _initialize_population(self, conflict: Conflict) -> List[List[Resolution]]:
        """Create diverse initial population with conflict-aware seeding."""
        population = []
        
        # Seed 20% of population with conflict-aware actions
        num_seeded = max(5, self.population_size // 5)
        
        for i in range(self.population_size):
            individual = []
            num_actions = random.randint(1, max(1, len(conflict.train_ids)))
            if not conflict.train_ids:
                population.append([])
                continue
            trains = random.sample(conflict.train_ids, min(num_actions, len(conflict.train_ids)))
            
            # First portion uses conflict-aware action selection
            use_conflict_aware = i < num_seeded
            
            for j, train_id in enumerate(trains):
                delay = conflict.delay_values.get(train_id, 0)
                is_priority = train_id in (conflict.priority_trains or [])
                
                if use_conflict_aware:
                    # Use conflict-type-aware action
                    action_type, params = ConflictAwareActionGenerator.get_best_action_for_train(
                        conflict_type=conflict.conflict_type,
                        train_id=train_id,
                        delay=delay,
                        is_trailing=(j == len(trains) - 1),  # Last train as trailing
                        is_priority=is_priority
                    )
                else:
                    # Random action weighted by conflict type
                    action_type = ConflictAwareActionGenerator.choose_action(conflict.conflict_type)
                    params = self._random_params(action_type)
                
                individual.append(Resolution(
                    action_type=action_type,
                    target_train_id=train_id,
                    parameters=params
                ))
            
            population.append(individual)
        
        return population
    
    def _selection(
        self,
        population: List[List[Resolution]],
        fitness_scores: List[float]
    ) -> List[List[Resolution]]:
        """Roulette wheel selection with fitness scaling."""
        # Scale fitness to avoid negative values
        min_fit = min(fitness_scores)
        scaled = [f - min_fit + 0.01 for f in fitness_scores]
        total = sum(scaled)
        probs = [s / total for s in scaled]
        
        # Select parents
        selected = []
        for _ in range(self.population_size):
            r = random.random()
            cumsum = 0
            for i, p in enumerate(probs):
                cumsum += p
                if r <= cumsum:
                    selected.append(population[i])
                    break
        
        return selected
    
    def _crossover(
        self,
        parent1: List[Resolution],
        parent2: List[Resolution],
        conflict: Conflict
    ) -> Tuple[List[Resolution], List[Resolution]]:
        """Two-point crossover for variable-length individuals."""
        if not parent1 or not parent2:
            return list(parent1) if parent1 else [], list(parent2) if parent2 else []
        
        # Uniform crossover: each action has 50% chance from each parent
        all_trains = set(r.target_train_id for r in parent1 + parent2)
        
        child1, child2 = [], []
        max_actions = len(conflict.train_ids)  # Cap at one action per train
        
        for train_id in all_trains:
            if len(child1) >= max_actions and len(child2) >= max_actions:
                break  # Both children at max size
                
            action1 = next((r for r in parent1 if r.target_train_id == train_id), None)
            action2 = next((r for r in parent2 if r.target_train_id == train_id), None)
            
            if action1 and action2:
                if random.random() < 0.5:
                    if len(child1) < max_actions:
                        child1.append(action1)
                    if len(child2) < max_actions:
                        child2.append(action2)
                else:
                    if len(child1) < max_actions:
                        child1.append(action2)
                    if len(child2) < max_actions:
                        child2.append(action1)
            elif action1:
                if random.random() < 0.5:
                    if len(child1) < max_actions:
                        child1.append(action1)
                else:
                    if len(child2) < max_actions:
                        child2.append(action1)
            elif action2:
                if random.random() < 0.5:
                    if len(child1) < max_actions:
                        child1.append(action2)
                else:
                    if len(child2) < max_actions:
                        child2.append(action2)
        
        return child1, child2
    
    def _mutate(
        self,
        individual: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """Apply mutations with probability."""
        mutated = list(individual)
        
        max_actions = len(conflict.train_ids)  # Max one action per train
        
        for i in range(len(mutated)):
            if random.random() < self.mutation_rate:
                mutation_type = random.choice(["action", "params", "swap"])
                
                if mutation_type == "action":
                    # Change action type (exclude CANCEL)
                    new_type = random.choice([
                        ActionType.HOLD,
                        ActionType.SPEED_ADJUST,
                        ActionType.REROUTE,
                        ActionType.PLATFORM_CHANGE,
                    ])
                    mutated[i] = Resolution(
                        action_type=new_type,
                        target_train_id=mutated[i].target_train_id,
                        parameters=self._random_params(new_type)
                    )
                elif mutation_type == "params":
                    # Mutate parameters
                    mutated[i] = Resolution(
                        action_type=mutated[i].action_type,
                        target_train_id=mutated[i].target_train_id,
                        parameters=self._mutate_params(mutated[i].action_type, mutated[i].parameters)
                    )
        
        # Occasionally add or remove an action (but cap at max_actions)
        if random.random() < self.mutation_rate:
            if random.random() < 0.5 and mutated:
                # Remove random action
                mutated.pop(random.randint(0, len(mutated) - 1))
            elif len(mutated) < max_actions:
                # Add new action only if under limit
                used_trains = {r.target_train_id for r in mutated}
                available = [t for t in conflict.train_ids if t not in used_trains]
                if available:
                    train_id = random.choice(available)
                    action_type = random.choice([
                        ActionType.HOLD,
                        ActionType.SPEED_ADJUST,
                        ActionType.REROUTE,
                        ActionType.PLATFORM_CHANGE,
                    ])
                    mutated.append(Resolution(
                        action_type=action_type,
                        target_train_id=train_id,
                        parameters=self._random_params(action_type)
                    ))
        
        return mutated
    
    def _random_params(self, action_type: ActionType) -> Dict:
        """Generate random parameters for action type."""
        if action_type == ActionType.HOLD:
            return {"hold_minutes": random.uniform(1, 6)}
        elif action_type == ActionType.SPEED_ADJUST:
            # Realistic: trains can adjust speed by max 10-12%
            return {"speed_factor": random.uniform(0.90, 1.12)}
        elif action_type == ActionType.REROUTE:
            # Reroute to alternate path
            return {"alternate_route": random.randint(1, 3)}
        elif action_type == ActionType.PLATFORM_CHANGE:
            return {"new_platform": random.randint(1, 12)}
        elif action_type == ActionType.CANCEL:
            return {"refund_policy": random.choice(["full", "partial", "voucher"])}
        return {}
    
    def _mutate_params(self, action_type: ActionType, params: Dict) -> Dict:
        """Slightly mutate existing parameters."""
        new_params = dict(params)
        
        if action_type == ActionType.HOLD and "hold_minutes" in new_params:
            new_params["hold_minutes"] += random.gauss(0, 1)
            new_params["hold_minutes"] = max(0.5, min(10, new_params["hold_minutes"]))
        elif action_type == ActionType.SPEED_ADJUST and "speed_factor" in new_params:
            new_params["speed_factor"] += random.gauss(0, 0.03)
            # Realistic cap: 90%-112% of normal speed
            new_params["speed_factor"] = max(0.90, min(1.12, new_params["speed_factor"]))
        elif action_type == ActionType.REROUTE and "alternate_route" in new_params:
            # Mutate to different alternate route
            new_params["alternate_route"] = random.randint(1, 3)
        
        return new_params


class NSGAII:
    """
    NSGA-II: Non-dominated Sorting Genetic Algorithm II.
    Multi-objective optimization maintaining Pareto front.
    """
    
    def __init__(
        self,
        evaluator: FitnessEvaluator,
        population_size: int = 50,
        generations: int = 100,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1
    ):
        self.evaluator = evaluator
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
    
    def solve(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]]
    ) -> ResolutionPlan:
        """Run NSGA-II optimization, return best from Pareto front."""
        
        # Initialize population
        population = self._initialize_population(conflict)
        
        for _ in range(self.generations):
            # Evaluate fitness
            evaluated = [
                (ind, self.evaluator.evaluate(conflict, ind, context, adjacency))
                for ind in population
            ]
            
            # Non-dominated sorting
            fronts = self._fast_non_dominated_sort(evaluated)
            
            # Calculate crowding distance
            for front in fronts:
                self._crowding_distance(front)
            
            # Selection
            parents = self._tournament_selection(evaluated, fronts)
            
            # Crossover and mutation
            offspring = []
            for i in range(0, len(parents) - 1, 2):
                child1, child2 = self._crossover(parents[i], parents[i + 1], conflict)
                mutated1 = self._mutate(child1, conflict)
                mutated2 = self._mutate(child2, conflict)
                # Only add non-empty offspring
                if mutated1:
                    offspring.append(mutated1)
                if mutated2:
                    offspring.append(mutated2)
            
            # Combine and select next generation
            combined = population + offspring
            evaluated_combined = [
                (ind, self.evaluator.evaluate(conflict, ind, context, adjacency))
                for ind in combined
            ]
            
            fronts = self._fast_non_dominated_sort(evaluated_combined)
            population = self._select_next_generation(evaluated_combined, fronts)
        
        # Return best from final population
        final_plans = [
            self.evaluator.evaluate(conflict, ind, context, adjacency)
            for ind in population
        ]
        best_plan = max(final_plans, key=lambda p: p.overall_fitness)
        best_plan.solver_used = "nsga2"
        return best_plan
    
    def _initialize_population(self, conflict: Conflict) -> List[List[Resolution]]:
        """Create random initial population."""
        population = []
        
        for _ in range(self.population_size):
            individual = []
            num_actions = random.randint(1, max(1, len(conflict.train_ids)))
            if not conflict.train_ids:
                population.append([])
                continue
            trains = random.sample(conflict.train_ids, min(num_actions, len(conflict.train_ids)))
            
            for train_id in trains:
                action_type = random.choice([
                    ActionType.HOLD,
                    ActionType.REROUTE,
                    ActionType.SPEED_ADJUST,
                    ActionType.PLATFORM_CHANGE,
                ])
                individual.append(Resolution(
                    action_type=action_type,
                    target_train_id=train_id,
                    parameters=self._random_params(action_type)
                ))
            
            population.append(individual)
        
        return population
    
    def _fast_non_dominated_sort(
        self,
        evaluated: List[Tuple[List[Resolution], ResolutionPlan]]
    ) -> List[List[int]]:
        """Sort population into non-dominated fronts."""
        n = len(evaluated)
        domination_count = [0] * n
        dominated_by = [[] for _ in range(n)]
        fronts = [[]]
        
        for i in range(n):
            for j in range(i + 1, n):
                if FitnessEvaluator.pareto_dominates(evaluated[i][1], evaluated[j][1]):
                    dominated_by[i].append(j)
                    domination_count[j] += 1
                elif FitnessEvaluator.pareto_dominates(evaluated[j][1], evaluated[i][1]):
                    dominated_by[j].append(i)
                    domination_count[i] += 1
        
        for i in range(n):
            if domination_count[i] == 0:
                fronts[0].append(i)
        
        current_front = 0
        # Guard against empty fronts to avoid index errors
        while current_front < len(fronts) and fronts[current_front]:
            next_front = []
            for i in fronts[current_front]:
                for j in dominated_by[i]:
                    domination_count[j] -= 1
                    if domination_count[j] == 0:
                        next_front.append(j)
            current_front += 1
            if next_front:
                fronts.append(next_front)
        
        return fronts
    
    def _crowding_distance(self, front: List[int]):
        """Calculate crowding distance (not stored, simplified)."""
        pass  # Simplified - would normally assign distance to each individual
    
    def _tournament_selection(
        self,
        evaluated: List[Tuple[List[Resolution], ResolutionPlan]],
        fronts: List[List[int]]
    ) -> List[List[Resolution]]:
        """Select parents via tournament."""
        front_rank = {}
        for rank, front in enumerate(fronts):
            for idx in front:
                front_rank[idx] = rank
        
        parents = []
        for _ in range(self.population_size):
            i, j = random.sample(range(len(evaluated)), 2)
            winner = i if front_rank.get(i, 999) <= front_rank.get(j, 999) else j
            parents.append(evaluated[winner][0])
        
        return parents
    
    def _crossover(
        self,
        parent1: List[Resolution],
        parent2: List[Resolution],
        conflict: Conflict
    ) -> Tuple[List[Resolution], List[Resolution]]:
        """Single-point crossover with size limiting."""
        if random.random() > self.crossover_rate:
            return parent1, parent2
        
        if not parent1 or not parent2:
            return parent1, parent2
        
        max_size = len(conflict.train_ids)
        # Prevent crossover points at 0 (would create empty child)
        point1 = random.randint(1, len(parent1)) if len(parent1) > 1 else len(parent1)
        point2 = random.randint(1, len(parent2)) if len(parent2) > 1 else len(parent2)
        
        child1 = parent1[:point1] + parent2[point2:]
        child2 = parent2[:point2] + parent1[point1:]
        
        # Trim to max size and deduplicate
        child1 = self._deduplicate_and_trim(child1, max_size)
        child2 = self._deduplicate_and_trim(child2, max_size)
        
        # If either child is empty, return parents instead
        if not child1:
            child1 = parent1
        if not child2:
            child2 = parent2
        
        return child1, child2
    
    def _deduplicate_and_trim(self, individual: List[Resolution], max_size: int) -> List[Resolution]:
        """Remove duplicate train actions and trim to max size."""
        seen_trains = set()
        dedup = []
        for action in individual:
            if action.target_train_id not in seen_trains:
                dedup.append(action)
                seen_trains.add(action.target_train_id)
                if len(dedup) >= max_size:
                    break
        return dedup
    
    def _mutate(
        self,
        individual: List[Resolution],
        conflict: Conflict
    ) -> List[Resolution]:
        """Mutate individual with probability."""
        if random.random() > self.mutation_rate:
            return individual
        
        mutated = list(individual)
        if mutated and random.random() < 0.5:
            idx = random.randint(0, len(mutated) - 1)
            new_type = random.choice([
                ActionType.HOLD,
                ActionType.REROUTE,
                ActionType.SPEED_ADJUST,
                ActionType.PLATFORM_CHANGE,
            ])
            mutated[idx] = Resolution(
                action_type=new_type,
                target_train_id=mutated[idx].target_train_id,
                parameters=self._random_params(new_type)
            )
        return mutated
    
    def _select_next_generation(
        self,
        evaluated: List[Tuple[List[Resolution], ResolutionPlan]],
        fronts: List[List[int]]
    ) -> List[List[Resolution]]:
        """Select next generation maintaining diversity."""
        next_gen = []
        
        for front in fronts:
            if len(next_gen) + len(front) <= self.population_size:
                next_gen.extend([evaluated[i][0] for i in front])
            else:
                remaining = self.population_size - len(next_gen)
                selected = random.sample(front, remaining)
                next_gen.extend([evaluated[i][0] for i in selected])
                break
        
        return next_gen
    
    def _random_params(self, action_type: ActionType) -> Dict:
        if action_type == ActionType.HOLD:
            return {"hold_minutes": random.uniform(1, 5)}
        elif action_type == ActionType.SPEED_ADJUST:
            return {"speed_factor": random.uniform(0.85, 1.25)}
        elif action_type == ActionType.REROUTE:
            return {"time_delta": random.uniform(-2, 4)}
        return {}
