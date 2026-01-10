"""
utils.py
General utility functions for ambient lighting laptop application.
Strictly follows PROJECT_SPEC.md.
"""
import numpy as np

def clamp(x, min_val, max_val):
    return max(min(x, max_val), min_val)
