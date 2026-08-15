import joblib
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
bundle = joblib.load(BASE / "model" / "student_performance_model.joblib")
model = bundle["model"]
features = bundle["features"]
algorithm = bundle["algorithm"]

def predict_performance(attendance, internal_marks, assignment_marks,
                        practical_marks, previous_cgpa, backlog_count):
    data = pd.DataFrame([{
        "attendance": attendance,
        "internal_marks": internal_marks,
        "assignment_marks": assignment_marks,
        "practical_marks": practical_marks,
        "previous_cgpa": previous_cgpa,
        "backlog_count": backlog_count
    }])[features]
    result = model.predict(data)[0]
    confidence = float(model.predict_proba(data).max()) if hasattr(model, "predict_proba") else None
    return result, confidence, algorithm
