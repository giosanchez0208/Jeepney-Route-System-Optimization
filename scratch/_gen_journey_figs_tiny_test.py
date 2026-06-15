"""Smoke test for _gen_journey_figs.py — fast, no full figure generation.

Verifies the two fragile pieces: (1) a two-route transfer journey is still
discoverable, and (2) the phase-boundary / 3D-render plumbing still works.

    ./.venv/Scripts/python.exe scratch/_gen_journey_figs_tiny_test.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "_gjf", os.path.join(os.path.dirname(__file__), "_gen_journey_figs.py"))
gjf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gjf)


def main():
    city, sampler, config, routes, tg, o, d, journey = gjf.find_transfer_scenario()
    sig = gjf.collapsed_sig(journey)
    assert len(routes) == 2, routes
    assert "TR" in sig, sig
    assert sig.count("RI") >= 2, sig
    assert len(journey) > 0

    bounds = gjf.phase_boundaries(journey)
    assert len(bounds) == 5, bounds
    ks = [k for k, _, _ in bounds]
    assert ks == sorted(ks) and ks[-1] == len(journey), ks
    assert [on for _, _, on in bounds] == [0, 1, 0, 1, 0], bounds

    phases, key = gjf.journey_phases(journey)
    assert sum(1 for p in phases if p[0] == "ride") >= 2, phases
    assert key["board"] is not None and key["transfer"] is not None

    img = gjf._3d_image(tg, journey[:bounds[1][0]])  # render one partial-journey 3D frame
    assert img.width > 100 and img.height > 100, img.size

    print("PASS  sig=%s  edges=%d  3d=%dx%d" % (sig, len(journey), img.width, img.height))


if __name__ == "__main__":
    main()
