import yaml
import pickle
from typing import Optional
from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from datetime import datetime

# =========================================================
# City Graph
# =========================================================

def build_citygraph(yaml_file: str, pkl_path: Optional[str] = None) -> CityGraph:
    print(f"[INFO] Building CityGraph from YAML file: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) 
    cg_config = config.get('city_graph', {})
    if 'bbox' in cg_config and isinstance(cg_config['bbox'], list):
        cg_config['bbox'] = tuple(cg_config['bbox'])
    cg = CityGraph(**cg_config)
    
    if pkl_path:
        import os
        os.makedirs(os.path.dirname(pkl_path), exist_ok=True)
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

# =========================================================
# Direct Demand Model
# =========================================================

def build_ddm(yaml_file: str, cg: CityGraph, target_time: Optional[datetime], pkl_path: Optional[str] = None) -> DirectDemandSampler:
    print(f"[INFO] Building DirectDemandSampler from YAML file: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
        
    ddm_config_data = config_data.get('ddm', {})
    
    ddm_config = DDMConfig(
        alpha=ddm_config_data.get('alpha', 0.6),
        beta=ddm_config_data.get('beta', 0.4),
        target_time=target_time
    )
    
    # use_cache=False to avoid relying on pre-existing DDM internal cache
    ddm = DirectDemandSampler(city=cg, config=ddm_config, verbose=True, use_cache=False)
    if pkl_path:
        import os
        os.makedirs(os.path.dirname(pkl_path), exist_ok=True)
        print(f"[INFO] Serializing DirectDemandSampler to pickle file: {pkl_path}")
        with open(pkl_path, 'wb') as f:
            pickle.dump(ddm, f)
        print(f"[INFO] DirectDemandSampler successfully serialized to pickle file: {pkl_path}")
            
    return ddm

def reuse_ddm(pkl_file: str) -> DirectDemandSampler:
    print(f"[INFO] Reusing DirectDemandSampler from pickle file: {pkl_file}")
    with open(pkl_file, 'rb') as f:
        ddm = pickle.load(f)
    return ddm


