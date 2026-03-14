const FACTOR_COLORS = {
  'Sea Surface Temp':  '#f97316',
  'Hour of Day':       '#eab308',
  'Current Speed':     '#22d3c8',
  'Migration Pattern': '#4ade80',
  'Target Species':    '#a78bfa',
  'Geography':         '#94a3b8',
};

async function runPrediction() {
  const btn    = document.getElementById('submitBtn');
  const loader = document.getElementById('btnLoader');
  const text   = btn.querySelector('.btn-text');

  btn.classList.add('loading');
  btn.disabled  = true;
  text.style.display  = 'none';
  loader.style.display = 'inline';

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
    const res  = await fetch('/predict', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    console.error('Prediction failed:', err);
    alert('Could not connect to the model server. Make sure app.py is running on port 5000.');
  } finally {
    btn.classList.remove('loading');
    btn.disabled     = false;
    text.style.display   = 'inline';
    loader.style.display = 'none';
  }
}

function renderResult(data) {
  const score = data.score;
  const level = data.level;

  document.getElementById('resultActive').style.display = 'block';
  document.querySelector('.result-idle').style.display  = 'none';

  // Score number
  document.getElementById('scoreBig').textContent = score.toFixed(2);

  // Donut
  const circumference = 2 * Math.PI * 50;
  const offset = circumference * (1 - score);
  const fill   = document.getElementById('donutFill');
  fill.style.strokeDashoffset = offset;

  const donutColor = level === 'HIGH' ? '#f97316' : level === 'MEDIUM' ? '#eab308' : '#22c55e';
  fill.style.stroke = donutColor;
  document.getElementById('scoreBig').style.color = donutColor;

  // Badge
  const badge = document.getElementById('riskBadge');
  badge.textContent  = level + ' RISK';
  badge.className    = 'risk-level-badge badge-' + level.toLowerCase();

  // Message
  const messages = {
    HIGH:   'Conditions strongly favour non-target species encountering your gear. Consider adjusting time of day, location, or gear configuration.',
    MEDIUM: 'Moderate bycatch likelihood detected. Monitor conditions and consider preventative gear modifications.',
    LOW:    'Current conditions present relatively low bycatch risk. Maintain standard monitoring practices.',
  };
  document.getElementById('riskMessage').textContent = messages[level];

  // Factors
  const fl = document.getElementById('factorList');
  fl.innerHTML = '';
  Object.entries(data.factors).forEach(([name, pct]) => {
    const color = FACTOR_COLORS[name] || '#22d3c8';
    fl.innerHTML += `
      <div class="factor-item">
        <div class="factor-row">
          <span class="factor-name">${name}</span>
          <span class="factor-pct">${pct}%</span>
        </div>
        <div class="factor-track">
          <div class="factor-bar-fill" style="width:${pct}%; background:${color};"></div>
        </div>
      </div>`;
  });

  // Recommendation
  const recs = {
    HIGH:   'Try fishing during midday (10am–2pm), targeting Wahoo or Mahi-Mahi in cooler waters below 22°C, and use more selective gear types.',
    MEDIUM: 'Slight adjustments to time of day or target area could meaningfully reduce your risk score.',
    LOW:    'Current parameters are well within safe thresholds. No immediate changes recommended.',
  };
  document.getElementById('recommendation').textContent = recs[level];

  // Scroll sidebar into view on mobile
  document.querySelector('.result-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Live input feedback
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', () => {
      document.querySelector('.result-idle') && (document.querySelector('.result-idle').style.opacity = '0.5');
    });
  });
});
