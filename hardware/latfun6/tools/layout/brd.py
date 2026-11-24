import sys; sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
from eprj_core import Board, bbox
B=Board(__import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj'))
