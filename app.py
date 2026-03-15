from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
import os
import warnings
warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DATA_PATH  = os.path.join(BASE_DIR, 'bycatch_dataset.xlsx')

app = Flask(__name__, static_folder=STATIC_DIR)

# ---------------------------------------------------------------------------
# STEP 1 — Load data
# ---------------------------------------------------------------------------
print("Loading dataset...")
df = pd.read_excel(DATA_PATH, sheet_name='Bycatch_Data')
print(f"Loaded {len(df)} rows.")
print(f"Columns: {list(df.columns)}")

# Detect the hour column regardless of unicode dash vs ASCII hyphen
HOUR_COL = next(c for c in df.columns if 'Hour' in c)
print(f"Hour column detected: '{HOUR_COL}'")

# ---------------------------------------------------------------------------
# STEP 2 — Build the environmental index used to define the threshold label
#
# This is NOT used at prediction time — it is only used to create training
# labels so logistic regression has something to learn.
#
# env_index = weighted combination of ocean conditions per row
# threshold = 65th percentile of env_index across all rows
# label     = 1 if env_index > threshold, else 0
#
# The model then learns P(label=1 | input features).
# That probability is the risk score returned to the user.
# ---------------------------------------------------------------------------
def gauss(arr, mu, sigma):
    return np.exp(-0.5 * ((np.array(arr, dtype=float) - mu) / sigma) ** 2)

df['ei_temp']      = gauss(df['Sea Surface Temp (°C)'], 26, 5)
df['ei_current']   = np.clip(df['Current Speed (kn)'] / 5.0, 0, 1)
df['ei_migration'] = df['Migration Pattern'].map({
    'Stationary': 1.0, 'Southward': 0.7, 'Northward': 0.65,
    'Eastward':   0.5, 'Westward':  0.5
}).fillna(0.5)
df['ei_hour']    = df[HOUR_COL].apply(
    lambda h: float(max(gauss(h, 6, 1.5), gauss(h, 18, 1.5)))
)
df['ei_bycatch'] = (df['Bycatch Present'] == 'Present').astype(float)

df['env_index'] = (
    0.35 * df['ei_temp']      +
    0.20 * df['ei_current']   +
    0.15 * df['ei_migration'] +
    0.10 * df['ei_hour']      +
    0.20 * df['ei_bycatch']
)

THRESHOLD = float(np.percentile(df['env_index'], 65))
df['label'] = (df['env_index'] > THRESHOLD).astype(int)

print(f"Threshold (65th percentile): {THRESHOLD:.4f}")
print(f"High-risk rows: {df['label'].sum()} / {len(df)} ({df['label'].mean()*100:.1f}%)")

# ---------------------------------------------------------------------------
# STEP 3 — Train logistic regression on the raw input features
#
# The model receives the 9 raw input columns (temp, speed, lat, lon etc.)
# and predicts P(env_index exceeded threshold).
# This is a pure logistic regression — no Gaussian math at inference time.
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    'Latitude (°)', 'Longitude (°)',
    'Sea Surface Temp (°C)', 'Current Speed (kn)',
    'Current Direction', HOUR_COL,
    'Migration Pattern', 'Target Species', 'Species Fate'
]
CAT_COLS = ['Current Direction', 'Migration Pattern', 'Target Species', 'Species Fate']

X = df[FEATURE_COLS].copy()
y = df['label']

ENCODERS = {}
for col in CAT_COLS:
    le = LabelEncoder()
    X[col] = le.fit_transform(X[col].astype(str))
    ENCODERS[col] = le

SCALER   = StandardScaler()
X_scaled = SCALER.fit_transform(X)

MODEL = LogisticRegression(max_iter=2000, C=1.0, random_state=42)
MODEL.fit(X_scaled, y)

train_acc = MODEL.score(X_scaled, y)
print(f"Model trained. Train accuracy: {train_acc:.3f}")

# Feature importance from logistic regression coefficients (not Gaussian)
coef_abs = np.abs(MODEL.coef_[0])
FEAT_IMPORTANCE = {
    FEATURE_COLS[i]: round(float(coef_abs[i] / coef_abs.sum() * 100), 1)
    for i in range(len(FEATURE_COLS))
}
print(f"Feature importance: {FEAT_IMPORTANCE}")

# ---------------------------------------------------------------------------
# STEP 4 — Helper: compute factor breakdown for UI display
#
# These are simple 0-100 scores showing how "activated" each input is.
# They are displayed as bars in the frontend. They do NOT affect the risk
# score — that comes entirely from MODEL.predict_proba.
# ---------------------------------------------------------------------------
MIG_SCORES = {'Stationary':1.0,'Southward':0.7,'Northward':0.65,'Eastward':0.5,'Westward':0.5}
SP_SCORES  = {'Yellowfin Tuna':0.47,'Bigeye Tuna':0.45,'Mahi-Mahi':0.19,'Wahoo':0.19,'Striped Marlin':0.25}

def get_display_factors(temp, speed, hour, migration, species):
    """
    Returns 0-100 scores per factor for the UI breakdown bars.
    These are for display only — the actual risk score comes from the model.
    """
    temp_act  = float(gauss(temp,  26,  5))
    hour_act  = float(max(gauss(hour, 6, 1.5), gauss(hour, 18, 1.5)))
    curr_act  = min(speed / 5.0, 1.0)
    mig_act   = MIG_SCORES.get(migration, 0.5)
    sp_act    = SP_SCORES.get(species,    0.3)
    return {
        'Sea Surface Temp':  round(temp_act  * 100),
        'Hour of Day':       round(hour_act  * 100),
        'Current Speed':     round(curr_act  * 100),
        'Migration Pattern': round(mig_act   * 100),
        'Target Species':    round(sp_act    * 100),
    }

# ---------------------------------------------------------------------------
# STEP 5 — Routes
# ---------------------------------------------------------------------------
@app.route('/')
def home():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/assessor')
def assessor():
    return send_from_directory(STATIC_DIR, 'assessor.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/predict', methods=['POST'])
def predict():
    d = request.get_json(force=True)

    lat   = float(d['lat'])
    lon   = float(d['lon'])
    temp  = float(d['temp'])
    speed = float(d['speed'])
    dir_  = str(d['direction'])
    hour  = int(d['hour'])
    mig   = str(d['migration'])
    sp    = str(d['species'])
    fate  = str(d['fate'])

    # Build input DataFrame matching training feature order
    row = pd.DataFrame([{
        'Latitude (°)':          lat,
        'Longitude (°)':         lon,
        'Sea Surface Temp (°C)': temp,
        'Current Speed (kn)':    speed,
        'Current Direction':     dir_,
        HOUR_COL:                hour,
        'Migration Pattern':     mig,
        'Target Species':        sp,
        'Species Fate':          fate,
    }])

    # Encode categoricals using the same encoders fitted on training data
    for col in CAT_COLS:
        val = row[col].iloc[0]
        if val in ENCODERS[col].classes_:
            row[col] = int(ENCODERS[col].transform([val])[0])
        else:
            row[col] = 0  # unseen category — default to 0

    # Scale using training scaler
    row_scaled = SCALER.transform(row[FEATURE_COLS])

    # ── THE RISK SCORE ──────────────────────────────────────────────────────
    # This is 100% from the logistic regression model.
    # It is P(env_index > THRESHOLD | these input conditions).
    # No Gaussian math. No manual formula.
    risk_score = float(MODEL.predict_proba(row_scaled)[0][1])
    # ────────────────────────────────────────────────────────────────────────

    level = 'HIGH' if risk_score > 0.65 else ('MEDIUM' if risk_score > 0.35 else 'LOW')

    # Display factors (for UI bars only — do not affect score)
    factors = get_display_factors(temp, speed, hour, mig, sp)

    return jsonify({
        'score':            round(risk_score, 3),
        'percent':          round(risk_score * 100, 1),
        'level':            level,
        'threshold':        round(THRESHOLD, 3),
        'threshold_pct':    round(THRESHOLD * 100, 1),
        'factors':          factors,
        'feature_importance': FEAT_IMPORTANCE,
    })

# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
