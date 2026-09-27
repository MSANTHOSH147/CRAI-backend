import os
import json
import joblib
import pandas as pd

# Load model artifacts on startup
MODEL_PATH = "risk_ai/models/crai_risk_model_v1.pkl"
CONFIG_PATH = "risk_ai/models/feature_config.json"

if not os.path.exists(MODEL_PATH) or not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError("Model artifacts not found! Please run train_risk_model.py first.")

model = joblib.load(MODEL_PATH)
with open(CONFIG_PATH, "r") as f:
    training_columns = json.load(f)

def get_risk_level(score):
    if score < 30:
        return "LOW"
    elif score < 60:
        return "MODERATE"
    elif score < 80:
        return "HIGH"
    else:
        return "CRITICAL"

def generate_explainable_factors(features, score):
    """Generates human-readable contributing factors for the SIH 2026 prototype dashboard."""
    factors = []
    
    if features.get("disease_confidence", 0) > 0.80:
        factors.append(f"High disease confidence ({int(features['disease_confidence'] * 100)}%)")
    
    if features.get("disease_density", 0) > 0.50:
        factors.append(f"High regional infection density ({int(features['disease_density'] * 100)}%)")
        
    if features.get("infected_neighbor_count", 0) >= 3:
        factors.append(f"Multiple nearby infected observations ({features['infected_neighbor_count']} detected)")
        
    if features.get("thermal_anomaly", 0) > 2.0:
        factors.append(f"Elevated thermal anomaly ({features['thermal_anomaly']}°C above baseline)")
        
    if features.get("humidity", 0) > 80.0 and ("Blight" in features.get("disease", "") or "Mold" in features.get("disease", "")):
        factors.append(f"High humidity ({features['humidity']}%) favorable for fungal spread")
        
    if not factors and score > 30:
        factors.append("Moderate environmental and spatial stress accumulation")
    elif not factors:
        factors.append("No significant risk indicators detected; crop conditions stable")
        
    return factors

def predict_risk(features: dict) -> dict:
    """
    Accepts structured feature dictionary, aligns columns with training schema,
    runs CPU inference, and returns risk score, level, and explainable factors.
    """
    # Convert input dict to DataFrame
    input_df = pd.DataFrame([features])
    
    # One-hot encode categorical features identically to training setup
    input_encoded = pd.get_dummies(input_df, columns=["crop", "disease", "growth_stage"], drop_first=False)
    
    # Reindex to strictly match the training feature columns (fill missing columns with 0)
    input_aligned = input_encoded.reindex(columns=training_columns, fill_value=0)
    
    # Run CPU prediction
    raw_score = float(model.predict(input_aligned)[0])
    risk_score = round(min(max(raw_score, 0.0), 100.0), 1)
    risk_level = get_risk_level(risk_score)
    
    # Generate explainable factors
    factors = generate_explainable_factors(features, risk_score)
    
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "dominant_disease": features.get("disease"),
        "confidence": features.get("disease_confidence"),
        "factors": factors
    }

# --- Test Execution Block ---
if __name__ == "__main__":
    # Sample test payload matching your specifications
    sample_features = {
        "crop": "Tomato",
        "disease": "4_Tomato_Early_Blight",
        "disease_confidence": 0.91,
        "temperature": 31.2,
        "humidity": 83.0,
        "thermal_anomaly": 2.8,
        "infected_neighbor_count": 4,
        "total_neighbor_count": 6,
        "disease_density": 0.67,
        "cluster_density": 0.72,
        "observation_count": 8,
        "growth_stage": "Vegetative"
    }
    
    print("\nRunning Test Prediction for CRAI Risk AI V1...")
    result = predict_risk(sample_features)
    
    print("\nCRAI RISK AI")
    print("-------------------------")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Dominant Disease: {result['dominant_disease']}")
    print("\nMajor Risk Factors:")
    for factor in result['factors']:
        print(f" - {factor}")