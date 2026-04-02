/* === Dashboard JavaScript === */

const PHONETIC = {
  Fajr: 'Fadjer', Dhuhr: 'Dohr', Asr: 'Asr', Maghrib: 'Maghrib', Isha: 'Icha'
};

const WEATHER_ICONS = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌦️', 55: '🌧️', 56: '🌧️', 57: '🌧️',
  61: '🌧️', 63: '🌧️', 65: '🌧️', 66: '🌧️', 67: '🌧️',
  71: '🌨️', 73: '🌨️', 75: '🌨️', 77: '🌨️',
  80: '🌦️', 81: '🌦️', 82: '🌦️',
  95: '⛈️', 96: '⛈️', 99: '⛈️',
};

function getWeatherIcon(code) {
  return WEATHER_ICONS[code] || '🌡️';
}

/* --- Clock --- */

function updateClock() {
  const now = new Date();
  const timeEl = document.getElementById('clock-time');
  const dateEl = document.getElementById('clock-date');
  if (!timeEl) return;

  timeEl.textContent = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  dateEl.textContent = now.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

/* --- Countdown --- */

let secondsUntilNext = 0;

function updateCountdown() {
  const el = document.getElementById('countdown');
  if (!el) return;

  if (secondsUntilNext <= 0) {
    // Prayer time reached — refresh data immediately
    fetchPrayers();
    return;
  }

  secondsUntilNext--;
  const h = Math.floor(secondsUntilNext / 3600);
  const m = Math.floor((secondsUntilNext % 3600) / 60);
  const s = secondsUntilNext % 60;

  let text = '';
  if (h > 0) text += `${h}h `;
  if (m > 0 || h > 0) text += `${m}min `;
  text += `${s}s`;
  el.textContent = text;
}

/* --- Prayers --- */

function renderPrayers(data) {
  const list = document.getElementById('prayers-list');
  if (!list || !data.prayers) return;

  list.innerHTML = data.prayers.map(p => `
    <div class="prayer-item ${p.status}">
      <span class="prayer-name">${PHONETIC[p.name] || p.name}</span>
      <span class="prayer-time">${p.adhan}</span>
      <span class="prayer-iqama">
        <svg class="iqm-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
        ${p.iqama}
      </span>
    </div>
  `).join('');

  // Next prayer (right panel)
  const next = data.next;
  if (next) {
    document.getElementById('next-arabic').textContent = next.arabic || '';
    document.getElementById('next-time').textContent = next.adhan;
    document.getElementById('next-iqama').innerHTML = `<svg class="iqm-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> ${next.iqama || next.adhan}`;
    secondsUntilNext = next.seconds_until || 0;
    updateCountdown();
  }
}

async function fetchPrayers() {
  try {
    const resp = await fetch('/api/prayers');
    if (resp.ok) {
      const data = await resp.json();
      renderPrayers(data);
    }
  } catch (e) {
    console.error('Erreur fetch prayers:', e);
  }
}

/* --- Weather --- */

async function fetchWeather() {
  try {
    const resp = await fetch('/api/weather');
    if (resp.ok) {
      const data = await resp.json();
      document.getElementById('weather-icon').textContent = getWeatherIcon(data.weather_code);
      document.getElementById('weather-temp').textContent = data.temperature + '°';
      document.getElementById('weather-city').textContent = data.city;
    }
  } catch (e) {
    console.error('Erreur fetch weather:', e);
  }
}

/* --- Jumua (Friday) --- */

async function fetchJumua() {
  const footer = document.getElementById('dash-footer');
  if (!footer) return;

  const isFriday = new Date().getDay() === 5;
  if (!isFriday) { footer.style.display = 'none'; return; }

  try {
    const resp = await fetch('/api/jumua');
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.times && data.times.length > 0) {
      document.getElementById('jumua-times').textContent = data.times.join(' / ');
      footer.style.display = 'block';
    }
  } catch (e) {
    console.error('Erreur fetch jumua:', e);
  }
}

/* --- Init Dashboard --- */

function initDashboard() {
  if (!document.querySelector('.dashboard-page')) return;

  updateClock();
  setInterval(updateClock, 1000);
  setInterval(updateCountdown, 1000);

  fetchPrayers();
  setInterval(fetchPrayers, 60000);

  fetchWeather();
  setInterval(fetchWeather, 1800000);

  fetchJumua();
}

/* === Setup Page JavaScript === */

async function validateUrl() {
  const input = document.getElementById('mosque_url');
  const preview = document.getElementById('url-preview');
  const btn = document.getElementById('validate-btn');
  if (!input || !preview) return;

  const url = input.value.trim();
  if (!url) return;

  btn.disabled = true;
  btn.innerHTML = 'Vérification<span class="spinner"></span>';
  preview.innerHTML = '';

  try {
    const resp = await fetch('/api/validate-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await resp.json();

    if (data.valid) {
      let html = `<div class="preview-city">${data.city}</div><div class="preview-prayers">`;
      data.prayers.forEach(p => {
        html += `<div class="preview-prayer"><span class="name">${p.name}</span> <span class="time">${p.adhan}</span></div>`;
      });
      html += '</div>';
      preview.innerHTML = html;
      preview.className = 'preview';

      // Enable the submit button
      const submitBtn = document.getElementById('submit-btn');
      if (submitBtn) submitBtn.disabled = false;
    } else {
      preview.innerHTML = data.error;
      preview.className = 'msg msg-error';
    }
  } catch (e) {
    preview.innerHTML = 'Erreur de connexion';
    preview.className = 'msg msg-error';
  }

  btn.disabled = false;
  btn.textContent = 'Vérifier';
}

async function submitSetup(event) {
  event.preventDefault();
  const form = event.target;
  const msgEl = document.getElementById('setup-msg');

  const data = {};
  new FormData(form).forEach((v, k) => { data[k] = v; });

  msgEl.innerHTML = 'Sauvegarde en cours<span class="spinner"></span>';
  msgEl.className = 'msg';

  try {
    const resp = await fetch('/api/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await resp.json();

    if (result.success) {
      let html = '<strong>Configuration sauvegardée !</strong>';
      if (result.token) {
        html += `<div class="token-display"><strong>Votre token API (à conserver) :</strong><code>${result.token}</code></div>`;
      }
      html += '<p style="margin-top:1rem">Redirection vers le dashboard dans 5 secondes...</p>';
      msgEl.innerHTML = html;
      msgEl.className = 'msg msg-success';

      // Store token in localStorage for settings page
      if (result.token) {
        localStorage.setItem('adhan_token', result.token);
      }

      setTimeout(() => { window.location.href = '/dashboard'; }, 5000);
    } else {
      msgEl.innerHTML = result.detail || 'Erreur inconnue';
      msgEl.className = 'msg msg-error';
    }
  } catch (e) {
    msgEl.innerHTML = 'Erreur de connexion';
    msgEl.className = 'msg msg-error';
  }
}

/* === Settings Page JavaScript === */

async function loadConfig() {
  const form = document.getElementById('settings-form');
  if (!form) return;

  try {
    const resp = await fetch('/api/config');
    if (resp.ok) {
      const data = await resp.json();
      Object.entries(data).forEach(([key, value]) => {
        const input = form.querySelector(`[name="${key}"]`);
        if (!input) return;
        if (input.type === 'checkbox') {
          input.checked = value === 'true';
          input.dispatchEvent(new Event('change'));
        } else if (typeof value === 'string') {
          input.value = value;
        }
      });
      // Build OwnTone link
      updateOwntoneLink();
    }
  } catch (e) {
    console.error('Erreur chargement config:', e);
  }
}

function updateOwntoneLink() {
  const portInput = document.getElementById('owntone_port');
  const link = document.getElementById('owntone-link');
  if (!link) return;

  const port = (portInput && portInput.value.trim()) || '3689';
  link.href = `http://${window.location.hostname}:${port}`;
}

async function submitSettings(event) {
  event.preventDefault();
  const form = event.target;
  const msgEl = document.getElementById('settings-msg');
  const token = localStorage.getItem('adhan_token');

  if (!token) {
    msgEl.innerHTML = 'Token API manquant. Entrez-le ci-dessous.';
    msgEl.className = 'msg msg-error';
    return;
  }

  const data = {};
  new FormData(form).forEach((v, k) => { data[k] = v; });

  msgEl.innerHTML = 'Sauvegarde<span class="spinner"></span>';
  msgEl.className = 'msg';

  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });

    if (resp.status === 401) {
      msgEl.innerHTML = 'Token invalide';
      msgEl.className = 'msg msg-error';
      return;
    }

    const result = await resp.json();
    if (result.success) {
      // Also save prayer outputs if available
      if (typeof savePrayerOutputs === 'function') await savePrayerOutputs();
      msgEl.innerHTML = 'Configuration mise à jour. Les horaires seront recalculés.';
      msgEl.className = 'msg msg-success';
    }
  } catch (e) {
    msgEl.innerHTML = 'Erreur de connexion';
    msgEl.className = 'msg msg-error';
  }
}

/* === Init === */

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
  loadConfig();

  // Live update OwnTone link when typing
  const otHost = document.getElementById('owntone_host');
  const otPort = document.getElementById('owntone_port');
  if (otHost) otHost.addEventListener('input', updateOwntoneLink);
  if (otPort) otPort.addEventListener('input', updateOwntoneLink);
});
