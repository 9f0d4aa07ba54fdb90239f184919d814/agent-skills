"""Debug the retriever code query."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(__file__))
tmpdir = tempfile.mkdtemp()
cache_dir = os.path.join(tmpdir, '.cache')

from repository.intelligence import RepositoryIntelligence
intel = RepositoryIntelligence(tmpdir, os.path.join(cache_dir, 'intel_test'))
intel_kg = intel.kg
intel_kg.clear()

from repository.kg_types import NodeType, RelationType, KGNode, KGRelation

# Add test entities (same as test)
entities = [
    KGNode(id='function:login', type=NodeType.FUNCTION, name='login',
           file_path='auth/login.py', line=5, signature='def login()'),
    KGNode(id='function:validate', type=NodeType.FUNCTION, name='validate',
           file_path='auth/login.py', line=15, signature='def validate()'),
    KGNode(id='class:LoginForm', type=NodeType.CLASS, name='LoginForm',
           file_path='auth/login.py', line=25, signature='class LoginForm'),
]
for e in entities:
    intel_kg.add_node(e)

# Test find_in_file
print('Nodes in auth/login.py:', [n.name for n in intel_kg.find_in_file('auth/login.py')])
print('Nodes in login.py:', [n.name for n in intel_kg.find_in_file('login.py')])

# Test retriever code query
from repository.retriever import Retriever
retriever = Retriever(intel)
result = retriever.query('auth/login.py', 'code')
print(f'Code query results: {len(result.results)}')
for r in result.results:
    print(f'  - {r.get("type")}: {r.get("name")} @ {r.get("file_path")}')
