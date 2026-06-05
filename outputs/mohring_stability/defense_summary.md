# Mohring Stability Calibration Defense Summary

This experiment does not run the microscopic passenger-jeep simulation. It repeatedly samples OD pairs, computes TravelGraph journeys, counts route usage, applies square-root Mohring allocation, and selects the smallest sample size that stabilizes allocation variability.

| Route count | Total fleet | Chosen sample size | Max allocation CV | Mean allocation CV | Route-hit rate |
|---:|---:|---:|---:|---:|---:|
| 4 | 40 | 150 | 0.5000 | 0.1841 | 0.7295 |
| 8 | 80 | 50 | 0.3339 | 0.1734 | 0.7629 |
| 16 | 160 | 300 | 0.4082 | 0.1435 | 0.8824 |
| 32 | 320 | 450 | 0.3742 | 0.1086 | 0.9435 |

Recommended defense interpretation:

> The selected Mohring sample size is the smallest tested value that keeps the worst route-level allocation coefficient of variation at or below the target threshold, while also checking that OD samples actually use the route network.