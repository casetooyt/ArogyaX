/* ══════════════════════════════════════════════════════════
   Orbix Studio — Navigation & Theme (shared across all pages)
   ══════════════════════════════════════════════════════════ */

// ── Current page state ──
let currentPage = 'index';

// ── Language state ──
let currentLang = 'en';
let translations = TRANSLATIONS_EN;

// ── Initialize sidebar active state ──
document.querySelectorAll('.sidebar-item').forEach(item => {
  item.addEventListener('click', function () {
    document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
    this.classList.add('active');
  });
});

// ── Current page indicator ──
(function setSidebarActive() {
  const path = window.location.pathname;
  const map = {
    '/':             'home',
    '/page/home':    'home',
    '/page/chat':    'ai-chat',
    '/page/analytics': 'analytics',
    '/page/comparison': 'comparison',
    '/page/knowledge': 'knowledge',
    '/page/reports':  'reports',
    '/page/languages': 'languages',
  };
  let active = map[path] || 'home';
  document.querySelectorAll('.sidebar-item').forEach(item => {
    if (item.id === `nav-${active}`) item.classList.add('active');
  });
})();

// ── Navbar search ──
document.querySelector('.nav-search input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const q = e.target.value.trim();
    if (q) {
      window.location.href = `/page/knowledge?query=${encodeURIComponent(q)}`;
    }
  }
});

// ── Icon rail actions (placeholder) ──
document.querySelectorAll('.icon-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.style.transform = 'scale(0.9)';
    setTimeout(() => btn.style.transform = '', 150);
  });
});

// ── Week/period toggle ──
function initPeriodToggles(groupName) {
  const buttons = document.querySelectorAll(`[name="${groupName}"]`);
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      // Dispatch custom event for child components to listen
      document.dispatchEvent(new CustomEvent('periodChange', { detail: { name: groupName, value: btn.dataset.period } }));
    });
  });
}

// ── Generic tab pill switching ──
function initTabSwitching(selector) {
  document.querySelectorAll(selector).forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll(`${selector}.active`).forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });
}

// ── Initialize everything on DOM ready ──
document.addEventListener('DOMContentLoaded', () => {
  initPeriodToggles('period-group');
  initTabSwitching('.tab-pill');
  // Re-render Lucide icons after dynamic content loads
  if (typeof lucide !== 'undefined') lucide.createIcons();
});
