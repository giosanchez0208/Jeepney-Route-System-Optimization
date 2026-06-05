"""Machine 1 -- runs 3 final optimizations in parallel. Press play:  python run_machine_1.py

Launches p1, p2, p3 at once, auto-sizes workers to share this machine's cores, logs each to
logs/opt_pN.log, and waits. Keep the window open until it prints BATCH COMPLETE.
"""
from opt_run import run_batch

if __name__ == "__main__":
    run_batch(["p1", "p2", "p3"])
