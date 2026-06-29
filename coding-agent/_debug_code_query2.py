"""Debug the retriever code query with the exact test setup."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(__file__))
tmpdir = tempfile.mkdtemp()
cache_dir = os.path.join(tmpdir, '.cache')
os.makedirs(cache_dir, exist_ok=True)

from repository.kg_types import NodeType, RelationType, KGNode, KGRelation
from repository.knowledge_graph import KnowledgeGraph
from repository.indexer import Indexer
from repository.intelligence import RepositoryIntelligence
from repository.retriever import Retriever

# Recreate the exact setup from section 16 and 17
intel = RepositoryIntelligence(tmpdir, os.path.join(cache_dir, "intel_test"))
intel_kg = intel.kg
intel_kg.clear()

# Same entities as the test
entities = [
    KGNode(id="module:auth/login.py", type=NodeType.MODULE, name="login",
           file_path="auth/login.py", line=1),
    KGNode(id="function:login", type=NodeType.FUNCTION, name="login",
           file_path="auth/login.py", line=5, signature="def login()"),
    KGNode(id="function:validate", type=NodeType.FUNCTION, name="validate",
           file_path="auth/login.py", line=15, signature="def validate()"),
    KGNode(id="class:LoginForm", type=NodeType.CLASS, name="LoginForm",
           file_path="auth/login.py", line=25, signature="class LoginForm"),
    KGNode(id="module:auth/register.py", type=NodeType.MODULE, name="register",
           file_path="auth/register.py", line=1),
    KGNode(id="function:register", type=NodeType.FUNCTION, name="register",
           file_path="auth/register.py", line=5, signature="def register()"),
    KGNode(id="module:payment/service.py", type=NodeType.MODULE, name="service",
           file_path="payment/service.py", line=1),
    KGNode(id="function:process_payment", type=NodeType.FUNCTION, name="process_payment",
           file_path="payment/service.py", line=10, signature="def process_payment()"),
    KGNode(id="module:models/user.py", type=NodeType.MODULE, name="user",
           file_path="models/user.py", line=1),
    KGNode(id="class:User", type=NodeType.CLASS, name="User",
           file_path="models/user.py", line=5, signature="class User"),
    KGNode(id="function:create_user", type=NodeType.FUNCTION, name="create_user",
           file_path="models/user.py", line=20, signature="def create_user()"),
]
for e in entities:
    intel_kg.add_node(e)

# Add relations
relations = [
    KGRelation("function:login", "function:validate", RelationType.CALLS, "auth/login.py", 6),
    KGRelation("function:login", "function:create_user", RelationType.CALLS, "auth/login.py", 7),
    KGRelation("function:register", "function:create_user", RelationType.CALLS, "auth/register.py", 6),
    KGRelation("function:process_payment", "class:User", RelationType.USES, "payment/service.py", 11),
    KGRelation("module:auth/login.py", "module:models/user.py", RelationType.DEPENDS_ON, "auth/login.py", 2),
    KGRelation("module:auth/register.py", "module:models/user.py", RelationType.DEPENDS_ON, "auth/register.py", 2),
    KGRelation("module:payment/service.py", "module:models/user.py", RelationType.DEPENDS_ON, "payment/service.py", 3),
]
for r in relations:
    intel_kg.add_relation(r)

print(f"KG has {intel_kg.node_count()} nodes, {intel_kg.relation_count()} relations")

# Test find_in_file
nodes = intel_kg.find_in_file("auth/login.py")
print(f"find_in_file('auth/login.py'): {[n.name for n in nodes]}")

# Create retriever and test
retriever = Retriever(intel)
print(f"retriever.kg is intel.kg: {retriever.kg is intel.kg}")
print(f"retriever.kg node_count: {retriever.kg.node_count()}")

result = retriever.query("auth/login.py", "code")
print(f"Code query results: {len(result.results)}")
print(f"Result error: {result.error}")
for r in result.results:
    print(f"  - {r}")
