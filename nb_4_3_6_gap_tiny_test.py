"""Tiny smoke test for PheromoneMatrix.draw_gaps -- the signed demand-service gap field added for
Visual 3 of nb_4_3_6_lamarckian.ipynb. No simulation: builds a synthetic gaps dict on stub edges
and checks the diverging draw renders correctly. Runs in <1s.

Run:  python nb_4_3_6_gap_tiny_test.py
"""
from PIL import Image
from utils.pheromone import PheromoneMatrix

# context = ((left_lon, top_lat), (right_lon, bottom_lat)) -- matches CityGraph.get_bounds()
CTX = ((0.0, 1.0), (1.0, 0.0))


class _Node:
    def __init__(self, lon, lat):
        self.lon = lon
        self.lat = lat


class _Edge:
    """Minimal stand-in: draw_gaps and _edge_key only need .start/.end with .lon/.lat."""
    def __init__(self, x1, y1, x2, y2):
        self.start = _Node(x1, y1)
        self.end = _Node(x2, y2)


def _matrix(edges):
    return PheromoneMatrix(all_edges=edges, config={})


def test_draw_gaps_renders_signed_field():
    edges = [_Edge(0.1, 0.1, 0.9, 0.1), _Edge(0.1, 0.5, 0.9, 0.5), _Edge(0.1, 0.9, 0.9, 0.9)]
    m = _matrix(edges)
    m.gaps = {edges[0]: 0.40, edges[1]: -0.25, edges[2]: 0.0}  # underserved / oversupplied / balanced
    base = Image.new("RGB", (256, 256), "white")
    out = m.draw_gaps(CTX, base)
    assert isinstance(out, Image.Image), "must return an Image"
    assert out.size == (256, 256), "must preserve image size"
    assert out is not base, "must not return the caller's image object"
    assert out.tobytes() != base.tobytes(), "must actually draw the gap field"


def test_draw_gaps_signs_use_distinct_colors():
    # A purely-underserved field (red) must differ pixel-for-pixel from a purely-oversupplied one (blue).
    e = _Edge(0.1, 0.5, 0.9, 0.5)
    m = _matrix([e])
    base = Image.new("RGB", (128, 128), "white")
    m.gaps = {e: 0.5}
    red = m.draw_gaps(CTX, base)
    m.gaps = {e: -0.5}
    blue = m.draw_gaps(CTX, base)
    assert red.tobytes() != blue.tobytes(), "positive vs negative gap must render differently"


def test_draw_gaps_threshold_suppresses_weak_edges():
    edges = [_Edge(0.1, 0.3, 0.9, 0.3), _Edge(0.1, 0.7, 0.9, 0.7)]
    m = _matrix(edges)
    m.gaps = {edges[0]: 0.5, edges[1]: 0.05}  # one strong, one weak (0.1 of the max)
    base = Image.new("RGB", (200, 200), "white")
    full = m.draw_gaps(CTX, base, threshold=0.0)
    thresholded = m.draw_gaps(CTX, base, threshold=0.5)  # drops the weak edge
    assert full.tobytes() != thresholded.tobytes(), "threshold must suppress weak edges"
    assert thresholded.tobytes() != base.tobytes(), "the strong edge must still draw"


def test_draw_gaps_empty_is_noop_copy():
    m = _matrix([_Edge(0.1, 0.1, 0.9, 0.9)])
    m.gaps = {}
    base = Image.new("RGB", (128, 128), "white")
    out = m.draw_gaps(CTX, base)
    assert out.size == (128, 128)
    assert out is not base, "empty gaps must still return a copy, not the original"
    assert out.tobytes() == base.tobytes(), "no gaps -> unchanged"


def test_draw_gaps_rejects_non_square():
    m = _matrix([_Edge(0.1, 0.1, 0.9, 0.9)])
    m.gaps = {}
    try:
        m.draw_gaps(CTX, Image.new("RGB", (100, 50), "white"))
    except ValueError:
        return
    raise AssertionError("draw_gaps should reject non-square images")


if __name__ == "__main__":
    test_draw_gaps_renders_signed_field()
    test_draw_gaps_signs_use_distinct_colors()
    test_draw_gaps_threshold_suppresses_weak_edges()
    test_draw_gaps_empty_is_noop_copy()
    test_draw_gaps_rejects_non_square()
    print("OK: draw_gaps tiny test passed (5 checks)")
