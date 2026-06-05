"""Machine 2 -- runs 3 final optimizations in parallel. Press play:  python run_machine_2.py

Launches p4, p5, p6 at once, auto-sizes workers to share this machine's cores, logs each to
logs/opt_pN.log, and waits. Keep the window open until it prints BATCH COMPLETE.
"""
from opt_run import run_batch

if __name__ == "__main__":
    run_batch(["p4", "p5", "p6"])
