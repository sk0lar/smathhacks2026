from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import os, warnings
warnings.filterwarnings('ignore')

app = Flask(__name__, static_folder='static')

# ── Train model on startup ───────────────────────────────────────────────────
df = pd.read_excel('../bycatch_dataset.xlsx', sheet_name='Bycatch_Data')

# Build continuous risk score (same formula as before)
def gaussian(x, mean, sigma):
    return np.exp(-0.5 * ((x - mean) / sigma) ** 2)

df['temp_risk']      = gaussian(df['Sea Surface Temp (°C)'], 26, 5)
df['current_risk']   = np.clip(df['Current Speed (kn)'] / 5.0, 0, 1)
migration_map        = {'Stationary': 1.0, 'Southward': 0.7, 'Northward': 0.65, 'Eastward': 0.5, 'Westward': 0.5}
df['migration_risk'] = df['Migration Pattern'].map(migration_map).fillna(0.5)

def hour_risk(h):
    return float(max(gaussian(h, 6, 1.5), gaussian(h, 18, 1.5)))

df['hour_risk']      = df['Hour of Day (0-23)'].apply(hour_risk) if 'Hour of Day (0-23)' in df.columns else df['Hour of Day (0–23)'].apply(hour_risk)
df['bycatch_binary'] = (df['Bycatch Present'] == 'Present').astype(float)

df['risk_score'] = (
    0.45 * df['bycatch_binary'] +
    0.20 * df['temp_risk']      +
    0.15 * df['current_risk']   +
    0.12 * df['migration_risk'] +
    0.08 * df['hour_risk']
)
df['risk_score'] = (df['risk_score'] - df['risk_score'].min()) / (df['risk_score'].max() - df['risk_score'].min())
df['risk_label'] = (df['risk_score'] > 0.5).astype(int)

# Features
hour_col = 'Hour of Day (0-23)' if 'Hour of Day (0-23)' in df.columns else 'Hour of Day (0–23)'
features = ['Latitude (°)', 'Longitude (°)', 'Sea Surface Temp (°C)',
            'Current Speed (kn)', 'Current Direction', hour_col,
            'Migration Pattern', 'Target Species', 'Species Fate']

X = df[features].copy()
y = df['risk_label']

cat_cols = ['Current Direction', 'Migration Pattern', 'Target Species', 'Species Fate']
encoders = {}
for col in cat_cols:
    encoders[col] = LabelEncoder()
    X[col] = encoders[col].fit_transform(X[col].astype(str))

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
model.fit(X_scaled, y)
print(f"Model trained. Classes: {model.classes_}")

# Feature importance via coefficients
coef_importance = dict(zip(features, np.abs(model.coef_[0])))
total = sum(coef_importance.values())
coef_pct = {k: round(v / total * 100, 1) for k, v in coef_importance.items()}
print("Feature importances:", coef_pct)


# ── Helpers ──────────────────────────────────────────────────────────────────
def gaussian_val(x, mean, sigma):
    return float(np.exp(-0.5 * ((x - mean) / sigma) ** 2))

def hour_risk_val(h):
    return max(gaussian_val(h, 6, 1.5), gaussian_val(h, 18, 1.5))

migration_risk_map = {'Stationary': 1.0, 'Southward': 0.7, 'Northward': 0.65, 'Eastward': 0.5, 'Westward': 0.5}
species_risk_map   = {'Yellowfin Tuna': 0.47, 'Bigeye Tuna': 0.45, 'Mahi-Mahi': 0.19, 'Wahoo': 0.19, 'Striped Marlin': 0.25}
direction_risk_map = {'NE': 0.75, 'E': 0.65, 'SE': 0.60, 'N': 0.55, 'S': 0.50, 'NW': 0.45, 'W': 0.40, 'SW': 0.35}


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/assessor')
def assessor():
    return send_from_directory('static', 'assessor.html')

@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()

    lat   = float(data['lat'])
    lon   = float(data['lon'])
    temp  = float(data['temp'])
    speed = float(data['speed'])
    dir_  = data['direction']
    hour  = int(data['hour'])
    mig   = data['migration']
    sp    = data['species']
    fate  = data['fate']

    row = pd.DataFrame([{
        'Latitude (°)':          lat,
        'Longitude (°)':         lon,
        'Sea Surface Temp (°C)': temp,
        'Current Speed (kn)':    speed,
        'Current Direction':     dir_,
        hour_col:                hour,
        'Migration Pattern':     mig,
        'Target Species':        sp,
        'Species Fate':          fate,
    }])

    for col in cat_cols:
        val = row[col].iloc[0]
        if val in encoders[col].classes_:
            row[col] = encoders[col].transform([val])
        else:
            row[col] = 0

    row_scaled = scaler.transform(row)
    prob       = float(model.predict_proba(row_scaled)[0][1])

    # Factor breakdown
    temp_score    = gaussian_val(temp, 26, 5)
    current_score = min(speed / 5.0, 1.0)
    mig_score     = migration_risk_map.get(mig, 0.5)
    hr_score      = hour_risk_val(hour)
    sp_score      = species_risk_map.get(sp, 0.3)
    dir_score     = direction_risk_map.get(dir_, 0.5)
    fate_score    = 0.8 if fate == 'Discarded' else 0.3
    geo_score     = max(0, 1 - abs(lat - 35) / 20) * max(0, 1 - abs(lon + 76) / 10)

    level = 'HIGH' if prob > 0.65 else ('MEDIUM' if prob > 0.35 else 'LOW')

    return jsonify({
        'score': round(prob, 3),
        'level': level,
        'factors': {
            'Sea Surface Temp':  round(temp_score * 100),
            'Hour of Day':       round(hr_score * 100),
            'Current Speed':     round(current_score * 100),
            'Migration Pattern': round(mig_score * 100),
            'Target Species':    round(sp_score * 100),
            'Geography':         round(geo_score * 100),
        },
        'feature_importance': coef_pct
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
