"""Entity Profile completeness and confidence-impact scoring.

Pure and deterministic (CONVENTIONS.md rule #1): given a field catalog and
which fields are known vs. unknown/defaulted, this computes a completeness
score and flags which unknowns will reduce memo confidence later. No I/O,
no LLM call — this is exactly the kind of number the engine is for.
"""
