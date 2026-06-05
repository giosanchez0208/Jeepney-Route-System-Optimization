"""Final optimization p5 -- reproducibility run (8am DDM, seed varies). Run on one machine:  python opt_p5.py"""
from opt_run import run_profile

if __name__ == "__main__":
    run_profile("p5", seed=5)
