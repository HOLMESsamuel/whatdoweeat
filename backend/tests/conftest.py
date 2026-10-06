import os
import sys

# The app imports itself as `src.*` (see main.py); make that resolvable
# however pytest is launched.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
