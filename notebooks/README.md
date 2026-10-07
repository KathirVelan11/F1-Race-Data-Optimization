# Notebooks Directory

This directory is reserved for exploratory data analysis, offline experiments, and interactive model validation.

## Principles

1. **Exploration Only:** Production algorithms and models reside in `src/f1_optimizer/`, NOT in notebooks.
2. **Reproducibility:** Notebooks should import reusable functionality from `f1_optimizer.common` rather than redefining data loaders or models.
3. **Structure:**
   - `exploration/`: Exploratory analysis of lap times, tyre degradation patterns, and pit-stop distributions.
   - `validation/`: Validation of model outputs against historical race results.
   - `experiments/`: Parameter sensitivity experiments (e.g. testing different pit loss values $P$, degradation slope limits).
