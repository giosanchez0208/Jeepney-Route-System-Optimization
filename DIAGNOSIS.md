# Diagnostic Report: Route Cell Exceptions

**Status: FIXED**

## CELL 15: Route Validation Tests

### Issue: ALL tests fail with "Invalid edge layer" error

### Root Cause: Shallow Copy Side Effects

The test cases used shallow copies via `copy.copy()`, causing modifications to later test paths to corrupt earlier ones:

1. Create `layer_path = copy.copy(valid_path)` - shallow copy, same edge objects
2. Execute `set_layer(layer_path[2], 1)` - modifies e3 IN PLACE
3. Now `valid_path[2]` also has layer=1 (same object)
4. All subsequent tests reference corrupted edges

### Fix Applied

Changed all test cases to use `copy.deepcopy(base_path)`:

```python
base_path = [e1, e2, e3, e4]

valid_path = copy.deepcopy(base_path)
open_path = copy.deepcopy(base_path)[:-1]
broken_path = copy.deepcopy(base_path)
...
```

Each test now gets its own independent edge objects with proper layer attributes.

---

## CELL 16: Full Integration (Iligan Route Generation)

### Issue: Generate Iligan Route (5 points) fails

**Error:** `[CITY GRAPH] No path found between {start_node} and {end_node}.`

### Root Cause: Graph Connectivity Constraints

The `find_shortest_path()` method only traverses drivable edges (arterial roads from OSM). Some randomly sampled nodes aren't connected by drivable-only paths.

### Fix Applied

Added retry logic to RouteGenerator.generate() with max_retries parameter (default 10):

```python
def generate(self, n_points: int = 4, max_retries: int = 10) -> Route:
    for attempt in range(max_retries):
        nodes = [self.sampler.get_point() for _ in range(n_points)]
        # Try to build route with these nodes
        # If any segment fails, break and retry with new nodes
        
    # Only raise error after all retries exhausted
```

This ensures that if one set of randomly sampled points can't be connected via drivable roads, the algorithm retries with different points. Most routing attempts succeed on first try if the drivable network is well-connected.

---

## Summary of Changes

### diagnostic.ipynb
- **Cell 15:** Replaced shallow copies with deep copies to prevent edge object corruption

### utils/route.py
- **RouteGenerator.generate():** Added retry logic with max_retries parameter (default 10)
  - Handles cases where sampled nodes lack drivable paths between them
  - Provides informative logging when verbose mode is enabled
  - Only raises error after exhausting all retry attempts
