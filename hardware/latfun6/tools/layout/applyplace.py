"""Apply the checked candidate's PCB document into the project (EDA must be closed; Project.write backs up + verifies)."""
import sys
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
import eprj_core as ec
SRC = __import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj')
cand = ec.Project(sys.argv[1] if len(sys.argv) > 1 else 'cand.eprj')
P = ec.Project(SRC)
P.write(cand.text, sys.argv[2] if len(sys.argv) > 2 else 'tidy_labels')
print('written')
