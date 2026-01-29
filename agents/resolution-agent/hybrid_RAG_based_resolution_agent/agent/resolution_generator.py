"""
Two-Layer Explainable Resolution Generation System
Layer 1: Algorithm-based resolutions from research papers
Layer 2: Historical case-based fine-tuning and ranking
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
from groq import Groq


# =========================
# Data Models
# =========================

@dataclass
class ResolutionCandidate:
    """Single resolution option with full explainability"""
    resolution_id: str
    strategy_name: str
    action_steps: List[str]
    expected_outcome: str
    
    # Explainability components
    reasoning: str
    source_type: str  # "algorithm" or "historical" or "hybrid"
    source_references: List[str]
    confidence_score: float  # 0.0 to 1.0
    
    # Algorithm-specific
    algorithm_name: Optional[str] = None
    algorithm_reasoning: Optional[str] = None
    
    # Historical-specific
    similar_cases: List[Dict[str, Any]] = field(default_factory=list)
    historical_success_rate: Optional[float] = None
    
    # Impact assessment
    affected_trains: List[str] = field(default_factory=list)
    estimated_delay_reduction_sec: Optional[int] = None
    side_effects: List[str] = field(default_factory=list)
    
    # Ranking factors
    feasibility_score: float = 0.0
    safety_score: float = 0.0
    efficiency_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResolutionReport:
    """Final output with ranked resolution candidates"""
    conflict_id: str
    conflict_summary: str
    timestamp: str
    context_snapshot: Dict[str, Any]
    
    # The three ranked resolutions
    resolutions: List[ResolutionCandidate]
    
    # Meta information
    layer1_count: int
    layer2_refinements: Dict[str, Any]
    generation_time_sec: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "resolutions": [r.to_dict() for r in self.resolutions]
        }


# =========================
# Layer 1: Algorithm Extractor
# =========================

class AlgorithmResolutionExtractor:
    """
    Extracts resolutions from research algorithm collection in Qdrant
    """
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str = "railway_algorithms",
        llm_api_key: Optional[str] = None,
        llm_model: str = "mixtral-8x7b-32768",
        embedder: Optional[Any] = None
    ):
        self.client = qdrant_client
        self.collection_name = collection_name
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.groq_client = Groq(api_key=llm_api_key) if llm_api_key else None
        self._embedder = embedder  # Reuse pre-loaded embedder from system level
    
    def extract_algorithm_resolutions(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        top_k: int = 5
    ) -> List[ResolutionCandidate]:
        """
        Layer 1: Find relevant algorithms and extract resolution strategies
        """
        
        # Build search query from conflict
        query_text = self._build_algorithm_query(conflict)
        
        # Search for relevant algorithms
        search_results = self._search_algorithms(query_text, top_k)
        
        if not search_results:
            return []
        
        # Use LLM to extract actionable resolutions from algorithms
        resolutions = self._llm_extract_resolutions(
            conflict=conflict,
            context=context,
            algorithms=search_results
        )
        
        return resolutions
    
    def _build_algorithm_query(self, conflict: Dict[str, Any]) -> str:
        """Build semantic search query from conflict description"""
        parts = [
            conflict.get("conflict_type", ""),
            conflict.get("explanation", ""),
        ]
        
        if conflict.get("metadata"):
            for key, value in conflict["metadata"].items():
                parts.append(f"{key}: {value}")
        
        return " ".join(str(p) for p in parts if p)
    
    def _search_algorithms(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Search for relevant algorithms in Qdrant"""
        try:
            # Use pre-loaded embedder if available, otherwise load now
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            query_vector = self._embedder.encode(query).tolist()
            
            # Use query_points instead of search
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k
            )
            
            algorithms = []
            for hit in results.points:
                algorithms.append({
                    "score": hit.score,
                    "algorithm_id": hit.id,
                    "payload": hit.payload
                })
            
            return algorithms
        
        except Exception as e:
            print(f"⚠️ Algorithm search failed: {e}")
            return []
    
    def _llm_extract_resolutions(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        algorithms: List[Dict[str, Any]]
    ) -> List[ResolutionCandidate]:
        """Use LLM to convert algorithms into actionable resolutions"""
        
        if not self.llm_api_key:
            # Fallback: direct conversion without LLM
            return self._fallback_algorithm_conversion(algorithms)
        
        prompt = self._build_extraction_prompt(conflict, context, algorithms)
        
        try:
            response = self._call_llm(prompt)
            resolutions = self._parse_llm_response(response, algorithms)
            return resolutions
        
        except Exception as e:
            print(f"⚠️ LLM extraction failed: {e}")
            return self._fallback_algorithm_conversion(algorithms)
    
    def _build_extraction_prompt(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        algorithms: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for LLM to extract resolutions"""
        
        # Summarize context
        context_summary = {
            "total_trains": len(context.get("trains", [])),
            "total_edges": len(context.get("edges", [])),
            "conflict_location": conflict.get("location", {}),
        }
        
        prompt = f"""You are a railway operations expert. Given a conflict and relevant research algorithms, extract actionable resolution strategies.

CONFLICT:
{json.dumps(conflict, indent=2)}

NETWORK CONTEXT:
{json.dumps(context_summary, indent=2)}

RELEVANT ALGORITHMS:
{json.dumps([a["payload"] for a in algorithms], indent=2)}

Your task:
1. Analyze how each algorithm addresses this specific conflict
2. Extract concrete action steps from the algorithms
3. Explain the reasoning behind each resolution
4. Assess confidence based on algorithm applicability

Return ONLY a JSON array of resolutions. Each resolution must have:
- strategy_name: Brief name (e.g., "Priority-based rescheduling")
- action_steps: Array of specific actions to take
- expected_outcome: What will this achieve?
- reasoning: Why this algorithm applies to this conflict
- algorithm_name: Name from the source algorithm
- confidence_score: 0.0 to 1.0 based on applicability
- affected_trains: Array of train IDs that will be impacted
- estimated_delay_reduction_sec: Estimated delay reduction (integer)

Return 2-4 resolutions maximum, ranked by confidence.
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call Groq Cloud API"""
        response = self.groq_client.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096
        )
        
        content = response.choices[0].message.content.strip()
        
        # Remove markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            content = content.replace("json", "").strip()
        
        return content
    
    def _parse_llm_response(
        self,
        response: str,
        algorithms: List[Dict[str, Any]]
    ) -> List[ResolutionCandidate]:
        """Parse LLM JSON response into ResolutionCandidate objects"""
        
        try:
            data = json.loads(response)
            
            resolutions = []
            for i, item in enumerate(data):
                # Build source references
                source_refs = [
                    f"Algorithm: {item.get('algorithm_name', 'Unknown')}"
                ]
                
                resolution = ResolutionCandidate(
                    resolution_id=f"algo_{i+1}",
                    strategy_name=item.get("strategy_name", "Unknown Strategy"),
                    action_steps=item.get("action_steps", []),
                    expected_outcome=item.get("expected_outcome", ""),
                    reasoning=item.get("reasoning", ""),
                    source_type="algorithm",
                    source_references=source_refs,
                    confidence_score=item.get("confidence_score", 0.5),
                    algorithm_name=item.get("algorithm_name"),
                    algorithm_reasoning=item.get("reasoning"),
                    affected_trains=item.get("affected_trains", []),
                    estimated_delay_reduction_sec=item.get("estimated_delay_reduction_sec"),
                    feasibility_score=item.get("confidence_score", 0.5),
                    safety_score=0.8,  # Default, will be refined in layer 2
                    efficiency_score=0.7
                )
                
                resolutions.append(resolution)
            
            return resolutions
        
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse LLM response: {e}")
            print(f"Response: {response[:500]}")
            return []
    
    def _fallback_algorithm_conversion(
        self,
        algorithms: List[Dict[str, Any]]
    ) -> List[ResolutionCandidate]:
        """Fallback: Direct conversion of algorithms without LLM"""
        
        resolutions = []
        for i, algo in enumerate(algorithms[:3]):
            payload = algo["payload"]
            
            resolution = ResolutionCandidate(
                resolution_id=f"algo_{i+1}",
                strategy_name=payload.get("conflict_type", "Unknown Strategy"),
                action_steps=[payload.get("resolution_strategy", "No strategy available")],
                expected_outcome="Resolve the conflict based on algorithm",
                reasoning=payload.get("reasoning", "No reasoning provided"),
                source_type="algorithm",
                source_references=[f"Algorithm score: {algo['score']:.3f}"],
                confidence_score=min(algo["score"], 1.0),
                algorithm_name=payload.get("conflict_type"),
                algorithm_reasoning=payload.get("reasoning")
            )
            
            resolutions.append(resolution)
        
        return resolutions


# =========================
# Layer 2: Historical Refiner
# =========================

class HistoricalResolutionRefiner:
    """
    Refines algorithm resolutions using historical case data
    Adds context, success rates, and generates final ranked recommendations
    """
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str = "historical_incidents",
        llm_api_key: Optional[str] = None,
        llm_model: str = "mixtral-8x7b-32768",
        embedder: Optional[Any] = None
    ):
        self.client = qdrant_client
        self.collection_name = collection_name
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.groq_client = Groq(api_key=llm_api_key) if llm_api_key else None
        self._embedder = embedder  # Reuse pre-loaded embedder from system level
    
    def refine_and_rank(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        algorithm_resolutions: List[ResolutionCandidate],
        top_k_historical: int = 10
    ) -> Tuple[List[ResolutionCandidate], Dict[str, Any]]:
        """
        Layer 2: Refine resolutions with historical data and rank top 3
        
        Returns:
            - Top 3 ranked resolutions
            - Refinement metadata
        """
        
        # Search for similar historical cases
        historical_cases = self._search_historical_cases(conflict, top_k_historical)
        
        # Refine each algorithm resolution
        refined_resolutions = []
        for resolution in algorithm_resolutions:
            refined = self._refine_resolution(
                resolution=resolution,
                conflict=conflict,
                context=context,
                historical_cases=historical_cases
            )
            refined_resolutions.append(refined)
        
        # If we have LLM, generate hybrid resolutions
        if self.llm_api_key and historical_cases:
            hybrid_resolutions = self._generate_hybrid_resolutions(
                conflict=conflict,
                context=context,
                algorithm_resolutions=refined_resolutions,
                historical_cases=historical_cases
            )
            refined_resolutions.extend(hybrid_resolutions)
        
        # Rank all resolutions
        ranked = self._rank_resolutions(refined_resolutions, conflict, context)
        
        # Select top 3
        top_3 = ranked[:3]
        
        # Build metadata about refinements
        metadata = {
            "historical_cases_found": len(historical_cases),
            "algorithm_resolutions": len(algorithm_resolutions),
            "hybrid_resolutions_generated": len(refined_resolutions) - len(algorithm_resolutions),
            "total_candidates_evaluated": len(refined_resolutions),
            "historical_success_rates": self._calculate_historical_stats(historical_cases)
        }
        
        return top_3, metadata
    
    def _search_historical_cases(
        self,
        conflict: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Search for similar historical incidents"""
        
        query_text = f"{conflict.get('conflict_type', '')} {conflict.get('explanation', '')}"
        
        try:
            # Use pre-loaded embedder if available, otherwise load now
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            query_vector = self._embedder.encode(query_text).tolist()
            
            # Use query_points instead of search
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k
            )
            
            cases = []
            for hit in results.points:
                cases.append({
                    "score": hit.score,
                    "case_id": hit.id,
                    "payload": hit.payload
                })
            
            return cases
        
        except Exception as e:
            print(f"⚠️ Historical search failed: {e}")
            return []
    
    def _refine_resolution(
        self,
        resolution: ResolutionCandidate,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        historical_cases: List[Dict[str, Any]]
    ) -> ResolutionCandidate:
        """Refine a single resolution with historical data"""
        
        # Find relevant historical cases for this resolution strategy
        relevant_cases = self._filter_relevant_cases(
            resolution.strategy_name,
            historical_cases
        )
        
        # Calculate historical success rate
        success_rate = self._calculate_success_rate(relevant_cases)
        
        # Update resolution with historical info
        resolution.similar_cases = [
            {
                "case_id": case["case_id"],
                "similarity": case["score"],
                "outcome": case["payload"].get("resolution_outcome", "unknown")
            }
            for case in relevant_cases[:3]
        ]
        
        resolution.historical_success_rate = success_rate
        
        # Update source references
        if relevant_cases:
            resolution.source_references.append(
                f"Based on {len(relevant_cases)} similar historical cases"
            )
            resolution.source_type = "hybrid"
        
        # Adjust confidence based on historical success
        if success_rate is not None:
            resolution.confidence_score = (
                resolution.confidence_score * 0.6 + success_rate * 0.4
            )
        
        # Update scores based on historical data
        resolution.safety_score = self._calculate_safety_score(relevant_cases)
        resolution.efficiency_score = self._calculate_efficiency_score(relevant_cases)
        
        return resolution
    
    def _filter_relevant_cases(
        self,
        strategy_name: str,
        cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter cases relevant to a specific strategy"""
        
        # Simple keyword matching for now
        strategy_keywords = strategy_name.lower().split()
        
        relevant = []
        for case in cases:
            resolution_text = str(case["payload"].get("resolution", "")).lower()
            
            # Check if any strategy keywords appear in the resolution
            if any(kw in resolution_text for kw in strategy_keywords):
                relevant.append(case)
        
        return relevant
    
    def _calculate_success_rate(self, cases: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate success rate from historical cases"""
        
        if not cases:
            return None
        
        successful = 0
        total = 0
        
        for case in cases:
            outcome = case["payload"].get("resolution_outcome", "").lower()
            if outcome in ["success", "resolved", "effective"]:
                successful += 1
            total += 1
        
        return successful / total if total > 0 else None
    
    def _calculate_safety_score(self, cases: List[Dict[str, Any]]) -> float:
        """Calculate safety score based on historical incidents"""
        
        if not cases:
            return 0.8  # Default
        
        # Check for safety-related issues in historical cases
        safety_issues = 0
        for case in cases:
            if "safety" in str(case["payload"]).lower():
                safety_issues += 1
        
        # Higher score = safer (fewer issues)
        return max(0.5, 1.0 - (safety_issues / len(cases)))
    
    def _calculate_efficiency_score(self, cases: List[Dict[str, Any]]) -> float:
        """Calculate efficiency score from historical cases"""
        
        if not cases:
            return 0.7  # Default
        
        # Look for delay reductions in historical cases
        total_efficiency = 0.0
        count = 0
        
        for case in cases:
            delay_reduction = case["payload"].get("delay_reduction_sec")
            if delay_reduction and delay_reduction > 0:
                # Normalize to 0-1 scale (assuming 600s is excellent)
                total_efficiency += min(delay_reduction / 600.0, 1.0)
                count += 1
        
        return total_efficiency / count if count > 0 else 0.7
    
    def _generate_hybrid_resolutions(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        algorithm_resolutions: List[ResolutionCandidate],
        historical_cases: List[Dict[str, Any]]
    ) -> List[ResolutionCandidate]:
        """Use LLM to generate new hybrid resolutions combining algorithms and history"""
        
        if not self.llm_api_key or not historical_cases:
            return []
        
        prompt = self._build_hybrid_prompt(
            conflict,
            context,
            algorithm_resolutions,
            historical_cases
        )
        
        try:
            response = self._call_llm(prompt)
            hybrids = self._parse_hybrid_response(response)
            return hybrids
        
        except Exception as e:
            print(f"⚠️ Hybrid generation failed: {e}")
            return []
    
    def _build_hybrid_prompt(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any],
        algorithm_resolutions: List[ResolutionCandidate],
        historical_cases: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for generating hybrid resolutions"""
        
        algo_summaries = [
            {
                "strategy": r.strategy_name,
                "actions": r.action_steps,
                "reasoning": r.reasoning
            }
            for r in algorithm_resolutions
        ]
        
        historical_summaries = [
            {
                "resolution": case["payload"].get("resolution", ""),
                "outcome": case["payload"].get("resolution_outcome", ""),
                "similarity": case["score"]
            }
            for case in historical_cases[:5]
        ]
        
        prompt = f"""You are a railway operations expert. Generate 1-2 NEW hybrid resolution strategies by combining insights from research algorithms and successful historical cases.

CONFLICT:
{json.dumps(conflict, indent=2)}

ALGORITHM-BASED RESOLUTIONS:
{json.dumps(algo_summaries, indent=2)}

HISTORICAL SIMILAR CASES:
{json.dumps(historical_summaries, indent=2)}

Your task:
Generate innovative hybrid strategies that:
1. Combine the best elements from algorithms and historical cases
2. Are specifically tailored to this conflict and context
3. Offer different approaches than the pure algorithm solutions

Return ONLY a JSON array with 1-2 hybrid resolutions. Each must have:
- strategy_name: Descriptive name
- action_steps: Concrete steps (array of strings)
- expected_outcome: What will be achieved
- reasoning: Why this hybrid approach is effective
- confidence_score: 0.0 to 1.0
- affected_trains: Train IDs (array)
- estimated_delay_reduction_sec: Integer estimate
- side_effects: Potential negative impacts (array)

Focus on PRACTICAL, ACTIONABLE resolutions.
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call Groq Cloud API"""
        response = self.groq_client.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=3072
        )
        
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```"):
            content = content.split("```")[1]
            content = content.replace("json", "").strip()
        
        return content
    
    def _parse_hybrid_response(self, response: str) -> List[ResolutionCandidate]:
        """Parse hybrid resolution JSON"""
        
        try:
            data = json.loads(response)
            
            hybrids = []
            for i, item in enumerate(data):
                hybrid = ResolutionCandidate(
                    resolution_id=f"hybrid_{i+1}",
                    strategy_name=item.get("strategy_name", "Hybrid Strategy"),
                    action_steps=item.get("action_steps", []),
                    expected_outcome=item.get("expected_outcome", ""),
                    reasoning=item.get("reasoning", ""),
                    source_type="hybrid",
                    source_references=["Combined algorithm and historical insights"],
                    confidence_score=item.get("confidence_score", 0.6),
                    affected_trains=item.get("affected_trains", []),
                    estimated_delay_reduction_sec=item.get("estimated_delay_reduction_sec"),
                    side_effects=item.get("side_effects", []),
                    feasibility_score=item.get("confidence_score", 0.6),
                    safety_score=0.75,
                    efficiency_score=0.75
                )
                hybrids.append(hybrid)
            
            return hybrids
        
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse hybrid response: {e}")
            return []
    
    def _rank_resolutions(
        self,
        resolutions: List[ResolutionCandidate],
        conflict: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[ResolutionCandidate]:
        """Rank resolutions using multi-criteria scoring"""
        
        severity_multiplier = {
            "critical": 1.2,
            "high": 1.1,
            "medium": 1.0,
            "low": 0.9
        }.get(conflict.get("severity", "medium"), 1.0)
        
        for resolution in resolutions:
            # Composite score
            composite = (
                resolution.confidence_score * 0.35 +
                resolution.feasibility_score * 0.25 +
                resolution.safety_score * 0.25 +
                resolution.efficiency_score * 0.15
            )
            
            # Apply severity multiplier
            composite *= severity_multiplier
            
            # Bonus for historical success
            if resolution.historical_success_rate:
                composite *= (0.9 + resolution.historical_success_rate * 0.2)
            
            # Store final score (use confidence_score field for sorting)
            resolution.confidence_score = min(composite, 1.0)
        
        # Sort by composite score
        ranked = sorted(
            resolutions,
            key=lambda r: r.confidence_score,
            reverse=True
        )
        
        return ranked
    
    def _calculate_historical_stats(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics about historical cases"""
        
        if not cases:
            return {}
        
        total_cases = len(cases)
        avg_similarity = sum(c["score"] for c in cases) / total_cases
        
        outcomes = {}
        for case in cases:
            outcome = case["payload"].get("resolution_outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        return {
            "total_cases": total_cases,
            "average_similarity": avg_similarity,
            "outcome_distribution": outcomes
        }


# =========================
# Main Resolution Generator
# =========================

class ResolutionGenerationSystem:
    """
    Complete two-layer system for generating explainable resolutions
    """
    
    def __init__(
        self,
        qdrant_url: str,
        qdrant_api_key: Optional[str] = None,
        algorithm_collection: str = "railway_algorithms",
        historical_collection: str = "rail_incidents",
        llm_api_key: Optional[str] = None,
        llm_model: str = "openai/gpt-oss-120b"
    ):
        # Initialize Qdrant client
        if qdrant_api_key:
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            self.client = QdrantClient(url=qdrant_url)
        
        # ✨ Load embedder ONCE at system level
        print("⚡ Loading embedding model (cached for reuse)...")
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            print("✓ Embedding model loaded\n")
        except Exception as e:
            print(f"⚠️ Failed to load embedding model: {e}")
            self.embedder = None
        
        # Initialize layers (passing shared embedder)
        self.layer1 = AlgorithmResolutionExtractor(
            qdrant_client=self.client,
            collection_name=algorithm_collection,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            embedder=self.embedder
        )
        
        self.layer2 = HistoricalResolutionRefiner(
            qdrant_client=self.client,
            collection_name=historical_collection,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            embedder=self.embedder
        )
    
    def generate_resolutions(
        self,
        conflict: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ResolutionReport:
        """
        Main entry point: Generate top 3 explainable resolutions
        
        Args:
            conflict: Conflict data from conflict_input.json format
            context: Network context from context.json format
        
        Returns:
            ResolutionReport with top 3 ranked resolutions
        """
        
        start_time = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"🚂 Resolution Generation for Conflict: {conflict.get('conflict_id')}")
        print(f"{'='*60}\n")
        
        # Layer 1: Extract algorithm-based resolutions
        print("📚 Layer 1: Extracting algorithm-based resolutions...")
        algorithm_resolutions = self.layer1.extract_algorithm_resolutions(
            conflict=conflict,
            context=context,
            top_k=5
        )
        print(f"   ✓ Found {len(algorithm_resolutions)} algorithm resolutions\n")
        
        # Layer 2: Refine with historical data and rank
        print("🔍 Layer 2: Refining with historical cases...")
        top_3, refinement_metadata = self.layer2.refine_and_rank(
            conflict=conflict,
            context=context,
            algorithm_resolutions=algorithm_resolutions,
            top_k_historical=10
        )
        print(f"   ✓ Generated {len(top_3)} final ranked resolutions\n")
        
        # Build report
        end_time = datetime.now()
        generation_time = (end_time - start_time).total_seconds()
        
        report = ResolutionReport(
            conflict_id=conflict.get("conflict_id", "unknown"),
            conflict_summary=conflict.get("explanation", ""),
            timestamp=datetime.now().isoformat(),
            context_snapshot={
                "total_trains": len(context.get("trains", [])),
                "total_edges": len(context.get("edges", [])),
                "conflict_location": conflict.get("location", {})
            },
            resolutions=top_3,
            layer1_count=len(algorithm_resolutions),
            layer2_refinements=refinement_metadata,
            generation_time_sec=generation_time
        )
        
        # Print summary
        self._print_summary(report)
        
        return report
    
    def _print_summary(self, report: ResolutionReport):
        """Print a summary of the generated resolutions"""
        
        print(f"\n{'='*60}")
        print(f"📊 RESOLUTION SUMMARY")
        print(f"{'='*60}\n")
        
        for i, resolution in enumerate(report.resolutions, 1):
            print(f"--- Resolution {i}: {resolution.strategy_name} ---")
            print(f"Source: {resolution.source_type}")
            print(f"Confidence: {resolution.confidence_score:.2%}")
            print(f"Safety: {resolution.safety_score:.2%}")
            print(f"Efficiency: {resolution.efficiency_score:.2%}")
            
            if resolution.historical_success_rate:
                print(f"Historical Success: {resolution.historical_success_rate:.2%}")
            
            print(f"\nReasoning: {resolution.reasoning}")
            print(f"\nAction Steps:")
            for step in resolution.action_steps:
                print(f"  • {step}")
            
            print(f"\nExpected Outcome: {resolution.expected_outcome}")
            
            if resolution.side_effects:
                print(f"\nPotential Side Effects:")
                for effect in resolution.side_effects:
                    print(f"  ⚠️ {effect}")
            
            print()
        
        print(f"{'='*60}\n")
        print(f"Generation Time: {report.generation_time_sec:.2f}s")
        print(f"Historical Cases Analyzed: {report.layer2_refinements.get('historical_cases_found', 0)}")
        print()
    
    def save_report(
        self,
        report: ResolutionReport,
        output_path: str,
        format: str = "json"
    ):
        """Save resolution report to file"""
        
        output_path = Path(output_path)
        
        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"✅ Report saved to {output_path}")
        
        elif format == "markdown":
            md = self._generate_markdown_report(report)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"✅ Report saved to {output_path}")
    
    def _generate_markdown_report(self, report: ResolutionReport) -> str:
        """Generate markdown format report"""
        
        md = f"""# Conflict Resolution Report

**Conflict ID:** {report.conflict_id}
**Timestamp:** {report.timestamp}
**Generation Time:** {report.generation_time_sec:.2f}s

## Conflict Summary
{report.conflict_summary}

### Context
- Total Trains: {report.context_snapshot.get('total_trains', 'N/A')}
- Total Edges: {report.context_snapshot.get('total_edges', 'N/A')}
- Location: {report.context_snapshot.get('conflict_location', 'N/A')}

---

## Recommended Resolutions

"""
        
        for i, res in enumerate(report.resolutions, 1):
            md += f"""### Resolution {i}: {res.strategy_name}

**Source Type:** {res.source_type}
**Confidence Score:** {res.confidence_score:.1%}
**Safety Score:** {res.safety_score:.1%}
**Efficiency Score:** {res.efficiency_score:.1%}
"""
            
            if res.historical_success_rate:
                md += f"**Historical Success Rate:** {res.historical_success_rate:.1%}\n"
            
            md += f"""
#### Reasoning
{res.reasoning}

#### Action Steps
"""
            for step in res.action_steps:
                md += f"1. {step}\n"
            
            md += f"""
#### Expected Outcome
{res.expected_outcome}

#### Impact
- **Affected Trains:** {', '.join(res.affected_trains) if res.affected_trains else 'To be determined'}
"""
            
            if res.estimated_delay_reduction_sec:
                md += f"- **Estimated Delay Reduction:** {res.estimated_delay_reduction_sec}s ({res.estimated_delay_reduction_sec/60:.1f} minutes)\n"
            
            if res.side_effects:
                md += "\n#### Potential Side Effects\n"
                for effect in res.side_effects:
                    md += f"- ⚠️ {effect}\n"
            
            if res.similar_cases:
                md += "\n#### Similar Historical Cases\n"
                for case in res.similar_cases:
                    md += f"- Case {case['case_id']}: Similarity {case['similarity']:.2%}, Outcome: {case['outcome']}\n"
            
            md += "\n---\n\n"
        
        md += f"""
## Analysis Metadata

- **Layer 1 (Algorithm) Resolutions:** {report.layer1_count}
- **Layer 2 Refinements:**
  - Historical Cases Found: {report.layer2_refinements.get('historical_cases_found', 0)}
  - Total Candidates Evaluated: {report.layer2_refinements.get('total_candidates_evaluated', 0)}
  - Hybrid Resolutions Generated: {report.layer2_refinements.get('hybrid_resolutions_generated', 0)}

"""
        
        return md