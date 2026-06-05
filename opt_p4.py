"""Final optimization p4 -- reproducibility run (8am DDM, seed varies). Run on one machine:  python opt_p4.py"""
from opt_run import run_profile

if __name__ == "__main__":
    run_profile("p4", seed=4)
