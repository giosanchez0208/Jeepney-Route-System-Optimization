"""
optimizer_adaptive.py

Dynamically scales mutation probabilities to escape local optima.
"""

class AdaptiveController:
    def __init__(self, base_mutation: float, stagnation_limit: int, max_mutation: float = 0.8):
        self.base_mutation = base_mutation
        self.stagnation_limit = max(1, stagnation_limit)
        self.max_mutation = max(base_mutation, max_mutation)
        self.current_mutation = base_mutation

    def update(self, stagnation_counter: int) -> float:
        """
        Scales mutation intensity non-linearly as stagnation increases.
        Resets to baseline immediately upon fitness improvement.
        """
        if stagnation_counter == 0:
            self.current_mutation = self.base_mutation
            return self.current_mutation

        # Quadratic scaling: smoothly accelerates towards the hard cap.
        progress = min(stagnation_counter / self.stagnation_limit, 1.0)
        self.current_mutation = self.base_mutation + (self.max_mutation - self.base_mutation) * (progress ** 2)
        
        return self.current_mutation