# Mohring Stability Calibration Defense Summary

This experiment does not run the microscopic passenger-jeep simulation. It repeatedly samples OD pairs, computes TravelGraph journeys, counts route usage, applies square-root Mohring allocation, and selects the smallest sample size that stabilizes allocation variability.

| Route count | Total fleet | Chosen sample size | Max allocation CV | Mean allocation CV | Route-hit rate |
|---:|---:|---:|---:|---:|---:|
| 38 | - | Not reached | - | - | - |

Recommended defense interpretation:

> The selected Mohring sample size is the smallest tested value that keeps the worst route-level allocation coefficient of variation at or below the target threshold, while also checking that OD samples actually use the route network.