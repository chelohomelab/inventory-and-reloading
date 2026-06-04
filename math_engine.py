import math

def calculate_shot_metrics(velocity_string: str):
    """
    Takes a string like "2750, 2762, 2748" 
    Returns a dict with (avg_velocity, extreme_spread, standard_deviation)
    """
    if not velocity_string or not velocity_string.strip():
        return {"avg": 0.0, "es": 0.0, "sd": 0.0}
    
    try:
        # Convert the comma-separated string into a clean list of floats
        velocities = [float(v.strip()) for v in velocity_string.split(",") if v.strip()]
    except ValueError:
        # Handle cases where user typed a typo or non-number
        return {"avg": 0.0, "es": 0.0, "sd": 0.0}
        
    n = len(velocities)
    if n == 0:
        return {"avg": 0.0, "es": 0.0, "sd": 0.0}
    if n == 1:
        return {"avg": velocities[0], "es": 0.0, "sd": 0.0}

    # 1. Calculate Average (Mean)
    avg_vel = sum(velocities) / n
    
    # 2. Calculate Extreme Spread (Max - Min)
    extreme_spread = max(velocities) - min(velocities)
    
    # 3. Calculate Sample Standard Deviation
    variance_sum = sum((v - avg_vel) ** 2 for v in velocities)
    standard_dev = math.sqrt(variance_sum / (n - 1))
    
    return {
        "avg": round(avg_vel, 1),
        "es": round(extreme_spread, 1),
        "sd": round(standard_dev, 1)
    }