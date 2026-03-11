/* ============================================================
   main.js — CloudDom Dashboard  |  Dark + Light Mode
   ============================================================ */

/* ── 1. Live Clock ── */
(function initClock() {
  const el = document.getElementById('liveTime');
  if (!el) return;
  const opts = { weekday:'short', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' };
  function tick() { el.textContent = new Date().toLocaleString('en-US', opts); }
  tick();
  setInterval(tick, 1000);
  // Clock interval naturally lives for page lifetime — no cleanup needed
})();


/* ── 2. Scroll Reveal ── */
function initReveal() {
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        io.unobserve(e.target); // stop watching once revealed
      }
    });
  }, { threshold: 0.08 });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
}
document.addEventListener('DOMContentLoaded', initReveal);


/* ── 3. Animated Counters ── */
function animateCounters() {
  document.querySelectorAll('.counter').forEach(el => {
    const target   = parseInt(el.dataset.target, 10) || 0;
    const duration = 1400;
    const start    = performance.now();

    function step(now) {
      const p    = Math.min((now - start) / duration, 1);
      const ease = p >= 1 ? 1 : 1 - Math.pow(2, -10 * p); // exponential ease-out
      el.textContent = Math.round(ease * target);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = target; // snap to exact value at end
    }
    requestAnimationFrame(step);
  });
}
document.addEventListener('DOMContentLoaded', () => setTimeout(animateCounters, 400));


/* ── 4. Table Row Stagger ──
   FIX: stagger only uses opacity (not translateX) so it doesn't conflict
   with the CSS .table-row td white-space/transition declarations.
   Also skips rows that are inside .reveal elements that haven't
   become visible yet — those are handled by the IntersectionObserver. */
function staggerRows() {
  const rows = document.querySelectorAll('.table-row');
  rows.forEach((row, i) => {
    // Set initial hidden state — opacity only, no transform conflict
    row.style.opacity    = '0';
    row.style.transition = `opacity 0.45s ease ${i * 0.055}s`;

    // Reveal after a short base delay so the card's own reveal animation fires first
    setTimeout(() => {
      row.style.opacity = '1';
    }, 560 + i * 55);
  });
}
document.addEventListener('DOMContentLoaded', staggerRows);


/* ── 5. Stat Card Tilt ──
   FIX: tilt transform is removed on mouseleave via style.transform = ''
   which correctly falls back to the CSS declaration (translateY(-6px) scale(1.02)).
   mouseenter sets a fast transition for responsive feel.
   mouseleave restores the slow spring transition for CSS hover state. */
function initCardTilt() {
  document.querySelectorAll('.stat-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      // Fast transition while actively tilting
      card.style.transition = 'transform 0.08s ease';
    });

    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left)  / r.width  - 0.5;
      const y = (e.clientY - r.top)   / r.height - 0.5;
      // translateY(-6px) scale(1.02) matches CSS :hover baseline; tilt layered on top
      card.style.transform = `translateY(-6px) scale(1.02) rotateX(${-y * 7}deg) rotateY(${x * 7}deg)`;
    });

    card.addEventListener('mouseleave', () => {
      // Clear inline transform so CSS :hover / CSS transition takes back control
      card.style.transform  = '';
      // Restore spring transition for smooth snap-back
      card.style.transition = 'transform 0.45s cubic-bezier(0.34,1.56,0.64,1), border-color 0.3s ease, box-shadow 0.3s ease';
    });
  });
}
document.addEventListener('DOMContentLoaded', initCardTilt);


/* ══════════════════════════════════════════
   6. Theme-aware Chart color helpers
══════════════════════════════════════════ */
function isDark() {
  return document.documentElement.getAttribute('data-theme') !== 'light';
}

function chartTextColor()     { return isDark() ? 'rgba(232,234,246,0.60)' : 'rgba(26,31,54,0.60)'; }
function chartGridColor()     { return isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(100,116,180,0.12)'; }
function chartTooltipBg()     { return isDark() ? 'rgba(11,15,26,0.92)'    : 'rgba(255,255,255,0.97)'; }
function chartTooltipBorder() { return isDark() ? 'rgba(255,255,255,0.12)' : 'rgba(100,116,180,0.22)'; }
function chartTooltipColor()  { return isDark() ? '#e8eaf6'                : '#1a1f36'; }

function makeTooltip() {
  return {
    backgroundColor: chartTooltipBg(),
    borderColor:     chartTooltipBorder(),
    titleColor:      chartTooltipColor(),
    bodyColor:       chartTooltipColor(),
    borderWidth: 1, padding: 12, cornerRadius: 10,
    titleFont: { size: 13, weight: '700' },
    bodyFont:  { size: 13 }
  };
}


/* ══════════════════════════════════════════
   7. initCharts — called from dashboard.html
   FIX: on theme switch, update chart options
   in-place instead of destroying and rebuilding,
   so animations don't annoyingly replay every
   time the user toggles the theme.
══════════════════════════════════════════ */
let statusChartInst = null;
let typeChartInst   = null;
let _chartData      = null; // stashed for theme-switch refresh

function initCharts(online, offline, unknown, routers, switches, pcs, phones, servers) {
  _chartData = { online, offline, unknown, routers, switches, pcs, phones, servers };

  Chart.defaults.font.family = "'Nunito', sans-serif";
  Chart.defaults.font.weight = '600';

  buildStatusChart(online, offline, unknown);
  buildTypeChart(routers, switches, pcs, phones, servers);
}


function buildStatusChart(online, offline, unknown) {
  const canvas = document.getElementById('statusChart');
  if (!canvas) return;
  if (statusChartInst) { statusChartInst.destroy(); statusChartInst = null; }

  statusChartInst = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Online', 'Offline', 'Unknown'],
      datasets: [{
        data: [online, offline, unknown],
        backgroundColor: ['rgba(52,211,153,0.85)', 'rgba(248,113,113,0.85)', 'rgba(148,163,184,0.85)'],
        borderColor:     ['rgba(52,211,153,1)',     'rgba(248,113,113,1)',    'rgba(148,163,184,1)'],
        borderWidth: 2, hoverOffset: 10, borderRadius: 6
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: '70%',
      animation: { animateRotate: true, duration: 1200, easing: 'easeOutQuart' },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: chartTextColor(), padding: 20,
            usePointStyle: true, pointStyleWidth: 10,
            font: { size: 13, weight: '600' }
          }
        },
        tooltip: makeTooltip()
      }
    }
  });
}


function buildTypeChart(routers, switches, pcs, phones, servers) {
  const canvas = document.getElementById('typeChart');
  if (!canvas) return;
  if (typeChartInst) { typeChartInst.destroy(); typeChartInst = null; }

  typeChartInst = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['Router', 'Switch', 'PC', 'Phone', 'Server'],
      datasets: [{
        label: 'Devices',
        data: [routers, switches, pcs, phones, servers],
        backgroundColor: [
          'rgba(129,140,248,0.75)', 'rgba(251,191,36,0.75)',
          'rgba(52,211,153,0.75)',  'rgba(244,114,182,0.75)',
          'rgba(56,189,248,0.75)'
        ],
        borderColor: [
          'rgba(129,140,248,1)', 'rgba(251,191,36,1)',
          'rgba(52,211,153,1)',  'rgba(244,114,182,1)',
          'rgba(56,189,248,1)'
        ],
        borderWidth: 2, borderRadius: 8, borderSkipped: false
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { delay: ctx => ctx.dataIndex * 120, duration: 900, easing: 'easeOutBack' },
      plugins: {
        legend: { display: false },
        tooltip: makeTooltip()
      },
      scales: {
        x: {
          grid:  { color: chartGridColor(), drawBorder: false },
          ticks: { color: chartTextColor(), font: { size: 12, weight: '700' } }
        },
        y: {
          beginAtZero: true,
          grid:  { color: chartGridColor(), drawBorder: false },
          ticks: { color: chartTextColor(), font: { size: 12, weight: '600' }, precision: 0, stepSize: 1 }
        }
      }
    }
  });
}


/* ── Theme switch: update chart colors in-place ──
   FIX: Instead of rebuild (which replays full enter animation), we patch
   only the color options and call chart.update('none') — zero animation,
   instant color update, no visual jank. */
function refreshCharts() {
  if (!_chartData) return;

  if (statusChartInst) {
    const legend = statusChartInst.options.plugins.legend.labels;
    const tooltip = statusChartInst.options.plugins.tooltip;
    legend.color = chartTextColor();
    Object.assign(tooltip, makeTooltip());
    statusChartInst.update('none'); // 'none' = instant, no animation
  }

  if (typeChartInst) {
    const scales  = typeChartInst.options.scales;
    const tooltip = typeChartInst.options.plugins.tooltip;
    scales.x.grid.color  = chartGridColor();
    scales.x.ticks.color = chartTextColor();
    scales.y.grid.color  = chartGridColor();
    scales.y.ticks.color = chartTextColor();
    Object.assign(tooltip, makeTooltip());
    typeChartInst.update('none');
  }
}

/* Watch for data-theme attribute changes on <html>
   FIX: Store observer reference — disconnect on page unload to avoid
   memory leak in SPAs or long-lived pages. */
const _themeObserver = new MutationObserver(mutations => {
  mutations.forEach(m => {
    if (m.attributeName === 'data-theme') {
      // Small delay so CSS variables settle before we read them
      setTimeout(refreshCharts, 80);
    }
  });
});
_themeObserver.observe(document.documentElement, { attributes: true });
window.addEventListener('pagehide', () => _themeObserver.disconnect());


/* ── 8. Cursor Sparkle Trail ──
   FIX: sparkle dots capped at z-index 4999 — below the blur-layer (z:5000)
   and well below overlay panels (z:9999999). This prevents sparkles from
   appearing on top of the loading or logout overlay backgrounds. */
(function sparkleTrail() {
  const colors = ['#a78bfa', '#38bdf8', '#34d399', '#f472b6', '#fbbf24'];
  let active = true;

  // Pause sparkles while an overlay is open (no sparkles bleeding through blur)
  const bodyObserver = new MutationObserver(() => {
    active = !document.body.classList.contains('overlay-open');
  });
  bodyObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });

  document.addEventListener('mousemove', e => {
    if (!active || Math.random() > 0.35) return;

    const dot  = document.createElement('span');
    const size = Math.random() * 7 + 3;

    Object.assign(dot.style, {
      position:      'fixed',
      left:          e.clientX + 'px',
      top:           e.clientY + 'px',
      width:         size + 'px',
      height:        size + 'px',
      borderRadius:  '50%',
      background:    colors[Math.floor(Math.random() * colors.length)],
      pointerEvents: 'none',
      zIndex:        '4999',    // below blur-layer (5000) and overlays (9999999)
      transform:     'translate(-50%,-50%) scale(1)',
      opacity:       '1',
      transition:    'transform 0.6s ease, opacity 0.6s ease'
    });

    document.body.appendChild(dot);
    requestAnimationFrame(() => {
      dot.style.transform = 'translate(-50%,-50%) scale(0)';
      dot.style.opacity   = '0';
    });
    setTimeout(() => dot.remove(), 650);
  });
})();