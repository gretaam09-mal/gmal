"""Deterministic exposure engine.

CONVENTIONS.md rule #1: all arithmetic lives in this package. The LLM never
computes a number. Modules under engine/ (predicates, impact, diff) are pure:
no I/O, no network, no database session, no wall-clock reads.
"""
