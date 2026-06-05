"""Final optimization p8_1pm -- temporal-DDM robustness (ddm_1pm.pkl). Run on one machine:  python opt_p8_1pm.py"""
from opt_run import run_profile

if __name__ == "__main__":
    run_profile("p8_1pm", seed=1, ddm_pkl="rnd/pkl/ddm_1pm.pkl")
