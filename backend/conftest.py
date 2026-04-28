import sys
from pathlib import Path

# Ensure the backend directory is on sys.path so tests can import market.*
sys.path.insert(0, str(Path(__file__).parent))
