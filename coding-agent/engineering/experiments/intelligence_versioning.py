"""
Intelligence Versioning - Track Decision Quality Over Time

Not feature versions. INTELLIGENCE versions.
Every improvement must be measurable.
"""

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime


@dataclass
class IntelligenceVersion:
    """
    A specific version of the system's intelligence.
    
    Versions are compared objectively through benchmarks.
    """
    version: str  # e.g., "v1.0", "v1.1"
    released: datetime
    
    # Capabilities
    reasoning_policy: str
    planning_algorithm: str
    trust_framework: str
    memory_system: str
    world_model: str
    
    # Performance
    benchmark_score: float
    reasoning_score: float
    planning_score: float
    execution_score: float
    trust_score: float
    cost_efficiency: float
    
    # Metadata
    commit_hash: str
    notes: str


class IntelligenceRegistry:
    """
    Version control for intelligence.
    
    Track improvements scientifically.
    """
    
    def __init__(self):
        self.versions: Dict[str, IntelligenceVersion] = {}
    
    def register_version(self, version: IntelligenceVersion):
        """Register a new intelligence version"""
        self.versions[version.version] = version
    
    def compare(self, v1: str, v2: str) -> Dict[str, Any]:
        """Compare two versions across all dimensions"""
        version1 = self.versions[v1]
        version2 = self.versions[v2]
        
        return {
            "benchmark_delta": version2.benchmark_score - version1.benchmark_score,
            "reasoning_delta": version2.reasoning_score - version1.reasoning_score,
            "planning_delta": version2.planning_score - version1.planning_score,
            "execution_delta": version2.execution_score - version1.execution_score,
            "trust_delta": version2.trust_score - version1.trust_score,
            "cost_delta": version2.cost_efficiency - version1.cost_efficiency
        }
    
    def get_best_version(self) -> IntelligenceVersion:
        """Get highest-performing version"""
        return max(self.versions.values(), key=lambda v: v.benchmark_score)
