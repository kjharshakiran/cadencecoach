from typing import Dict, Any

def calculate_bmr_tdee(weight_lbs: float, height_cm: float, age: int, gender: str, activity_level: str) -> Dict[str, Any]:
    """
    Calculates Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE)
    using the Mifflin-St Jeor equation.

    Args:
        weight_lbs: Weight in pounds (lbs).
        height_cm: Height in centimeters.
        age: Age in years.
        gender: "male" or "female".
        activity_level: One of "sedentary", "light", "moderate", "active", "very_active".

    Returns:
        A dictionary containing BMR, TDEE, and activity factor used.
    """
    # Convert lbs to kg for BMR calculation (1 lb = 0.453592 kg)
    weight_kg = weight_lbs * 0.453592

    # BMR Calculation (Mifflin-St Jeor)
    if gender.lower() == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    # Activity Factor
    activity_factors = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    
    factor = activity_factors.get(activity_level.lower(), 1.2) # Default to sedentary if unknown
    tdee = bmr * factor

    return {
        "bmr": round(bmr, 0),
        "tdee": round(tdee, 0),
        "activity_factor": factor,
        "formula": "Mifflin-St Jeor"
    }
