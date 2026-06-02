import sys
import os
sys.path.append(os.path.abspath('.'))
import pickle
from utils_simplified import build_ddm, build_citygraph

# Just try to build a tiny toy ddm to see if it pickles properly
print("Running tiny DDM test...")
cg = build_citygraph('configs/profile_p1.yaml', None)
import datetime
target_time = datetime.datetime.now().replace(hour=13, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
try:
    ddm = build_ddm('configs/profile_p1.yaml', cg, target_time, 'scratch/test_ddm.pkl')
    print("Success pickling DDM!")
except Exception as e:
    print("ERROR PICKLING DDM:", e)
