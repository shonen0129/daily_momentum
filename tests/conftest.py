import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'stock_comp_2026/strategies/dm_trainonly'))
sys.path.insert(0,str(ROOT/'stock_comp_2026'))
