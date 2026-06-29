"""
GOAL ENGINE

Converts vague user requests into structured engineering goals.

Instead of:
    "Build login page"

Creates:
    Goal: Implement user authentication interface
    Success Criteria: [Users can log in, Errors shown, Security validated]
    Constraints: [Must use existing auth API, Mobile responsive]
    Assumptions: [Auth API exists, Database has user table]
    Risks: [Security vulnerability, Session management]
    Dependencies: [Auth service, Database, Frontend framework]
    Acceptance Tests: [Can login with valid creds, Cannot with invalid, ...]

This ensures every worker understands the objective clearly.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EngineeringGoal:
    """A structured engineering goal with all necessary context."""
    
    # Core
    original_request: str
    goal: str
    type: str  # "feature", "bugfix", "refactor", "optimization", "security"
    
    # Success definition
    success_criteria: list[str] = field(default_factory=list)
    acceptance_tests: list[str] = field(default_factory=list)
    
    # Constraints and context
    constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    
    # Risk and impact
    risks: list[str] = field(default_factory=list)
    affected_systems: list[str] = field(default_factory=list)
    
    # Execution guidance
    approach: str = ""
    estimated_effort: str = "medium"
    priority: str = "normal"
    
    # Metadata
    confidence: float = 0.5
    clarification_needed: bool = False
    clarifying_questions: list[str] = field(default_factory=list)


class GoalEngine:
    """
    Converts vague requests into structured engineering goals.
    
    This is the first step in intelligent execution - understanding
    what we're actually trying to accomplish and why.
    """
    
    def __init__(self, brain=None, repo_intelligence=None):
        self.brain = brain
        self.repo_intel = repo_intelligence
    
    def structure_goal(self, request: str, context: dict = None) -> EngineeringGoal:
        """
        Convert a user request into a structured goal.
        
        Args:
            request: Raw user request (e.g., "add login page")
            context: Additional context (files, concepts, etc.)
        
        Returns:
            EngineeringGoal with all structured information
        """
        print(f"[GoalEngine] Structuring goal: {request[:60]}...")
        
        # 1. Classify goal type
        goal_type = self._classify_goal_type(request)
        
        # 2. Extract core goal
        core_goal = self._extract_core_goal(request, goal_type)
        
        # 3. Define success criteria
        success_criteria = self._define_success_criteria(request, goal_type, context)
        
        # 4. Generate acceptance tests
        acceptance_tests = self._generate_acceptance_tests(request, goal_type)
        
        # 5. Identify constraints
        constraints = self._identify_constraints(request, context)
        
        # 6. Document assumptions
        assumptions = self._document_assumptions(request, goal_type, context)
        
        # 7. Find dependencies
        dependencies = self._find_dependencies(request, context)
        
        # 8. Assess risks
        risks = self._assess_risks(request, goal_type)
        
        # 9. Identify affected systems
        affected_systems = self._identify_affected_systems(request, context)
        
        # 10. Recommend approach
        approach = self._recommend_approach(request, goal_type)
        
        # 11. Estimate effort
        effort = self._estimate_effort(request, goal_type, len(dependencies))
        
        goal = EngineeringGoal(
            original_request=request,
            goal=core_goal,
            type=goal_type,
            success_criteria=success_criteria,
            acceptance_tests=acceptance_tests,
            constraints=constraints,
            assumptions=assumptions,
            dependencies=dependencies,
            risks=risks,
            affected_systems=affected_systems,
            approach=approach,
            estimated_effort=effort
        )
        
        # Check if clarification needed
        if len(success_criteria) < 2 or len(assumptions) > 5:
            goal.clarification_needed = True
            goal.clarifying_questions = self._generate_clarifying_questions(goal)
        
        print(f"  Goal Type: {goal_type}")
        print(f"  Success Criteria: {len(success_criteria)}")
        print(f"  Dependencies: {len(dependencies)}")
        print(f"  Risks: {len(risks)}")
        
        return goal
    
    def _classify_goal_type(self, request: str) -> str:
        """Classify the type of engineering goal."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["fix", "bug", "error", "broken", "crash"]):
            return "bugfix"
        elif any(word in request_lower for word in ["refactor", "clean", "reorganize", "improve"]):
            return "refactor"
        elif any(word in request_lower for word in ["optimize", "performance", "faster", "slow"]):
            return "optimization"
        elif any(word in request_lower for word in ["security", "vulnerability", "auth", "permission"]):
            return "security"
        elif any(word in request_lower for word in ["add", "create", "implement", "build", "new"]):
            return "feature"
        else:
            return "feature"
    
    def _extract_core_goal(self, request: str, goal_type: str) -> str:
        """Extract the core goal from the request."""
        request_lower = request.lower()
        
        # Pattern-based extraction
        if goal_type == "bugfix":
            return f"Fix: {request}"
        elif goal_type == "refactor":
            return f"Refactor: {request}"
        elif goal_type == "optimization":
            return f"Optimize: {request}"
        elif goal_type == "security":
            return f"Security: {request}"
        else:
            # For features, try to make it more specific
            if "login" in request_lower:
                return "Implement user authentication interface"
            elif "dashboard" in request_lower:
                return "Build user dashboard with key metrics"
            elif "api" in request_lower:
                return f"Implement API endpoint: {request}"
            else:
                return request
    
    def _define_success_criteria(self, request: str, goal_type: str, context: dict = None) -> list[str]:
        """Define what success looks like."""
        criteria = []
        request_lower = request.lower()
        
        if goal_type == "bugfix":
            criteria.extend([
                "Error no longer occurs",
                "Root cause identified and fixed",
                "Tests pass",
                "No regression in other functionality"
            ])
        
        elif goal_type == "feature":
            if "login" in request_lower:
                criteria.extend([
                    "Users can authenticate with valid credentials",
                    "Invalid credentials show appropriate error",
                    "Session management works correctly",
                    "Password security requirements met",
                    "UI is responsive and accessible"
                ])
            elif "api" in request_lower:
                criteria.extend([
                    "Endpoint responds with correct status codes",
                    "Response format matches specification",
                    "Error handling is comprehensive",
                    "Authentication/authorization enforced",
                    "Performance meets requirements"
                ])
            else:
                criteria.extend([
                    "Feature works as described",
                    "Edge cases handled",
                    "Tests pass",
                    "Documentation updated"
                ])
        
        elif goal_type == "refactor":
            criteria.extend([
                "Code is cleaner and more maintainable",
                "No functional changes (behavior preserved)",
                "Tests still pass",
                "Performance not degraded"
            ])
        
        elif goal_type == "optimization":
            criteria.extend([
                "Performance improved by measurable amount",
                "No functionality broken",
                "Tests pass",
                "Memory usage acceptable"
            ])
        
        return criteria
    
    def _generate_acceptance_tests(self, request: str, goal_type: str) -> list[str]:
        """Generate acceptance tests."""
        tests = []
        request_lower = request.lower()
        
        if "login" in request_lower:
            tests.extend([
                "Can login with valid username and password",
                "Cannot login with invalid credentials",
                "Error message shown for empty fields",
                "Password is masked in input field",
                "Session persists after login",
                "Can logout successfully"
            ])
        
        elif "api" in request_lower:
            tests.extend([
                "GET request returns 200 for valid ID",
                "GET request returns 404 for invalid ID",
                "POST request creates resource",
                "PUT request updates resource",
                "DELETE request removes resource",
                "Unauthorized requests return 401"
            ])
        
        elif goal_type == "bugfix":
            tests.extend([
                "Original error scenario no longer fails",
                "Related functionality still works",
                "Edge cases handled"
            ])
        
        return tests
    
    def _identify_constraints(self, request: str, context: dict = None) -> list[str]:
        """Identify constraints on the implementation."""
        constraints = []
        request_lower = request.lower()
        
        # Technical constraints
        if self.repo_intel and self.repo_intel.architecture:
            frameworks = self.repo_intel.architecture.frameworks
            if frameworks:
                constraints.append(f"Must use existing framework: {', '.join(frameworks[:2])}")
        
        # Common constraints
        constraints.extend([
            "Must maintain backward compatibility",
            "Must follow existing code style",
            "Must include tests"
        ])
        
        # Security constraints
        if any(word in request_lower for word in ["auth", "login", "password", "security"]):
            constraints.extend([
                "Must follow security best practices",
                "Must handle sensitive data securely",
                "Must implement proper input validation"
            ])
        
        # Performance constraints
        if any(word in request_lower for word in ["api", "endpoint", "service"]):
            constraints.append("Response time should be < 200ms for 95th percentile")
        
        return constraints
    
    def _document_assumptions(self, request: str, goal_type: str, context: dict = None) -> list[str]:
        """Document assumptions being made."""
        assumptions = []
        request_lower = request.lower()
        
        if "login" in request_lower or "auth" in request_lower:
            assumptions.extend([
                "Authentication API/service already exists",
                "Database has user table with credentials",
                "Session management infrastructure exists"
            ])
        
        if "api" in request_lower:
            assumptions.extend([
                "Database schema supports required data",
                "API framework is set up",
                "Authentication middleware exists"
            ])
        
        if goal_type == "refactor":
            assumptions.extend([
                "Comprehensive test coverage exists",
                "Behavior should remain unchanged",
                "No new features being added"
            ])
        
        return assumptions
    
    def _find_dependencies(self, request: str, context: dict = None) -> list[str]:
        """Find dependencies for this goal."""
        dependencies = []
        request_lower = request.lower()
        
        # Use repository intelligence if available
        if self.repo_intel and context:
            if context.get("concepts"):
                dependencies.extend(context["concepts"])
        
        # Pattern-based dependencies
        if "login" in request_lower:
            dependencies.extend(["Authentication Service", "User Database", "Session Management"])
        
        if "api" in request_lower:
            dependencies.extend(["API Framework", "Database", "Authentication"])
        
        if "database" in request_lower:
            dependencies.extend(["Database Schema", "ORM", "Migrations"])
        
        if "frontend" in request_lower or "ui" in request_lower:
            dependencies.extend(["Frontend Framework", "State Management", "Styling"])
        
        return list(set(dependencies))  # Remove duplicates
    
    def _assess_risks(self, request: str, goal_type: str) -> list[str]:
        """Assess risks associated with this goal."""
        risks = []
        request_lower = request.lower()
        
        if goal_type == "security" or any(word in request_lower for word in ["auth", "security"]):
            risks.extend([
                "Security vulnerability if not implemented correctly",
                "Potential for unauthorized access",
                "Sensitive data exposure"
            ])
        
        if "database" in request_lower or "migration" in request_lower:
            risks.extend([
                "Data loss if migration fails",
                "Downtime during migration",
                "Performance impact"
            ])
        
        if goal_type == "refactor":
            risks.extend([
                "Regression in functionality",
                "Breaking existing integrations",
                "Time spent without user-visible value"
            ])
        
        if "api" in request_lower:
            risks.extend([
                "Breaking API clients",
                "Performance degradation",
                "Backward compatibility issues"
            ])
        
        return risks
    
    def _identify_affected_systems(self, request: str, context: dict = None) -> list[str]:
        """Identify systems that will be affected."""
        affected = []
        request_lower = request.lower()
        
        # Use repository intelligence
        if self.repo_intel and hasattr(self.repo_intel, 'find_concepts_for_task'):
            concepts = self.repo_intel.find_concepts_for_task(request)
            affected.extend([c.name for c in concepts])
        
        # Pattern-based
        system_map = {
            "auth": ["Authentication", "Authorization", "Security"],
            "login": ["Authentication", "Frontend", "Session Management"],
            "database": ["Database", "ORM", "Data Layer"],
            "api": ["API Layer", "Backend Services"],
            "frontend": ["Frontend", "UI", "User Experience"],
            "cache": ["Caching Layer", "Performance"],
        }
        
        for keyword, systems in system_map.items():
            if keyword in request_lower:
                affected.extend(systems)
        
        return list(set(affected))
    
    def _recommend_approach(self, request: str, goal_type: str) -> str:
        """Recommend implementation approach."""
        if goal_type == "bugfix":
            return "1) Reproduce bug, 2) Identify root cause, 3) Fix with test, 4) Verify no regression"
        elif goal_type == "refactor":
            return "1) Ensure test coverage, 2) Refactor incrementally, 3) Verify tests pass at each step"
        elif goal_type == "security":
            return "1) Security review of design, 2) Implement with security best practices, 3) Security audit before deployment"
        else:
            return "1) Design with constraints in mind, 2) Implement incrementally, 3) Test thoroughly, 4) Deploy with monitoring"
    
    def _estimate_effort(self, request: str, goal_type: str, dependency_count: int) -> str:
        """Estimate effort required."""
        base_effort = {
            "bugfix": "small",
            "refactor": "medium",
            "optimization": "medium",
            "security": "large",
            "feature": "medium"
        }.get(goal_type, "medium")
        
        # Adjust based on dependencies
        if dependency_count > 5:
            if base_effort == "small":
                return "medium"
            elif base_effort == "medium":
                return "large"
        
        return base_effort
    
    def _generate_clarifying_questions(self, goal: EngineeringGoal) -> list[str]:
        """Generate questions to clarify ambiguous goals."""
        questions = []
        
        if len(goal.success_criteria) < 2:
            questions.append("What specific outcomes define success for this task?")
        
        if not goal.dependencies:
            questions.append("What existing systems or components does this depend on?")
        
        if len(goal.assumptions) > 5:
            questions.append("Can you confirm these assumptions are correct?")
        
        if goal.type == "feature" and not goal.acceptance_tests:
            questions.append("What are the key user scenarios that should work?")
        
        return questions
