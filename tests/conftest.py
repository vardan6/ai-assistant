import sys
from pathlib import Path

# Make the project root importable as `app` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
