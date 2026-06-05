"""Machine 3 -- runs 3 final optimizations in parallel. Press play:  python run_machine_3.py

Launches p7 (reproducibility) + p8_1pm, p9_5pm (temporal robustness) at once, auto-sizes workers
to share this machine's cores, logs each to logs/opt_*.log, and waits. Keep the window open until
it prints BATCH COMPLETE.
"""
from opt_run import run_batch

if __name__ == "__main__":
    run_batch(["p7", "p8_1pm", "p9_5pm"])
