"""
optimizer_adaptive.py

Dynamically scales mutation probabilities to escape local optima.
"""

class AdaptiveController:
    """
    Adaptive Operator Controller (Dynamic Mutation)

    Function: 
        Adjusts mutation intensity dynamically based on population stagnation.
    
    Academic Backing:
        This is strictly backed by the literature on "Adaptive Parameter Control in 
        Evolutionary Computation" (Eiben, A. E., Hinterding, R., & Michalewicz, Z., 1999). 
        It solves the fundamental trade-off between premature convergence (exploration) 
        and inefficient random searches (exploitation). When progress stagnates, 
        the controller accelerates the mutation rate to force the system out of local optima,
        dampening it back to the baseline once improvements are registered.
    """
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

    def get_local_search_prob(self, generation: int, g_max: int, p_min: float = 0.05, p_max: float = 0.8) -> float:
        """
        Computes the linearly decayed local search mutation probability to prevent premature convergence.
        
        Formula:
            P_local(g) = P_min + (P_max - P_min) * (1 - g / G_max)
        """
        p_max = max(p_max, self.base_mutation)
        g_max = max(1, g_max)
        ratio = min(max(generation / g_max, 0.0), 1.0)
        return p_min + (p_max - p_min) * (1.0 - ratio)

    def get_local_search_intensity(self, generation: int, g_max: int, i_min: float = 0.1, i_max: float = 1.0) -> float:
        """
        Computes the dynamically tightened localized search radius (intensity parameter).
        
        Formula:
            I_local(g) = I_min + (I_max - I_min) * (1 - g / G_max)
        """
        g_max = max(1, g_max)
        ratio = min(max(generation / g_max, 0.0), 1.0)
        return i_min + (i_max - i_min) * (1.0 - ratio)