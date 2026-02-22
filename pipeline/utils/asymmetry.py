"""
Asymmetry calculation utilities.

Provides functions for computing hippocampal asymmetry indices.
"""

from typing import Tuple

import numpy as np

from backend.core.logging import get_logger

logger = get_logger(__name__)


def calculate_asymmetry_index(left_volume: float, right_volume: float) -> float:
    """
    Calculate asymmetry index between left and right hemisphere volumes.
    
    Formula: AI = (L - R) / (L + R)
    
    Where:
    - L = Left hemisphere volume
    - R = Right hemisphere volume
    - AI > 0: Left larger than right
    - AI < 0: Right larger than left
    - AI ≈ 0: Symmetric
    
    Args:
        left_volume: Left hemisphere volume (mm³)
        right_volume: Right hemisphere volume (mm³)
    
    Returns:
        Asymmetry index (dimensionless, typically between -1 and 1)
    """
    # Denominator: sum of volumes
    denom = (left_volume + right_volume)
    
    # Handle edge case of zero sum volume
    if denom == 0:
        logger.warning("zero_mean_volume", left=left_volume, right=right_volume)
        return 0.0
    
    # Calculate asymmetry index
    ai = (left_volume - right_volume) / denom
    
    return round(ai, 4)


def classify_laterality(asymmetry_index: float, threshold: float = 0.05) -> str:
    """
    Classify laterality based on asymmetry index.

    Args:
        asymmetry_index: Computed asymmetry index
        threshold: Threshold for considering asymmetry significant

    Returns:
        Laterality classification ('Left > Right', 'Right > Left', or 'Symmetric')
    """
    if asymmetry_index > threshold:
        return "Left > Right"
    elif asymmetry_index < -threshold:
        return "Right > Left"
    else:
        return "Symmetric"


def classify_hs_laterality(asymmetry_index: float) -> str:
    """
    Classify laterality using hippocampal sclerosis thresholds from dashboard.

    Uses the same thresholds and classifications as the web dashboard for consistency.

    Args:
        asymmetry_index: Computed asymmetry index

    Returns:
        HS-based laterality classification with suspicion details and threshold information
    """
    # HS thresholds from dashboard
    LEFT_HS_THRESHOLD = -0.070839747728063
    RIGHT_HS_THRESHOLD = 0.046915816971433

    if asymmetry_index > RIGHT_HS_THRESHOLD:
        classification = "Left-dominant (Right HS suspected)"
    elif asymmetry_index < LEFT_HS_THRESHOLD:
        classification = "Right-dominant (Left HS suspected)"
    else:
        classification = "Balanced (No HS)"

    # Add threshold information as bullet points
    thresholds_info = f"""Thresholds:

• Left HS (Right-dominant) if AI < {LEFT_HS_THRESHOLD:.12f}
• Right HS (Left-dominant) if AI > {RIGHT_HS_THRESHOLD:.12f}
• No HS (Balanced) otherwise."""

    return f"{classification}\n\n{thresholds_info}"


def calculate_percent_difference(left_volume: float, right_volume: float) -> float:
    """
    Calculate percent difference between left and right volumes.
    
    Formula: %diff = ((L - R) / L) * 100
    
    Args:
        left_volume: Left hemisphere volume
        right_volume: Right hemisphere volume
    
    Returns:
        Percent difference
    """
    if left_volume == 0:
        return 0.0
    
    percent_diff = ((left_volume - right_volume) / left_volume) * 100
    return round(percent_diff, 2)


def calculate_volume_ratio(left_volume: float, right_volume: float) -> float:
    """
    Calculate left-to-right volume ratio.
    
    Args:
        left_volume: Left hemisphere volume
        right_volume: Right hemisphere volume
    
    Returns:
        Volume ratio (L/R)
    """
    if right_volume == 0:
        return np.inf
    
    ratio = left_volume / right_volume
    return round(ratio, 3)

