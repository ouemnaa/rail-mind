"""
Intelligent Conflict Resolution Extractor
Uses OpenRouter (cloud LLM) to understand PDF content and extract conflicts/resolutions
Can append to existing JSON file for incremental knowledge base building
"""

import pymupdf
import json
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


# =========================
# Data model
# =========================

@dataclass
class ConflictResolution:
    conflict_description: str
    conflict_type: str
    resolution_strategy: str
    reasoning: str
    context: Optional[str] = None
    confidence: str = "high"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================
# Knowledge Base Manager
# =========================

class ConflictKnowledgeBase:
    """
    Manages a persistent JSON file that can be appended to
    """
    
    def __init__(self, json_file: str = "conflict_knowledge_base.json"):
        """
        Initialize knowledge base
        
        Args:
            json_file: Path to the JSON file storing all conflicts
        """
        self.json_file = Path(json_file)
        self.conflicts = []
        self.metadata = {
            "total_conflicts": 0,
            "sources": [],
            "last_updated": None
        }
        
        # Load existing data if file exists
        if self.json_file.exists():
            self._load_existing()
    
    def _load_existing(self):
        """Load existing conflicts from JSON file"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.conflicts = data.get('conflicts', [])
                self.metadata = data.get('metadata', self.metadata)
            print(f"✓ Loaded {len(self.conflicts)} existing conflicts from {self.json_file}")
        except Exception as e:
            print(f"⚠️  Error loading existing file: {e}")
            print("   Starting with empty knowledge base")
            self.conflicts = []
    
    def add_conflicts(self, new_conflicts: List[Dict[str, Any]], source_file: str):
        """
        Add new conflicts to the knowledge base
        
        Args:
            new_conflicts: List of conflict dictionaries with id, source, etc.
            source_file: Name of the source PDF
        """
        # Check for duplicates based on ID
        existing_ids = {c['id'] for c in self.conflicts}
        
        added = 0
        skipped = 0
        
        for conflict in new_conflicts:
            if conflict['id'] in existing_ids:
                print(f"   ⚠️  Skipping duplicate: {conflict['id']}")
                skipped += 1
            else:
                self.conflicts.append(conflict)
                existing_ids.add(conflict['id'])
                added += 1
        
        # Update metadata
        if source_file not in self.metadata['sources']:
            self.metadata['sources'].append(source_file)
        
        self.metadata['total_conflicts'] = len(self.conflicts)
        self.metadata['last_updated'] = datetime.now().isoformat()
        
        print(f"   ✓ Added {added} new conflicts")
        if skipped > 0:
            print(f"   ⚠️  Skipped {skipped} duplicates")
        
        return added
    
    def save(self):
        """Save all conflicts to JSON file"""
        data = {
            "metadata": self.metadata,
            "conflicts": self.conflicts
        }
        
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved {len(self.conflicts)} conflicts to {self.json_file}")
    
    def get_statistics(self):
        """Get statistics about the knowledge base"""
        type_counts = {}
        confidence_counts = {}
        
        for conflict in self.conflicts:
            # Count by type
            ctype = conflict.get('conflict_type', 'unknown')
            type_counts[ctype] = type_counts.get(ctype, 0) + 1
            
            # Count by confidence
            conf = conflict.get('confidence', 'unknown')
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
        
        return {
            "total_conflicts": len(self.conflicts),
            "sources": self.metadata['sources'],
            "conflict_types": type_counts,
            "confidence_levels": confidence_counts,
            "last_updated": self.metadata.get('last_updated')
        }


# =========================
# Extractor
# =========================

class IntelligentConflictExtractor:
    """
    AI-powered extractor using OpenRouter
    """

    def __init__(
        self,
        api_key: str,
        model: str = "tngtech/deepseek-r1t2-chimera:free"
    ):
        """
        Args:
            api_key: OpenRouter API key
            model: OpenRouter model ID
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def extract_from_pdf(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:

        pdf_path = Path(pdf_path)
        print(f"📄 Processing: {pdf_path.name}")

        full_text = self._extract_text_from_pdf(pdf_path, max_pages)

        if not full_text.strip():
            raise ValueError("No text could be extracted from the PDF")

        print(f"   Extracted {len(full_text)} characters from PDF")
        print(f"   Analyzing content with OpenRouter...")

        conflicts = self._analyze_with_llm(full_text)

        print(f"   ✓ Found {len(conflicts)} conflict-resolution pairs")

        # Format conflicts with id and source
        formatted_conflicts = []
        for i, conflict in enumerate(conflicts):
            conflict_dict = conflict.to_dict()
            # Add id and source at the beginning
            formatted_conflict = {
                "id": f"{pdf_path.stem}_{i}",
                "source": pdf_path.name,
                **conflict_dict  # Merge the rest of the conflict data
            }
            formatted_conflicts.append(formatted_conflict)

        return {
            "source_file": pdf_path.name,
            "total_conflicts_found": len(conflicts),
            "conflicts": formatted_conflicts,
            "extraction_method": "openrouter_llm"
        }
    
    def extract_and_append(
        self,
        pdf_path: str,
        knowledge_base: ConflictKnowledgeBase,
        max_pages: Optional[int] = None
    ) -> int:
        """
        Extract from PDF and append to knowledge base
        
        Args:
            pdf_path: Path to PDF file
            knowledge_base: ConflictKnowledgeBase instance
            max_pages: Optional page limit
            
        Returns:
            Number of conflicts added
        """
        results = self.extract_from_pdf(pdf_path, max_pages)
        
        # Add to knowledge base
        added = knowledge_base.add_conflicts(
            results['conflicts'],
            results['source_file']
        )
        
        # Save to file
        knowledge_base.save()
        
        return added

    def _extract_text_from_pdf(
        self,
        pdf_path: Path,
        max_pages: Optional[int] = None
    ) -> str:
        try:
            doc = pymupdf.open(pdf_path)
            text_parts = []

            num_pages = min(len(doc), max_pages) if max_pages else len(doc)

            for page_num in range(num_pages):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

            doc.close()
            return "\n\n".join(text_parts)

        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {e}")

    def _analyze_with_llm(self, text: str) -> List[ConflictResolution]:

        prompt = f"""
You are analyzing a research or technical document to extract conflict-resolution knowledge.

Your task:
1. Identify exact conflicts, problems, or challenges
2. Identify and include the railway-network-context of the conflict (The context of a railway network is the physical infrastructure, operational rules, and scheduling environment in which trains run, including tracks, stations, signaling, junctions, and traffic management constraints.)
3. Identify with details how each conflict is resolved
4. Explain with details the reasoning behind each resolution

Return ONLY a JSON array.

Each object must contain:
- conflict_description
- conflict_type
- context
- resolution_strategy
- reasoning
- confidence ("high", "medium", "low")

If no conflicts are found, return an empty array.

Article:
{text[:100000]}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Conflict Resolution Extractor"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }

        response_text = ""

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=180
            )

            response.raise_for_status()
            data = response.json()

            response_text = data["choices"][0]["message"]["content"].strip()

            # Remove markdown if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                response_text = response_text.replace("json", "").strip()

            conflicts_data = json.loads(response_text)

            conflicts = []
            for item in conflicts_data:
                conflicts.append(
                    ConflictResolution(
                        conflict_description=item.get("conflict_description", ""),
                        conflict_type=item.get("conflict_type", "unknown"),
                        resolution_strategy=item.get("resolution_strategy", ""),
                        reasoning=item.get("reasoning", ""),
                        context=item.get("context"),
                        confidence=item.get("confidence", "medium")
                    )
                )

            return conflicts

        except json.JSONDecodeError:
            print("⚠️ JSON parsing failed")
            print(response_text[:300])
            return []
        except Exception as e:
            print(f"⚠️ LLM error: {e}")
            return []


# =========================
# Main
# =========================

def main():
    import sys

    OPENROUTER_API_KEY = "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"
    KNOWLEDGE_BASE_FILE = "conflict_knowledge_base.json"  # Same file for all PDFs

    # Initialize
    extractor = IntelligentConflictExtractor(
        api_key=OPENROUTER_API_KEY,
        model="tngtech/deepseek-r1t2-chimera:free"
    )
    
    knowledge_base = ConflictKnowledgeBase(json_file=KNOWLEDGE_BASE_FILE)

    if len(sys.argv) < 2:
        print("Usage: python intelligent_conflict_extractor.py <path_to_pdf>")
        print("Example: python intelligent_conflict_extractor.py paper.pdf")
        print()
        print(f"Data will be appended to: {KNOWLEDGE_BASE_FILE}")
        return 1

    pdf_path = sys.argv[1]

    try:
        print("\n" + "="*70)
        print("EXTRACTING AND APPENDING TO KNOWLEDGE BASE")
        print("="*70 + "\n")
        
        # Extract and append
        added = extractor.extract_and_append(pdf_path, knowledge_base)
        
        # Show statistics
        print("\n" + "="*70)
        print("KNOWLEDGE BASE STATISTICS")
        print("="*70 + "\n")
        
        stats = knowledge_base.get_statistics()
        print(f"Total conflicts: {stats['total_conflicts']}")
        print(f"Sources processed: {len(stats['sources'])}")
        print(f"  - {', '.join(stats['sources'])}")
        print(f"\nConflict types:")
        for ctype, count in stats['conflict_types'].items():
            print(f"  - {ctype}: {count}")
        print(f"\nConfidence levels:")
        for conf, count in stats['confidence_levels'].items():
            print(f"  - {conf}: {count}")
        print(f"\nLast updated: {stats['last_updated']}")
        
        print(f"\n✓ All data saved to {KNOWLEDGE_BASE_FILE}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
