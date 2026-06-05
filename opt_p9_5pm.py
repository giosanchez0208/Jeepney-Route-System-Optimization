"""Final optimization p9_5pm -- temporal-DDM robustness (ddm_5pm.pkl). Run on one machine:  python opt_p9_5pm.py"""
from opt_run import run_profile

if __name__ == "__main__":
    run_profile("p9_5pm", seed=1, ddm_pkl="rnd/pkl/ddm_5pm.pkl")
