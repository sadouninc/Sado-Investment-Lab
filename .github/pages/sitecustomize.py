"""Pages-only Python path bootstrap.

The canonical Pages workflow executes selected builders by script path while
setting ``PYTHONPATH=.github/pages`` so local Pages modules remain importable.
Python imports ``sitecustomize`` from that path at interpreter startup; add the
repository root without changing builder semantics so canonical ``scripts``
modules are also resolvable.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
root = str(ROOT)
if root not in sys.path:
    sys.path.insert(0, root)
