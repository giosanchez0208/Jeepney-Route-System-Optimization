import yaml
import pickle
from typing import Optional
from utils.city_graph import CityGraph

def build_citygraph(yaml_file: str, pkl_path: Optional[str] = None) -> CityGraph:

    print(f"[INFO] Building CityGraph from YAML file: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) 
    cg_config = config.get('city_graph', {})
    if 'bbox' in cg_config and isinstance(cg_config['bbox'], list):
        cg_config['bbox'] = tuple(cg_config['bbox'])
    cg = CityGraph(**cg_config)
    
    if pkl_path:
        print(f"[INFO] Serializing CityGraph to pickle file: {pkl_path}")
        with open(pkl_path, 'wb') as f:
            pickle.dump(cg, f)
        print(f"[INFO] CityGraph successfully serialized to pickle file: {pkl_path}")
            
    return cg

def reuse_citygraph(pkl_file: str) -> CityGraph:
    print(f"[INFO] Reusing CityGraph from pickle file: {pkl_file}")
    with open(pkl_file, 'rb') as f:
        cg = pickle.load(f)
    return cg

if __name__ == "__main__":
    import os
    
    yaml_file = "configs/profile_p1.yaml"
    pkl_file = "test_citygraph.pkl"

    cg1 = build_citygraph(yaml_file, pkl_file)
    cg2 = reuse_citygraph(pkl_file)
    
    # Clean up the test pickle file
    if os.path.exists(pkl_file):
        os.remove(pkl_file)
