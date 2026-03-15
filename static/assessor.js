// assessor.js
// This file ONLY handles UI rendering.
// ALL risk calculation happens in app.py via logistic regression.
// This file does zero math — it just sends inputs to /predict and displays what comes back.

const FACTOR_COLORS = {
  'Sea Surface Temp':  '#f97316',
  'Hour of Day':       '#eab308',
  'Current Speed':     '#22d3c8',
  'Migration Pattern': '#4ade80',
  'Target Species':    '#a78bfa',
};

async function runAssessment() {
  const btn = document.getElementById('runBtn');
  const err = document.getElementById('errorMsg');

  btn.disabled    = true;
  btn.textContent = 'Running model...';
  err.style.display = 'none';

  // Collect inputs
  const payload = {
    lat:       parseFloat(document.getElementById('lat').value),
    lon:       parseFloat(document.getElementById('lon').value),
    temp:      parseFloat(document.getElementById('temp').value),
    speed:     parseFloat(document.getElementById('speed').value),
    direction: document.getElementById('direction').value,
    hour:      parseInt(document.getElementById('hour').value),
    migration: document.getElementById('migration').value,
    species:   document.getElementById('species').value,
    fate:      document.getElementById('fate').value,
  };

  try {
    // Send to Flask backend — logistic regression runs here
    const response = await fetch('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error(`Server returned ${response.status}`);

    // Get result from model
    const data = await response.json();

    // Render result — everything displayed comes directly from the model response
    renderResult(data);

  } catch (e) {
    console.error(e);
    err.style.display = 'block';
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Run Risk Assessment';
  }
}

function renderResult(data) {
  // data.score           = raw probability 0-1 from model.predict_proba
  // data.percent         = score * 100
  // data.level           = HIGH / MEDIUM / LOW
  // data.threshold       = 65th percentile threshold used to define risk label
  // data.threshold_pct   = threshold * 100
  // data.factors         = display-only factor breakdown (0-100 per factor)

  const { score, percent, level, threshold_pct, factors } = data;

  // Show result panel
  document.getElementById('idleState').style.display  = 'none';
  document.getElementById('resultState').style.display = 'block';

  // Score percentage text
  document.getElementById('scorePct').textContent = percent.toFixed(1) + '%';

  // Animate donut ring
  const circumference = 314.16; // 2 * pi * 50
  const offset = circumference * (1 - score);
  const ring = document.getElementById('donutRing');
  ring.style.strokeDashoffset = offset;

  // Colour based on level
  const colours = { HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e' };
  const colour  = colours[level] || '#22d3c8';
  ring.style.stroke = colour;
  document.getElementById('scorePct').style.color = colour;

  // Risk badge
  const badge = document.getElementById('levelBadge');
  badge.textContent = level + ' RISK';
  badge.className   = 'level-badge badge-' + level;

  // Description
  const descs = {
    HIGH:   `The model gives a ${percent.toFixed(1)}% probability that current conditions exceed the critical risk threshold. Bycatch encounters are likely.`,
    MEDIUM: `The model gives a ${percent.toFixed(1)}% probability that conditions exceed the risk threshold. Proceed with caution.`,
    LOW:    `The model gives only a ${percent.toFixed(1)}% probability that conditions exceed the risk threshold. Risk is within safe bounds.`,
  };
  document.getElementById('resultDesc').textContent = descs[level];

  // Threshold line
  document.getElementById('thresholdRow').innerHTML =
    `Risk threshold: <span style="color:${colour};font-weight:600">${threshold_pct}%</span> of max environmental index`;

  // Factor bars (display only — do not affect score)
  const fl = document.getElementById('factorList');
  fl.innerHTML = '';
  Object.entries(factors).forEach(([name, pct]) => {
    const c = FACTOR_COLORS[name] || '#22d3c8';
    fl.innerHTML += `
      <div class="factor-item">
        <div class="factor-row">
          <span class="factor-name">${name}</span>
          <span class="factor-pct">${pct}%</span>
        </div>
        <div class="factor-track">
          <div class="factor-fill" style="width:${pct}%;background:${c}"></div>
        </div>
      </div>`;
  });

  // Recommendation
  const recs = {
    HIGH:   'Consider shifting to midday fishing (10am–2pm), targeting Wahoo or Mahi-Mahi in cooler waters (below 22°C), and areas with slower currents.',
    MEDIUM: 'Small changes to time of day or location could push conditions below the risk threshold.',
    LOW:    'Conditions are well within safe bounds. Standard monitoring practices are sufficient.',
  };
  document.getElementById('recBox').textContent = recs[level];

  // Scroll sidebar into view on mobile
  document.querySelector('.result-box').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
