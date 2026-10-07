"""Priority weight configuration for Scope 2 Goal Programming."""
from pydantic import BaseModel, Field, model_validator


class GoalWeights(BaseModel):
    """Team-assigned priority weights for Goal Programming (Slide 14).
    
    Objective:
        min Z = w1 * d1+ + w2 * d2+ + w3 * d3+
        
    Example from PPT:
        w1 = 0.50 (Time goal weight)
        w2 = 0.25 (Pit stop goal weight)
        w3 = 0.25 (Degradation goal weight)
    """
    weight_time_w1: float = Field(default=0.50, ge=0.0, description="w1: Time goal penalty weight")
    weight_pit_stops_w2: float = Field(default=0.25, ge=0.0, description="w2: Pit stops penalty weight")
    weight_degradation_w3: float = Field(default=0.25, ge=0.0, description="w3: Tyre degradation penalty weight")

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "GoalWeights":
        """Verify weights are non-negative and can be normalized."""
        total = self.weight_time_w1 + self.weight_pit_stops_w2 + self.weight_degradation_w3
        if total <= 0:
            raise ValueError("Sum of goal weights must be greater than zero.")
        return self
