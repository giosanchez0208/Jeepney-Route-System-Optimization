# STANDARDS.md

## 1. Naming Conventions
* Classes utilize `PascalCase`.
* Functions and methods utilize `snake_case`.
* Constants utilize `UPPER_SNAKE_CASE`.
* Private module-level helpers and protected attributes utilize a single leading underscore (e.g., `_helper_function`).

## 2. Type Hinting and Signatures
* Require strict type hints for all parameters.
* Require explicit return type annotations for all methods, including `-> None`.
* Import `annotations` from `__future__` to allow forward referencing.
* Use `Optional[Type]` with an explicit `None` default for nullable parameters.

## 3. Validation and Exception Handling
* Execute input checks immediately for `None`, type correctness, boundary ranges, and spatial constraints.
* Handle default mutable arguments safely (e.g., `self.list = arg if arg is not None else []`).
* Raise standard `ValueError`, `TypeError`, or `AttributeError` for invalid states.
* Prefix all exception strings with a bracketed, all-caps class identifier (e.g., `[NODE]`, `[DIR EDGE]`).

## 4. Class Methods and Magic Methods
* Implement a `__str__` method for every class providing informative, human-readable output including the class name, unique ID, and key fields.
* Generate internal hexadecimal string UUIDs for default object identification.
* Utilize Python 3.10 structural pattern matching (`match` / `case`) for complex conditional logic.
* Utilize f-strings for all string formatting.

## 5. State Management and Execution
* Object states and coordinates may mutate post-instantiation via explicit class methods.
* Control execution tracing using a boolean `verbose` flag. Do not use external logger modules.
* Utilize `collections.defaultdict` for coordinate-based lookup tables to achieve O(1) intersection queries.

## 6. Visualization Primitives
* Require a standard `draw` method signature across spatial classes.
* The output of any visualization method must strictly evaluate to `-> Image.Image`.
* Enforce square aspect ratios for base images. Raise a `ValueError` if `image.width != image.height`.
* Calculate Cartesian coordinates by linearly mapping `(lon, lat)` limits to pixel positions.

# STANDARDS_NOTEBOOK.md

#### 1. Zero-Footprint Validation
* **Exclusive Authority:** All status reporting, success/failure messaging, and logic verification must be handled strictly by the `validate_call` function.
* **No Manual Logging:** Do not use `rich.print` or standard `print` for verification logic within the test cells. If an operation is being tested, it must be passed through `validate_call`.
* **Architectural Lean:** Use of wrapper functions within cells is strictly prohibited to prevent architectural bloat.

#### 2. Caching and Directory Hygiene
* **Isolated Cache Path:** All persistent data, including API responses and binary graph states, must be stored in `utils/.cache/`. Storage in the project root is strictly prohibited.
* **Temporal Partitioning:** Cache directories must support sub-folder partitioning (e.g., `utils/.cache/1PM_traffic/`) to prevent cross-contamination of time-dependent datasets.
* **Automated Provisioning:** Classes must verify the existence of their specific cache directory and create it programmatically if missing.

#### 3. Serialization and Reusability
* **Binary Integrity:** Use `pickle` for complex object serialization (like `MultiDiGraph` or `CityGraph`) to preserve internal topological states.
* **Keyed Hashing:** Cache filenames must be generated using an MD5 hash of the defining parameters (BBOX, name, temporal window) to ensure that changes in configuration trigger a fresh extraction rather than loading stale data.
* **Interoperability:** Serialized objects must remain decoupled from specific notebook instances. All paths and configurations required for deserialization must be injectable via YAML.

#### 4. Adversarial Testing Requirements
* **Positive Verification:** Test ideal conditions where success is expected.
* **Negative Verification:** Mandatory testing of "Expected Failures." You must pass arguments designed to trigger specific exceptions (e.g., `[ROUTE]` loop errors) to verify that the module's internal safeguards are active.

#### 5. Visualization Standards
* **Strict Return Check:** Every visualization test must assert that the return type is strictly `-> Image.Image`.
* **Sequential Display:** Use `display(img)` only after the `validate_call` has confirmed a successful execution.