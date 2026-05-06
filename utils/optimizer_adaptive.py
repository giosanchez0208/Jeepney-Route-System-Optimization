"""
optimizer_adaptive.py

Dynamically scales mutation probabilities to escape local optima.
"""

class AdaptiveController:
    def __init__(self, base_mutation: float, stagnation_limit: int):
        self.base_mutation = base_mutation
        self.stagnation_limit = stagnation_limit
        self.current_mutation = base_mutation

    def update(self, stagnation_counter: int) -> float:
        """
        Scales mutation intensity exponentially as stagnation increases.
        Resets to baseline immediately upon fitness improvement.
        """
        if stagnation_counter == 0:
            self.current_mutation = self.base_mutation
            return self.current_mutation

        # Increase mutation rate up to a hard cap of 0.8 to force exploration
        scale_factor = 1.0 + (stagnation_counter / self.stagnation_limit)
        self.current_mutation = min(self.base_mutation * scale_factor, 0.8)
        
        return self.current_mutation