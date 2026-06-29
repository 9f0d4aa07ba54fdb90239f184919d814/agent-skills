"""
Policy System - Governance for Autonomous Execution

Every decision must be evaluated against policies before execution.
This is essential for enterprise trust in autonomous systems.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PolicyVerdict(Enum):
    """Policy evaluation outcomes"""
    ALLOW = "allow"          # Proceed without restriction
    WARN = "warn"            # Proceed but log warning
    AUDIT = "audit"          # Log for review, continue
    SUGGEST = "suggest"      # Optional improvement
    BLOCK = "block"          # Halt execution immediately


class PolicyCategory(Enum):
    """Types of policies"""
    SECURITY = "security"
    CODING_STANDARDS = "coding_standards"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    LICENSING = "licensing"
    COST = "cost"
    ORGANIZATIONAL = "organizational"


@dataclass
class PolicyViolation:
    """A single policy violation"""
    category: PolicyCategory
    verdict: PolicyVerdict
    policy_id: str
    message: str
    evidence: Dict[str, Any]
    remediation: Optional[str] = None
    severity: str = "medium"  # low, medium, high, critical


@dataclass
class PolicyResult:
    """Result of policy evaluation"""
    allowed: bool
    violations: List[PolicyViolation] = field(default_factory=list)
    warnings: List[PolicyViolation] = field(default_factory=list)
    suggestions: List[PolicyViolation] = field(default_factory=list)
    audits: List[PolicyViolation] = field(default_factory=list)
    
    @property
    def has_blocks(self) -> bool:
        return any(v.verdict == PolicyVerdict.BLOCK for v in self.violations)
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def summary(self) -> str:
        """Human-readable summary"""
        if self.allowed:
            parts = ["✓ Allowed"]
            if self.warnings:
                parts.append(f"{len(self.warnings)} warnings")
            if self.suggestions:
                parts.append(f"{len(self.suggestions)} suggestions")
            return ", ".join(parts)
        else:
            return f"✗ Blocked: {len(self.violations)} violations"


class Policy:
    """Base class for all policies"""
    
    def __init__(self, policy_id: str, category: PolicyCategory, enabled: bool = True):
        self.policy_id = policy_id
        self.category = category
        self.enabled = enabled
    
    def evaluate(self, context: Dict[str, Any]) -> List[PolicyViolation]:
        """
        Evaluate this policy against given context.
        Return list of violations (empty if compliant).
        """
        raise NotImplementedError


class PolicyEngine:
    """
    Central policy evaluation engine.
    
    Every task/decision flows through this before execution:
    
        task → check_policies() → allowed? → proceed/block
    """
    
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self.policy_log: List[Dict[str, Any]] = []
    
    def register_policy(self, policy: Policy):
        """Register a new policy"""
        self.policies[policy.policy_id] = policy
        logger.info(f"Registered policy: {policy.policy_id} ({policy.category.value})")
    
    def unregister_policy(self, policy_id: str):
        """Remove a policy"""
        if policy_id in self.policies:
            del self.policies[policy_id]
            logger.info(f"Unregistered policy: {policy_id}")
    
    def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """
        Evaluate all policies against given context.
        
        Args:
            context: Task/decision context with:
                - task_type: str (e.g., "file_write", "command_execution")
                - files: List[str] (affected files)
                - commands: List[str] (commands to execute)
                - code_changes: Dict (code being modified)
                - dependencies: List[str] (packages being added)
                - etc.
        
        Returns:
            PolicyResult with allow/block decision and all violations
        """
        result = PolicyResult(allowed=True)
        
        for policy in self.policies.values():
            if not policy.enabled:
                continue
            
            try:
                violations = policy.evaluate(context)
                
                for violation in violations:
                    if violation.verdict == PolicyVerdict.BLOCK:
                        result.violations.append(violation)
                        result.allowed = False
                    elif violation.verdict == PolicyVerdict.WARN:
                        result.warnings.append(violation)
                    elif violation.verdict == PolicyVerdict.SUGGEST:
                        result.suggestions.append(violation)
                    elif violation.verdict == PolicyVerdict.AUDIT:
                        result.audits.append(violation)
                
            except Exception as e:
                logger.error(f"Policy {policy.policy_id} evaluation failed: {e}")
                # Fail-safe: treat evaluation errors as blocks
                result.violations.append(PolicyViolation(
                    category=policy.category,
                    verdict=PolicyVerdict.BLOCK,
                    policy_id=policy.policy_id,
                    message=f"Policy evaluation error: {str(e)}",
                    evidence={"error": str(e)},
                    severity="high"
                ))
                result.allowed = False
        
        # Log every evaluation
        self._log_evaluation(context, result)
        
        return result
    
    def _log_evaluation(self, context: Dict[str, Any], result: PolicyResult):
        """Log policy evaluation for audit trail"""
        self.policy_log.append({
            "timestamp": self._now(),
            "context": context,
            "result": {
                "allowed": result.allowed,
                "violations": len(result.violations),
                "warnings": len(result.warnings),
                "suggestions": len(result.suggestions),
                "audits": len(result.audits)
            }
        })
    
    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent policy evaluations"""
        return self.policy_log[-limit:]
    
    @staticmethod
    def _now():
        """Current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()


# Example policies (to be expanded)

class NoSecretsInCodePolicy(Policy):
    """Block any code containing secrets/credentials"""
    
    def __init__(self):
        super().__init__("no-secrets-in-code", PolicyCategory.SECURITY)
        self.patterns = [
            "password",
            "api_key",
            "secret",
            "token",
            "credential",
            "private_key"
        ]
    
    def evaluate(self, context: Dict[str, Any]) -> List[PolicyViolation]:
        violations = []
        
        code_changes = context.get("code_changes", {})
        for file_path, code in code_changes.items():
            for pattern in self.patterns:
                if pattern in code.lower():
                    violations.append(PolicyViolation(
                        category=self.category,
                        verdict=PolicyVerdict.BLOCK,
                        policy_id=self.policy_id,
                        message=f"Potential secret detected: '{pattern}' in {file_path}",
                        evidence={"file": file_path, "pattern": pattern},
                        remediation="Use environment variables or secret manager",
                        severity="critical"
                    ))
        
        return violations


class CommandWhitelistPolicy(Policy):
    """Only allow whitelisted shell commands"""
    
    def __init__(self):
        super().__init__("command-whitelist", PolicyCategory.SECURITY)
        self.whitelist = {
            "git", "npm", "pip", "python", "node", "go", "cargo",
            "ls", "cat", "grep", "find", "mkdir", "rm", "cp", "mv"
        }
    
    def evaluate(self, context: Dict[str, Any]) -> List[PolicyViolation]:
        violations = []
        
        commands = context.get("commands", [])
        for cmd in commands:
            cmd_name = cmd.split()[0] if cmd else ""
            if cmd_name not in self.whitelist:
                violations.append(PolicyViolation(
                    category=self.category,
                    verdict=PolicyVerdict.BLOCK,
                    policy_id=self.policy_id,
                    message=f"Command not whitelisted: '{cmd_name}'",
                    evidence={"command": cmd},
                    remediation=f"Add '{cmd_name}' to whitelist or use approved alternative",
                    severity="high"
                ))
        
        return violations


class MaxFileSizePolicy(Policy):
    """Warn on files exceeding size limit"""
    
    def __init__(self, max_lines: int = 500):
        super().__init__("max-file-size", PolicyCategory.CODING_STANDARDS)
        self.max_lines = max_lines
    
    def evaluate(self, context: Dict[str, Any]) -> List[PolicyViolation]:
        violations = []
        
        code_changes = context.get("code_changes", {})
        for file_path, code in code_changes.items():
            line_count = len(code.split('\n'))
            if line_count > self.max_lines:
                violations.append(PolicyViolation(
                    category=self.category,
                    verdict=PolicyVerdict.WARN,
                    policy_id=self.policy_id,
                    message=f"File exceeds {self.max_lines} lines: {file_path} ({line_count} lines)",
                    evidence={"file": file_path, "lines": line_count},
                    remediation="Consider breaking into smaller modules",
                    severity="low"
                ))
        
        return violations


class NoDirectDatabaseAccessPolicy(Policy):
    """Enforce repository pattern for database access"""
    
    def __init__(self):
        super().__init__("no-direct-db-access", PolicyCategory.ARCHITECTURE)
        self.forbidden_imports = [
            "import sqlite3",
            "import psycopg2",
            "import mysql.connector",
            "from sqlalchemy import"
        ]
    
    def evaluate(self, context: Dict[str, Any]) -> List[PolicyViolation]:
        violations = []
        
        code_changes = context.get("code_changes", {})
        for file_path, code in code_changes.items():
            # Skip repository layer files
            if "repository" in file_path.lower() or "dao" in file_path.lower():
                continue
            
            for forbidden in self.forbidden_imports:
                if forbidden in code:
                    violations.append(PolicyViolation(
                        category=self.category,
                        verdict=PolicyVerdict.BLOCK,
                        policy_id=self.policy_id,
                        message=f"Direct database access detected in {file_path}",
                        evidence={"file": file_path, "import": forbidden},
                        remediation="Use repository pattern for database access",
                        severity="high"
                    ))
        
        return violations


# Global policy engine instance
_policy_engine = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    """Get global policy engine instance"""
    return _policy_engine


def initialize_default_policies():
    """Register default policies"""
    engine = get_policy_engine()
    engine.register_policy(NoSecretsInCodePolicy())
    engine.register_policy(CommandWhitelistPolicy())
    engine.register_policy(MaxFileSizePolicy(max_lines=500))
    engine.register_policy(NoDirectDatabaseAccessPolicy())
