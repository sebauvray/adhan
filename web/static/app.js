/* === Dashboard JavaScript === */

const PHONETIC = {
  Fajr: 'Fajr', Dhuhr: 'Dhuhr', Asr: 'Asr', Maghrib: 'Maghrib', Isha: 'Isha'
};

const WEATHER_ICONS = {
  // Day icons
  '0_day': 'clear-day', '1_day': 'clear-day',
  '2_day': 'partly-cloudy-day', '3_day': 'overcast',
  '45_day': 'fog-day', '48_day': 'fog-day',
  '51_day': 'partly-cloudy-day-drizzle', '53_day': 'overcast-day-drizzle', '55_day': 'overcast-drizzle',
  '56_day': 'overcast-day-sleet', '57_day': 'overcast-sleet',
  '61_day': 'partly-cloudy-day-rain', '63_day': 'overcast-day-rain', '65_day': 'overcast-rain',
  '66_day': 'overcast-day-sleet', '67_day': 'overcast-sleet',
  '71_day': 'partly-cloudy-day-snow', '73_day': 'overcast-day-snow', '75_day': 'overcast-snow', '77_day': 'snowflake',
  '80_day': 'partly-cloudy-day-rain', '81_day': 'overcast-day-rain', '82_day': 'overcast-rain',
  '95_day': 'thunderstorms-day-rain', '96_day': 'thunderstorms-day-overcast-rain', '99_day': 'thunderstorms-overcast-rain',
  // Night icons
  '0_night': 'clear-night', '1_night': 'clear-night',
  '2_night': 'partly-cloudy-night', '3_night': 'overcast',
  '45_night': 'fog-night', '48_night': 'fog-night',
  '51_night': 'partly-cloudy-night-drizzle', '53_night': 'overcast-night-drizzle', '55_night': 'overcast-drizzle',
  '56_night': 'overcast-night-sleet', '57_night': 'overcast-sleet',
  '61_night': 'partly-cloudy-night-rain', '63_night': 'overcast-night-rain', '65_night': 'overcast-rain',
  '66_night': 'overcast-night-sleet', '67_night': 'overcast-sleet',
  '71_night': 'partly-cloudy-night-snow', '73_night': 'overcast-night-snow', '75_night': 'overcast-snow', '77_night': 'snowflake',
  '80_night': 'partly-cloudy-night-rain', '81_night': 'overcast-night-rain', '82_night': 'overcast-rain',
  '95_night': 'thunderstorms-night-rain', '96_night': 'thunderstorms-night-overcast-rain', '99_night': 'thunderstorms-overcast-rain',
};

function getWeatherIcon(code, isDay) {
  const timeOfDay = isDay ? 'day' : 'night';
  const icon = WEATHER_ICONS[`${code}_${timeOfDay}`] || 'not-available';
  return `/static/weather/${icon}.svg`;
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

/* --- Prayer Tracking --- */

let trackingUsers = [];
let trackingLogs = {};
let activePrayer = null;
let prayerStatuses = {};
let currentSalat = null;
let sunriseTime = null;

async function fetchTrackingData() {
  try {
    const date = new Date().toISOString().slice(0, 10);
    const resp = await fetch('/api/prayer-logs/' + date);
    if (resp.ok) {
      const data = await resp.json();
      trackingUsers = data.users || [];
      trackingLogs = data.logs || {};
      updatePrayerBadges();
    }
  } catch (e) {
    console.error('Erreur fetch tracking:', e);
  }
}

function updatePrayerBadges() {
  // Show a small count badge on each prayer that has logs
  document.querySelectorAll('.prayer-item').forEach(item => {
    const prayer = item.dataset.prayer;
    if (!prayer) return;
    const count = (trackingLogs[prayer] || []).length;
    let badge = item.querySelector('.prayer-badge');
    if (count > 0) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'prayer-badge';
        item.appendChild(badge);
      }
      badge.textContent = trackingUsers
        .filter(u => (trackingLogs[prayer] || []).includes(u.id))
        .map(u => u.emoji).join('');
    } else if (badge) {
      badge.remove();
    }
  });
}

function isPrayerLate(prayer) {
  if (prayer === currentSalat) return false;
  if (prayer === 'Fajr' && sunriseTime) {
    const now = new Date();
    const [h, m] = sunriseTime.split(':').map(Number);
    if (now.getHours() > h || (now.getHours() === h && now.getMinutes() >= m)) {
      return true;
    }
  }
  return prayerStatuses[prayer] === 'past';
}

function showWarning() {
  const overlay = document.getElementById('tracking-overlay');
  const container = document.getElementById('tracking-users');
  document.getElementById('tracking-prayer-name').textContent = '';
  container.innerHTML = '<div class="tracking-warning"><span style="font-size:2.5rem">☝️</span><p>Dieu te voit tu sais...</p></div>';
  overlay.style.display = 'flex';
  requestAnimationFrame(() => overlay.classList.add('open'));
  setTimeout(() => closeTracking(), 4000);
}

function openTracking(prayer) {
  if (prayerStatuses[prayer] === 'upcoming' && prayer !== currentSalat) {
    showWarning();
    return;
  }
  activePrayer = prayer;
  const overlay = document.getElementById('tracking-overlay');
  const container = document.getElementById('tracking-users');
  document.getElementById('tracking-prayer-name').textContent = PHONETIC[prayer] || prayer;

  if (!trackingUsers.length) {
    container.innerHTML = '<p style="font-size:0.85rem;color:rgba(26,26,26,0.5);margin:1rem 0">Ajoute des utilisateurs dans les <a href="/settings" style="color:#c8a97e">Parametres</a></p>';
  } else {
    const loggedIds = trackingLogs[prayer] || [];
    let html = trackingUsers.map((u, i) => {
      const done = loggedIds.includes(u.id);
      return `<button class="tracking-avatar ${done ? 'done' : ''}" data-user="${u.id}" onclick="toggleUserPrayer(this)" style="animation-delay:${i * 0.07}s">
        <span class="tracking-avatar-emoji">${u.emoji}</span>
        <span class="tracking-avatar-name">${u.name}</span>
        ${done ? '<span class="tracking-avatar-check">&#10003;</span>' : ''}
      </button>`;
    }).join('');

    if (isPrayerLate(prayer)) {
      html += '<p class="tracking-reminder">Chaque priere a son heure, ne tarde pas la prochaine fois inch\u2019Allah !</p>';
    }

    container.innerHTML = html;
  }

  overlay.style.display = 'flex';
  // Trigger animation
  requestAnimationFrame(() => overlay.classList.add('open'));
}

function closeTracking(event) {
  if (event && event.target !== event.currentTarget) return;
  const overlay = document.getElementById('tracking-overlay');
  overlay.classList.remove('open');
  setTimeout(() => { overlay.style.display = 'none'; }, 250);
  activePrayer = null;
}

async function toggleUserPrayer(btn) {
  const userId = parseInt(btn.dataset.user);
  const prayer = activePrayer;
  if (!prayer) return;

  const loggedIds = trackingLogs[prayer] || [];
  const isDone = loggedIds.includes(userId);
  const date = new Date().toISOString().slice(0, 10);

  if (isDone) {
    // Unlog
    try {
      await fetch('/api/prayer-log', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, prayer, date }),
      });
      trackingLogs[prayer] = loggedIds.filter(id => id !== userId);
      btn.classList.remove('done');
      btn.querySelector('.tracking-avatar-check')?.remove();
      updatePrayerBadges();
      setTimeout(() => closeTracking(), 800);
    } catch (e) {
      console.error('Erreur unlog prayer:', e);
    }
  } else {
    // Log
    try {
      await fetch('/api/prayer-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, prayer, date }),
      });
      if (!trackingLogs[prayer]) trackingLogs[prayer] = [];
      trackingLogs[prayer].push(userId);
      btn.classList.add('done');
      // Add check mark
      const check = document.createElement('span');
      check.className = 'tracking-avatar-check';
      check.innerHTML = '&#10003;';
      btn.appendChild(check);
      updatePrayerBadges();
      // Confetti + close after animation
      launchConfetti();
      setTimeout(() => closeTracking(), 800);
    } catch (e) {
      console.error('Erreur log prayer:', e);
    }
  }
}

/* --- Confetti --- */

function launchConfetti() {
  const canvas = document.getElementById('confetti-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const colors = ['#c8a97e', '#e8d5b7', '#f5f0e8', '#a68a5b', '#FFD700', '#FF6B6B', '#4ECDC4'];
  const particles = [];

  for (let i = 0; i < 120; i++) {
    particles.push({
      x: canvas.width / 2 + (Math.random() - 0.5) * 200,
      y: canvas.height / 2,
      vx: (Math.random() - 0.5) * 15,
      vy: (Math.random() - 1) * 18 - 5,
      w: Math.random() * 8 + 4,
      h: Math.random() * 6 + 3,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * 360,
      rotSpeed: (Math.random() - 0.5) * 12,
      life: 1,
    });
  }

  let frame = 0;
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = false;

    particles.forEach(p => {
      if (p.life <= 0) return;
      alive = true;
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.4;
      p.rotation += p.rotSpeed;
      p.life -= 0.012;
      p.vx *= 0.99;

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate((p.rotation * Math.PI) / 180);
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    });

    frame++;
    if (alive && frame < 180) {
      requestAnimationFrame(animate);
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  animate();
}

/* --- Prayers --- */

function renderPrayers(data) {
  const list = document.getElementById('prayers-list');
  if (!list || !data.prayers) return;

  data.prayers.forEach(p => { prayerStatuses[p.name] = p.status; });
  currentSalat = data.current_salat || null;

  list.innerHTML = data.prayers.map(p => `
    <div class="prayer-item ${p.status}${p.name === currentSalat && p.status !== 'current' ? ' current' : ''}" data-prayer="${p.name}" onclick="openTracking('${p.name}')">
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
      updatePrayerBadges();
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
      document.getElementById('weather-icon').src = getWeatherIcon(data.weather_code, data.is_day);
      document.getElementById('weather-temp').textContent = data.temperature + '°';
      document.getElementById('weather-city').textContent = data.city;
    }
  } catch (e) {
    console.error('Erreur fetch weather:', e);
  }
}

/* --- Sunrise (Chourouk) --- */

async function fetchSunrise() {
  try {
    const resp = await fetch('/api/sunrise');
    if (!resp.ok) return;
    const data = await resp.json();
    const el = document.getElementById('sunrise-info');
    if (data.time && el) {
      sunriseTime = data.time;
      document.getElementById('sunrise-time').textContent = data.time;
      el.style.display = 'flex';
    }
  } catch (e) {
    console.error('Erreur fetch sunrise:', e);
  }
}

/* --- Jumua (Friday) --- */

async function fetchJumua() {
  const isFriday = new Date().getDay() === 5;
  if (!isFriday) return;

  try {
    const resp = await fetch('/api/jumua');
    if (!resp.ok) return;
    const data = await resp.json();
    const el = document.getElementById('jumua-info');
    if (data.times && data.times.length > 0 && el) {
      document.getElementById('jumua-times').innerHTML = data.times.join(' <span class="jumua-sep">/</span> ');
      el.style.display = 'flex';
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

  fetchPrayers().then(() => fetchTrackingData());
  setInterval(fetchPrayers, 60000);
  setInterval(fetchTrackingData, 60000);

  fetchWeather();
  setInterval(fetchWeather, 1800000);

  fetchSunrise();
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
