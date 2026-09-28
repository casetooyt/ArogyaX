/* ══════════════════════════════════════════════════════════
   Orbix Studio — Complete Interactive JavaScript
   ══════════════════════════════════════════════════════════ */

const COLORS = {
  lime: '#D4F547', orange: '#F04E23', dark: '#101820',
  gray: '#C4C4C4', grayLight: '#E5E5E5', blueLight: '#E0F0FF',
  green: '#16A34A',
};

let trackerChart = null;

const TRACKER_TEMPLATES = {
  Tracker:          { bars: [12,18,95,42,30,25,78],  highlights: [2,6],  percent:'3.62%', time:'09:45 AM', temp:'98.57°F' },
  MedicalAnalytics: { bars: [45,60,30,85,55,70,40],  highlights: [3],    percent:'5.18%', time:'10:12 AM', temp:'98.41°F' },
  FitnessMetrics:   { bars: [20,35,50,65,80,55,90],  highlights: [6],    percent:'2.94%', time:'07:30 AM', temp:'98.62°F' },
  Patientinsights:  { bars: [70,55,40,60,45,80,35],  highlights: [0,5],  percent:'4.37%', time:'11:00 AM', temp:'98.70°F' },
  'AI Healthcare':  { bars: [15,25,35,45,55,65,75],  highlights: [6],    percent:'6.01%', time:'08:15 AM', temp:'98.45°F' },
};

// ── Navigation Handler ──
function handleNavigation() {
  document.querySelectorAll('.sidebar-item, .feature-card, .tab-pill, .nav-btn').forEach(el => {
    el.addEventListener('click', function(e) {
      // Don't prevent default for links
      if (this.tagName === 'A') {
        // Add active state to sidebar
        document.querySelectorAll('.sidebar-item').forEach(s => s.classList.remove('active'));
        const sidebarLink = document.querySelector(`.sidebar-item[href="${this.href}"]`);
        if (sidebarLink) sidebarLink.classList.add('active');
        return;
      }

      // Button click feedback
      this.style.transform = 'scale(0.95)';
      setTimeout(() => this.style.transform = '', 150);
    });
  });
}

// ── Dashboard Functions ──
function renderTrackerChart(data) {
  const ctx = document.getElementById('trackerChart');
  if (!ctx) return;
  if (trackerChart) trackerChart.destroy();
  const t = TRACKER_TEMPLATES[data.activeTab] || TRACKER_TEMPLATES.Tracker;
  trackerChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.months || ['Jan','Feb','Mar','Apr','May','Jun','Jul'],
      datasets: [{
        data: t.bars,
        backgroundColor: t.bars.map((_, i) => t.highlights.includes(i) ? COLORS.orange : COLORS.grayLight),
        borderRadius: 6, borderSkipped: false, maxBarThickness: 28,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: COLORS.dark, titleFont: {weight:'700',size:13}, bodyFont: {size:12}, padding:10, cornerRadius:8, callbacks: {label: ctx => ` ${ctx.parsed.y}%`} } },
      scales: {
        x: { grid: {display:false}, ticks: {font:{weight:'600',size:12}, color:'#909090'}, border: {display:false} },
        y: { grid: {color:'#F0F0F0', drawBorder:false}, ticks: {font:{weight:'600',size:11}, color:'#909090', callback:v=>v+'%', max:100}, border: {display:false} }
      }
    }
  });
}

function renderBreathChart(data) {
  const container = document.getElementById('breathStems');
  if (!container) return;
  container.innerHTML = '';
  const maxVal = Math.max(...data.levels, 1);
  data.days.forEach((day, i) => {
    const pct = data.levels[i] / maxVal;
    const lineH = 20 + pct * 120;
    const stem = document.createElement('div');
    stem.className = 'breath-stem';
    stem.innerHTML = `<div class="stem-line" style="height:${lineH}px;background:${pct>0.7?COLORS.lime:COLORS.grayLight}"></div><div class="stem-dot" style="${pct>0.7?'background:'+COLORS.lime:'background:'+COLORS.gray}"></div><span class="stem-label">${day}</span>`;
    container.appendChild(stem);
  });
}

function renderDashboard() {
  Promise.all([
    fetch('/api/tracker').then(r=>r.json()),
    fetch('/api/vitals').then(r=>r.json()),
    fetch('/api/wellness').then(r=>r.json()),
    fetch('/api/breath').then(r=>r.json()),
  ]).then(([tracker, vitals, wellness, breath]) => {
    renderTrackerChart({...tracker, activeTab:'Tracker'});
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('trackerTime', tracker.time.split(' ')[0]);
    set('trackerTemp', tracker.temp);
    set('trackerPercent', tracker.percent);
    set('oxygenPct', vitals.oxygen_pct);
    set('oxygenDelta', vitals.oxygen_delta);
    set('bpmTime', vitals.bpm_time);
    set('bpmValue', vitals.bpm_value);
    set('bpmDelta', vitals.bpm_delta);
    set('kcalValue', wellness.kcal);
    set('kcalBadge', wellness.kcal_badge);
    set('calBurned', wellness.calories_burned);
    set('workouts', wellness.workouts);
    set('workoutsBadge', wellness.workouts_badge);
    set('breathChange', breath.change);
    renderBreathChart(breath);
    set('breathStatus', `Breath Level is ${breath.current_status} now ${breath.current_value}`);
    set('userId', breath.user_id);
  }).catch(err => console.error('Failed to load dashboard:', err));
}

// ── Tracker Tab Switching ──
function initTabSwitching() {
  document.querySelectorAll('.tab-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.tab-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const tabName = pill.textContent.trim();
      fetch('/api/tracker').then(r=>r.json()).then(data => {
        renderTrackerChart({...data, activeTab: tabName});
      });
    });
  });
}

// ── Wellness Tab Switching ──
function initWellnessTabs() {
  document.querySelectorAll('.wellness-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.wellness-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
    });
  });
}

// ── Dot Indicators ──
function initDotIndicators() {
  document.querySelectorAll('.dot').forEach(dot => {
    dot.addEventListener('click', () => {
      document.querySelectorAll('.dot').forEach(d => d.classList.remove('active'));
      dot.classList.add('active');
    });
  });
}

// ── Navbar Actions ──
function initNavbarActions() {
  document.querySelectorAll('.icon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.style.transform = 'scale(0.9)';
      setTimeout(() => btn.style.transform = '', 150);
    });
  });
  document.querySelectorAll('.icon-btn[title="Refresh"]').forEach(btn => {
    btn.addEventListener('click', () => window.location.reload());
  });
  document.querySelectorAll('.icon-btn[title="AI Sparkle"]').forEach(btn => {
    btn.addEventListener('click', () => { window.location.href = '/page/chat'; });
  });
  document.querySelectorAll('.date-pill[title="Notifications"]').forEach(btn => {
    btn.addEventListener('click', () => window.alert('You have 5 health updates.'));
  });

  const dateRanges = ['Sep 02 - Sep 09', 'Sep 10 - Sep 17', 'Sep 18 - Sep 25', 'Sep 26 - Oct 03'];
  const dateControl = document.querySelector('.page-header .date-pill');
  if (dateControl) {
    let dateIndex = 0;
    const dateValue = dateControl.querySelector('span');
    if (dateValue) {
      dateValue.textContent = dateRanges[dateIndex];
    }
    dateControl.addEventListener('click', (event) => {
      event.stopPropagation();
      dateIndex = (dateIndex + 1) % dateRanges.length;
      dateControl.classList.add('active');
      if (dateValue) dateValue.textContent = dateRanges[dateIndex];
      setTimeout(() => dateControl.classList.remove('active'), 180);
    });
  }

  const timeControl = document.querySelector('.page-header .header-control:not(.date-pill)');
  if (timeControl) {
    const timeValue = timeControl.querySelector('span');
    let isSevenDays = false;
    timeControl.addEventListener('click', (event) => {
      event.stopPropagation();
      isSevenDays = !isSevenDays;
      timeControl.classList.add('active');
      if (timeValue) timeValue.textContent = isSevenDays ? '7d' : '24h';
      setTimeout(() => timeControl.classList.remove('active'), 180);
    });
  }

  const weeklyButton = document.querySelector('.weekly-btn');
  if (weeklyButton) {
    let isWeekly = true;
    weeklyButton.setAttribute('aria-pressed', String(isWeekly));
    const label = weeklyButton.childNodes[0];
    if (label && label.nodeType === Node.TEXT_NODE) {
      label.textContent = 'Weekly ';
    }
    weeklyButton.addEventListener('click', (event) => {
      event.stopPropagation();
      isWeekly = !isWeekly;
      weeklyButton.classList.toggle('active', isWeekly);
      weeklyButton.setAttribute('aria-pressed', String(isWeekly));
      if (label && label.nodeType === Node.TEXT_NODE) {
        label.textContent = isWeekly ? 'Weekly ' : 'Daily ';
      }
    });
  }

  const menuButton = document.querySelector('.hamburger');
  const sidebar = document.querySelector('.sidebar');
  if (menuButton && sidebar) {
    menuButton.setAttribute('role', 'button');
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.addEventListener('click', () => {
      const isOpen = sidebar.classList.toggle('is-open');
      menuButton.setAttribute('aria-expanded', String(isOpen));
    });
  }

  document.querySelectorAll('.user-menu-button, #userMenuBtn').forEach(button => {
    const dropdown = button.closest('#userMenu')?.querySelector('#userDropdown');
    if (!dropdown) return;
    button.addEventListener('click', event => {
      event.stopPropagation();
      dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
    });
    dropdown.addEventListener('click', event => event.stopPropagation());
  });
  document.addEventListener('click', () => {
    document.querySelectorAll('#userDropdown').forEach(dropdown => { dropdown.style.display = 'none'; });
  });
}

// ── Feature Card Click Handlers ──
function initFeatureCards() {
  document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('click', () => {
      const href = card.querySelector('a')?.href || card.getAttribute('href');
      if (href) window.location.href = href;
    });
  });
}

// ── Zoom Buttons ──
function initZoomButtons() {
  document.querySelectorAll('.zoom-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.style.opacity = '0.6';
      setTimeout(() => btn.style.opacity = '1', 150);
      const chart = btn.closest('.card')?.querySelector('canvas');
      if (chart && trackerChart) {
        const scale = btn.textContent.trim() === '+' ? 1.15 : 0.88;
        trackerChart.options.plugins.tooltip = trackerChart.options.plugins.tooltip || {};
        chart.style.transform = `scale(${scale})`;
        chart.style.transformOrigin = 'center bottom';
      }
    });
  });
}

// ── Toggle Buttons ──
function initToggleButtons() {
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.style.opacity = '0.6';
      setTimeout(() => btn.style.opacity = '1', 150);
      btn.closest('.toggle-group')?.querySelectorAll('.toggle-btn').forEach(item => item.classList.remove('active'));
      btn.classList.add('active');
    });
  });
  document.querySelectorAll('.breath-icon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const status = document.getElementById('breathStatus');
      if (status) status.textContent = 'Scanning breath level...';
      setTimeout(() => { if (status) status.textContent = 'Breath Level is Normal now 12'; }, 1200);
    });
  });
}

// ── Period Toggles ──
function initPeriodToggles() {
  document.querySelectorAll('.period-btn, .comparison-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const groupName = btn.name || btn.closest('[class*="toggle"], [class*="group"]')?.className;
      document.querySelectorAll(`[class*="${groupName || 'btn'}"]`).forEach(b => {
        if (b !== btn) b.classList.remove('active');
      });
      btn.classList.add('active');
    });
  });
}

// ── Reports Page Functions ──
function initReportsPage() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');

  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      if (e.dataTransfer.files.length > 0) processFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) processFile(e.target.files[0]);
    });
  }

  // Browse Files button
  const browseBtn = document.getElementById('browseBtn');
  if (browseBtn) browseBtn.addEventListener('click', () => fileInput?.click());

  // Paste Text button
  const pasteBtn = document.getElementById('pasteBtn');
  if (pasteBtn) {
    pasteBtn.addEventListener('click', () => {
      const text = prompt('Paste your report text here:');
      if (text) processOCR(text);
    });
  }

  // Try Sample Report button
  const sampleBtn = document.getElementById('sampleBtn');
  if (sampleBtn) {
    sampleBtn.addEventListener('click', () => {
      processOCR(`LABORATORY REPORT
Patient: Rahul Sharma
Age: 28 Years
Date: 2024-08-25

TEST RESULTS:

Hemoglobin: 14.5 g/dL
Total WBC: 7500 /µL
RBC Count: 5.2 million/µL
Platelet Count: 250,000 /µL
Fasting Glucose: 88 mg/dL
Postprandial Glucose: 112 mg/dL
Serum Creatinine: 0.9 mg/dL
Uric Acid: 5.2 mg/dL
Total Cholesterol: 185 mg/dL
LDL Cholesterol: 95 mg/dL
HDL Cholesterol: 55 mg/dL
Triglycerides: 120 mg/dL
TSH: 2.5 mIU/L`);
    });
  }

  const downloadBtn = document.getElementById('downloadBtn');
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      const preview = document.getElementById('ocrPreview');
      const text = preview?.textContent?.trim();
      if (!text) {
        window.alert('Scan a report before exporting it.');
        return;
      }
      const blob = new Blob([text], {type: 'text/plain;charset=utf-8'});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `orbix-health-report-${new Date().toISOString().slice(0, 10)}.txt`;
      link.click();
      URL.revokeObjectURL(link.href);
    });
  }
}

function processFile(file) {
  const dropZone = document.getElementById('dropZone');
  if (!file) return;

  if (dropZone) {
    dropZone.innerHTML = `
      <div style="animation: spin 1s linear infinite">
        <i data-lucide="loader" style="width:48px;height:48px;color:#D4F547;margin:0 auto 16px;display:block"></i>
      </div>
      <div style="font-size:16px;font-weight:700;margin-bottom:8px">Processing ${file.name}...</div>
      <div style="font-size:13px;color:#909090">Extracting and analyzing health parameters</div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  extractTextFromFile(file)
    .then((text) => {
      if (!text || !text.trim()) {
        throw new Error('No readable text found in the uploaded file.');
      }
      return analyzeReportText(text);
    })
    .catch((error) => {
      console.error('Report processing failed:', error);
      const message = error?.message || 'Unable to analyze this report yet.';
      if (dropZone) {
        dropZone.innerHTML = `
          <i data-lucide="alert-triangle" style="width:48px;height:48px;color:#F04E23;margin:0 auto 16px"></i>
          <div class="drop-zone-text">Could not read this file</div>
          <div class="drop-zone-sub">${message}. Please paste the report text or try a PNG/JPG/TXT/PDF file.</div>
        `;
        if (typeof lucide !== 'undefined') lucide.createIcons();
      }
    });
}

async function waitForGlobal(globalName, timeoutMs = 10000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      if (window[globalName]) {
        resolve(window[globalName]);
        return;
      }
      if (Date.now() - started > timeoutMs) {
        reject(new Error(`${globalName} is not available.`));
        return;
      }
      setTimeout(poll, 150);
    };
    poll();
  });
}

async function ensureScriptLoaded(src, globalName) {
  if (window[globalName]) return window[globalName];

  const existing = document.querySelector(`script[src="${src}"]`);
  if (!existing) {
    await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      script.dataset.orbix = globalName;
      document.head.appendChild(script);
    });
  }

  return waitForGlobal(globalName, 15000);
}

async function ensurePdfLibrary() {
  const pdfSources = [
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.js',
    'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.7.76/legacy/build/pdf.min.js',
    'https://unpkg.com/pdfjs-dist@4.7.76/legacy/build/pdf.min.js',
  ];

  let lastError = null;
  for (const src of pdfSources) {
    try {
      return await ensureScriptLoaded(src, 'pdfjsLib');
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('PDF extraction library not loaded.');
}

async function ensureTesseractLibrary() {
  const tesseractSources = [
    'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js',
    'https://unpkg.com/tesseract.js@5/dist/tesseract.min.js',
  ];

  let lastError = null;
  for (const src of tesseractSources) {
    try {
      return await ensureScriptLoaded(src, 'Tesseract');
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('Image OCR library not loaded.');
}

async function extractTextFromFile(file) {
  const name = (file.name || '').toLowerCase();
  const fileType = file.type || '';

  if (fileType.startsWith('text/') || /\.(txt|csv|json)$/i.test(name)) {
    return await file.text();
  }

  if (/\.pdf$/i.test(name)) {
    try {
      await ensurePdfLibrary();
      const pdfjsLib = window.pdfjsLib;
      if (!pdfjsLib) {
        throw new Error('PDF extraction library not loaded.');
      }

      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      let text = '';
      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum += 1) {
        const page = await pdf.getPage(pageNum);
        const content = await page.getTextContent();
        text += (content.items || []).map(item => item.str || '').join(' ') + '\n';
      }
      return text;
    } catch (error) {
      const fallbackText = await file.text().catch(() => '');
      if (fallbackText && fallbackText.trim()) {
        return fallbackText;
      }
      throw error;
    }
  }

  if (fileType.startsWith('image/') || /\.(png|jpe?g|webp|bmp)$/i.test(name)) {
    try {
      await ensureTesseractLibrary();
      const result = await window.Tesseract.recognize(file, 'eng');
      return result?.data?.text || '';
    } catch (error) {
      const fallbackText = await file.text().catch(() => '');
      if (fallbackText && fallbackText.trim()) {
        return fallbackText;
      }
      throw error;
    }
  }

  return await file.text();
}

async function analyzeReportText(text) {
  const response = await fetch('/api/report/ocr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ text })
  });

  const data = await response.json();
  if (!response.ok || !Array.isArray(data.params) || data.params.length === 0) {
    throw new Error('No health measurements could be read from this report.');
  }

  renderResults(data.params, text);
  return data;
}

function getStatusColor(status) {
  if (status === 'Normal') return '#16A34A';
  if (status === 'High') return '#F04E23';
  return '#2563EB';
}

function renderResults(params, text) {
  const summaryCards = document.getElementById('summaryCards');
  const tbody = document.getElementById('parameterBody');
  const ocrPreview = document.getElementById('ocrPreview');
  const scanResult = document.getElementById('scanResult');
  const insight = document.getElementById('aiInsight');

  if (!summaryCards || !tbody) return;

  const normalCount = params.filter(p => p.status === 'Normal').length;
  const abnormalCount = params.filter(p => p.status !== 'Normal').length;

  summaryCards.innerHTML = `
    <div class="summary-card"><div class="summary-value" style="color:#16A34A">${normalCount}</div><div class="summary-label">Normal Parameters</div></div>
    <div class="summary-card"><div class="summary-value" style="color:${abnormalCount > 0 ? '#F04E23' : '#16A34A'}">${abnormalCount}</div><div class="summary-label">Abnormal Parameters</div></div>
    <div class="summary-card"><div class="summary-value">${params.length}</div><div class="summary-label">Total Parameters</div></div>
  `;

  tbody.innerHTML = params.map((p) => {
    const statusColor = getStatusColor(p.status);
    const value = p.value ?? '—';
    const range = p.ref_range || `${p.low ?? 0}-${p.high ?? 0}`;
    const unit = p.unit || '';
    const explanation = p.explanation || 'Health parameter reviewed.';

    return `
      <tr>
        <td><strong>${p.name}</strong></td>
        <td>${value} <span style="font-size:12px;color:#909090">${unit}</span></td>
        <td>${range} ${unit}</td>
        <td style="color:${statusColor};font-weight:700">${p.status}</td>
        <td style="font-size:12px;color:#909090">${explanation}</td>
      </tr>
    `;
  }).join('');

  if (ocrPreview) ocrPreview.textContent = text;
  if (scanResult) {
    scanResult.style.display = 'block';
    scanResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  if (insight) {
    if (abnormalCount === 0) {
      insight.textContent = 'Great news! Most of the reviewed health markers are within the expected range. Continue regular checkups and a balanced lifestyle.';
    } else {
      const issueNames = params.filter(p => p.status !== 'Normal').slice(0, 3).map(p => p.name).join(', ');
      insight.textContent = `Analysis complete. ${normalCount} parameters are normal, but ${abnormalCount} item(s) need attention: ${issueNames}. Please review these values with a clinician and consider follow-up if symptoms persist.`;
    }
  }

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function getRecentScanItems(currentStatus = 'normal', latestName = 'Latest report') {
  const base = [
    { name: latestName, uploaded: 'Uploaded just now', tone: currentStatus },
    { name: 'Complete Blood Count (CBC)', uploaded: 'Uploaded 2 days ago', tone: 'normal' },
    { name: 'Lipid Profile', uploaded: 'Uploaded 1 week ago', tone: 'alert' },
    { name: 'Thyroid Function Test', uploaded: 'Uploaded 2 weeks ago', tone: 'normal' },
    { name: 'Vitamin D Panel', uploaded: 'Uploaded 1 month ago', tone: 'normal' },
    { name: 'Renal Function Test', uploaded: 'Uploaded 2 months ago', tone: 'alert' }
  ];

  return base;
}

function renderRecentScanHistory(items, expanded = false) {
  const container = document.getElementById('scanHistory');
  const button = document.getElementById('viewAllScans');
  if (!container) return;

  const visibleItems = expanded ? items : items.slice(0, 3);

  container.innerHTML = visibleItems.map((item) => {
    const isNormal = item.tone === 'normal';
    const pillClass = isNormal ? 'lime-pill' : 'orange-pill';
    const pillText = isNormal ? 'All Normal' : '1 Alert';
    const iconBg = isNormal ? 'var(--blue-light)' : 'var(--yellow-light)';
    const iconColor = isNormal ? '#2563EB' : '#D97706';

    return `
      <div style="display:flex;align-items:center;gap:16px;padding:12px;border-bottom:1px solid var(--gray-200)">
        <div style="width:40px;height:40px;border-radius:10px;background:${iconBg};display:flex;align-items:center;justify-content:center">
          <i data-lucide="file-text" style="width:20px;height:20px;color:${iconColor}"></i>
        </div>
        <div style="flex:1">
          <div style="font-size:14px;font-weight:700">${item.name}</div>
          <div style="font-size:12px;color:var(--gray-500)">${item.uploaded}</div>
        </div>
        <span class="${pillClass}">${pillText}</span>
      </div>
    `;
  }).join('');

  if (button) {
    button.textContent = expanded ? 'Collapse' : 'View All';
    button.onclick = () => {
      const nextExpanded = !expanded;
      renderRecentScanHistory(items, nextExpanded);
    };
  }

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function syncRecentScansWithReport(params = []) {
  const abnormalCount = params.filter((p) => p.status !== 'Normal').length;
  const currentStatus = abnormalCount > 0 ? 'alert' : 'normal';
  const paramNames = params.slice(0, 3).map((p) => p.name).filter(Boolean);
  const latestName = paramNames.length > 0 ? `Latest report (${paramNames.join(' • ')})` : 'Latest report';
  renderRecentScanHistory(getRecentScanItems(currentStatus, latestName), false);
}

function processOCR(text) {
  if (!text || !text.trim()) return;
  analyzeReportText(text)
    .then((data) => {
      const params = data && Array.isArray(data.params) ? data.params : [];
      syncRecentScansWithReport(params);
    })
    .catch((error) => {
      console.error('OCR analysis failed:', error);
      const insight = document.getElementById('aiInsight');
      if (insight) {
        insight.textContent = 'The report text was read, but no valid lab markers were detected. Try a clearer scan or paste the raw lab values.';
      }
      renderRecentScanHistory(getRecentScanItems('alert'), false);
    });
}

function initReportHistory() {
  renderRecentScanHistory(getRecentScanItems('normal'), false);
}

// ── Chat Page Functions ──
function initChatPage() {
  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');

  if (!chatMessages || !chatInput) return;

  function addBotMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'chat-msg bot animate-in';
    msg.innerHTML = `
      <div class="chat-avatar bot" style="width:40px;height:40px;border-radius:50%;background:#D4F547;display:flex;align-items:center;justify-content:center"><i data-lucide="bot" style="width:20px;height:20px"></i></div>
      <div class="chat-bubble" style="max-width:100%">${text}</div>
    `;
    chatMessages.appendChild(msg);
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function addUserMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'chat-msg user animate-in';
    msg.innerHTML = `
      <div class="chat-avatar" style="width:40px;height:40px;border-radius:50%;background:#101820;color:#fff;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700">R</div>
      <div class="chat-bubble" style="max-width:100%">${text}</div>
    `;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showTyping() {
    const typing = document.createElement('div');
    typing.className = 'chat-msg bot';
    typing.id = 'typingIndicator';
    typing.innerHTML = `
      <div class="chat-avatar bot" style="width:40px;height:40px;border-radius:50%;background:#D4F547;display:flex;align-items:center;justify-content:center"><i data-lucide="bot" style="width:20px;height:20px"></i></div>
      <div style="display:flex;gap:4px;padding:12px 16px;background:#F4F4F4;border-radius:16px;border-top-left-radius:4px">
        <div style="width:8px;height:8px;border-radius:50%;background:#909090;animation:typing 1.4s infinite"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#909090;animation:typing 1.4s infinite 0.2s"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#909090;animation:typing 1.4s infinite 0.4s"></div>
      </div>
    `;
    chatMessages.appendChild(typing);
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeTyping() {
    const typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
  }

  function generateResponse(userMessage) {
    const msg = userMessage.toLowerCase();
    const redFlags = [
      { keywords: ['chest pain', 'chest tightness'], response: '⚠️ <strong>CHEST PAIN DETECTED</strong> — This could be serious. Please seek emergency medical attention immediately. Call 108 or go to the nearest hospital.', level: 'urgent' },
      { keywords: ['difficulty breathing', 'breathing problem'], response: '⚠️ <strong>BREATHING DIFFICULTY DETECTED</strong> — This requires immediate medical attention. Call emergency services (108/112) right away.', level: 'urgent' },
      { keywords: ['severe headache', 'worst headache'], response: '⚠️ <strong>SEVERE HEADACHE</strong> — If this is the worst headache of your life or came on suddenly, seek medical care immediately.', level: 'high' },
    ];

    for (const flag of redFlags) {
      if (flag.keywords.some(k => msg.includes(k))) return { text: flag.response, level: flag.level };
    }

    if (msg.includes('headache')) {
      return { text: 'I understand you\'re experiencing headaches. To better understand your situation, can you tell me:<br/><br/>1. <strong>Where</strong> is the pain located? (front, back, one side, all around)<br/>2. <strong>How long</strong> have you had these headaches?<br/>3. <strong>On a scale of 1-10</strong>, how severe is the pain?<br/><br/>This will help me provide more relevant guidance.', level: 'low', followUp: true };
    }

    if (msg.includes('fatigue') || msg.includes('tired')) {
      return { text: 'Persistent fatigue can have many causes. Let me ask a few questions:<br/><br/>• How many hours of sleep are you getting per night?<br/>• Have you noticed any changes in your appetite or weight?<br/>• Are you feeling stressed or anxious lately?<br/><br/>Your recent vitals show normal oxygen (97.5%) and resting heart rate (72 bpm), which is good.', level: 'moderate', followUp: true };
    }

    if (msg.includes('hello') || msg.includes('hi')) {
      return { text: 'Hello! I\'m your AI health companion. I can help you with symptoms, nutrition guidance, sleep analysis, and more.<br/><br/>What would you like to discuss today?', level: 'low', followUp: false };
    }

    return { text: 'Thank you for sharing that information. Based on your health profile, I can provide some general guidance.<br/><br/>Could you tell me more about:<br/>• How long have you been experiencing this?<br/>• What makes it better or worse?<br/>• Any other symptoms you\'ve noticed?<br/><br/>This will help me give you more personalized recommendations.', level: 'moderate', followUp: true };
  }

  function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    addUserMessage(message);
    chatInput.value = '';
    chatInput.style.height = 'auto';

    showTyping();

    setTimeout(() => {
      removeTyping();
      const response = generateResponse(message);
      addBotMessage(response.text);

      if (response.level !== 'low') {
        const badge = document.createElement('div');
        badge.className = `lime-pill ${response.level === 'urgent' ? '' : response.level === 'high' ? '' : ''}`;
        badge.style.cssText = response.level === 'urgent' ? 'background:#FFEBEE;color:#991B1B;margin-top:8px;padding:8px 16px;border-radius:50px;font-size:12px;font-weight:700;display:inline-block' : 'margin-top:8px';
        badge.textContent = `Concern: ${response.level.charAt(0).toUpperCase() + response.level.slice(1)}`;
        chatMessages.appendChild(badge);
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    }, 1500);
  }

  if (chatSendBtn) chatSendBtn.addEventListener('click', sendMessage);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });

  // Add welcome message
  setTimeout(() => addBotMessage('Hello Rahul! 👋 I\'m your AI health companion. I can help you with symptoms, nutrition guidance, sleep analysis, and more.<br/><br/>What would you like to discuss today?'), 500);
}

// ── Analytics Page Functions ──
function initAnalyticsPage() {
  const subtitle = document.querySelector('.section-header .section-subtitle');
  // Period toggle
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (subtitle) subtitle.textContent = `Track your health metrics for the last ${btn.dataset.period} days`;
      document.dispatchEvent(new CustomEvent('analyticsPeriodChange', {detail: btn.dataset.period}));
    });
  });
}

// ── Comparison Page Functions ──
function initComparisonPage() {
  const subtitle = document.querySelector('.section-header .section-subtitle');
  const compareLabel = document.querySelector('.comparison-tabs + .btn-outline');
  document.querySelectorAll('.comparison-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.comparison-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const period = tab.dataset.period;
      if (subtitle) subtitle.textContent = `Compare your health metrics across the last ${period} days`;
      if (compareLabel) compareLabel.lastChild.textContent = `This ${period}-day period vs previous period`;
      document.dispatchEvent(new CustomEvent('comparisonPeriodChange', {detail: period}));
    });
  });
}

// ── Languages Page Functions ──
function initLanguagesPage() {
  const translations = {
    en: { greeting: "Hello! I'm your AI health companion. How can I help you today?", question: "I have been feeling tired lately. What should I do?", response: "Persistent fatigue can have many causes. Let me ask a few questions..." },
    hi: { greeting: "नमस्ते! मैं आपका AI स्वास्थ्य सहायक हूं। मैं आज आपकी कैसे मदद कर सकता हूं?", question: "मुझे पिछले कुछ समय से थकान महसूस हो रही है। मुझे क्या करना चाहिए?", response: "लगातार थकान के कई कारण हो सकते हैं।" },
    or: { greeting: "ନମସ୍କାର! ମୁଁ ଆପଣଙ୍କର AI ସ୍ୱାସ୍ଥ୍ୟ ସହାୟକ।", question: "ମୁଁ ପଶ୍ଚିମକାଳରୁ ଥକ୍କା ଅନୁଭବ କରୁଅଛି।", response: "ନିରନ୍ତର ଥକ୍କାର ଅନେକ କାରଣ ହୋଇପାରେ।" },
    es: { greeting: "¡Hola! Soy tu compañero de salud AI.", question: "He estado sintiéndome cansado últimamente.", response: "La fatiga persistente puede tener muchas causas." },
    fr: { greeting: "Bonjour! Je suis votre compagnon santé IA.", question: "Je me sens fatigué ces derniers temps.", response: "La fatigue persistante peut avoir de nombreuses causes." },
  };

  document.querySelectorAll('.lang-card').forEach(card => {
    card.addEventListener('click', function() {
      if (this.dataset.lang === 'add') return;
      localStorage.setItem('orbix-language', this.dataset.lang);
      document.querySelectorAll('.lang-card').forEach(c => c.classList.remove('active'));
      this.classList.add('active');
      const lang = this.dataset.lang;
      updatePreview(lang);
    });
  });

  document.querySelectorAll('[data-preview]').forEach(btn => {
    btn.addEventListener('click', function() {
      document.querySelectorAll('[data-preview]').forEach(b => {
        b.style.background = '';
        b.style.color = '';
      });
      this.style.background = '#D4F547';
      this.style.color = '#101820';
      updatePreview(this.dataset.preview);
    });
  });

  function updatePreview(lang) {
    const data = translations[lang] || translations.en;
    const t1 = document.getElementById('previewText1');
    const t2 = document.getElementById('previewText2');
    const t3 = document.getElementById('previewText3');
    if (t1) t1.textContent = data.greeting;
    if (t2) t2.textContent = data.question;
    if (t3) t3.textContent = data.response;
  }

  const copyBtn = document.getElementById('copyCode');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const code = document.getElementById('translationCode');
      if (code) {
        navigator.clipboard.writeText(code.textContent).then(() => {
          copyBtn.innerHTML = '<i data-lucide="check" style="width:12px;height:12px"></i> Copied!';
          setTimeout(() => { copyBtn.innerHTML = '<i data-lucide="copy" style="width:12px;height:12px"></i> Copy'; }, 2000);
        });
      }
    });
  }
}

function initSharedChrome() {
  const navbar = document.querySelector('.navbar');
  const navRight = navbar?.querySelector('.nav-right');
  if (navbar && navRight && !navbar.querySelector('.nav-search')) {
    const search = document.createElement('div');
    search.className = 'nav-center nav-search';
    search.innerHTML = '<i data-lucide="search"></i><input type="search" placeholder="Search anything..." aria-label="Search health knowledge" />';
    navbar.insertBefore(search, navRight);
    search.querySelector('input').addEventListener('keydown', event => {
      if (event.key === 'Enter' && event.target.value.trim()) {
        window.location.href = `/page/knowledge?query=${encodeURIComponent(event.target.value.trim())}`;
      }
    });
  }

  if (navbar && navRight && !navbar.querySelector('.global-language')) {
    const language = document.createElement('select');
    language.className = 'global-language';
    language.setAttribute('aria-label', 'Select language');
    const languageOptions = [
      ['en', 'EN'], ['as', 'অসমীয়া'], ['bn', 'বাংলা'], ['brx', 'बड़ो'], ['doi', 'डोगरी'],
      ['gu', 'ગુજરાતી'], ['hi', 'हिन्दी'], ['kn', 'ಕನ್ನಡ'], ['ks', 'कॉशुर'], ['kok', 'कोंकणी'],
      ['mai', 'मैथिली'], ['ml', 'മലയാളം'], ['mni', 'মৈতৈলোন্'], ['mr', 'मराठी'], ['ne', 'नेपाली'],
      ['or', 'ଓଡ଼ିଆ'], ['pa', 'ਪੰਜਾਬੀ'], ['sa', 'संस्कृतम्'], ['sat', 'ᱥᱟᱱᱛᱟᱲᱤ'], ['sd', 'سنڌي'],
      ['ta', 'தமிழ்'], ['te', 'తెలుగు'], ['ur', 'اردو'], ['es', 'ES'], ['fr', 'FR']
    ];
    language.innerHTML = languageOptions.map(([code, label]) => `<option value="${code}">${label}</option>`).join('');
    language.value = localStorage.getItem('orbix-language') || 'en';
    language.addEventListener('change', () => {
      localStorage.setItem('orbix-language', language.value);
      document.documentElement.lang = language.value;
      window.dispatchEvent(new CustomEvent('orbixLanguageChange', {detail: language.value}));
      window.location.reload();
    });
    navbar.insertBefore(language, navRight);
    document.documentElement.lang = language.value;
  }

  const sidebar = document.querySelector('.sidebar');
  if (sidebar) {
    const links = [
      ['care', '/page/care', 'heart-handshake', 'Care Hub'],
    ];
    const spacer = sidebar.querySelector('.sidebar-spacer');
    links.forEach(([id, href, icon, label]) => {
      if (sidebar.querySelector(`#nav-${id}`)) return;
      const link = document.createElement('a');
      link.href = href;
      link.id = `nav-${id}`;
      link.className = 'sidebar-item';
      link.innerHTML = `<i data-lucide="${icon}"></i><span>${label}</span>`;
      sidebar.insertBefore(link, spacer || sidebar.lastElementChild);
    });
    const activePath = window.location.pathname;
    sidebar.querySelectorAll('.sidebar-item').forEach(item => {
      if (item.getAttribute('href') === activePath) item.classList.add('active');
    });
  }

  document.querySelectorAll('a[href="#"]').forEach(link => {
    link.addEventListener('click', event => event.preventDefault());
  });
}

function initChatActions() {
  const messages = document.getElementById('chatMessages');
  const input = document.getElementById('chatInput');
  if (!messages || !input) return;

  const newChat = document.querySelector('.chat-sidebar .btn-lime');
  newChat?.addEventListener('click', () => {
    messages.innerHTML = '<div class="chat-msg bot"><div class="chat-bubble">New conversation started. How can I help with your health today?</div></div>';
    input.focus();
  });

  const quickActions = document.querySelectorAll('.chat-right-panel .btn-outline');
  quickActions.forEach((button, index) => button.addEventListener('click', () => {
    if (index === 0) {
      input.value = 'I want to log a new symptom';
      input.focus();
    } else {
      messages.scrollTo({top: messages.scrollHeight, behavior: 'smooth'});
    }
  }));

  const attachment = document.querySelector('.chat-input-area .icon-btn');
  attachment?.addEventListener('click', () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf,.jpg,.jpeg,.png,.txt';
    fileInput.addEventListener('change', () => {
      if (fileInput.files?.[0]) input.value = `Attached: ${fileInput.files[0].name}`;
    });
    fileInput.click();
  });
}

function initUserIdentity() {
  fetch('/api/me', {credentials: 'include'})
    .then(response => response.ok ? response.json() : null)
    .then(data => {
      const user = data?.user;
      if (!user) return;
      const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'User';
      document.querySelectorAll('[data-user-name]').forEach(element => { element.textContent = fullName; });
      document.querySelectorAll('[data-user-first-name]').forEach(element => { element.textContent = user.first_name || 'User'; });
      document.querySelectorAll('[data-user-avatar]').forEach(element => { element.textContent = fullName.charAt(0).toUpperCase(); });
      document.querySelectorAll('[data-user-age]').forEach(element => { element.textContent = user.age || '-'; });
      document.querySelectorAll('[data-user-gender]').forEach(element => { element.textContent = user.gender || '-'; });
      document.querySelectorAll('[data-user-weight]').forEach(element => { element.textContent = user.weight || '-'; });
      document.querySelectorAll('[data-user-height]').forEach(element => { element.textContent = user.height || '-'; });
      localStorage.setItem('orbix-user-name', fullName);
    })
    .catch(() => {});
}

// ── Initialize Everything ──
document.addEventListener('DOMContentLoaded', () => {
  // Determine which page we're on and initialize accordingly
  const path = window.location.pathname;
  initSharedChrome();
  initUserIdentity();

  // Always initialize common features
  handleNavigation();
  initTabSwitching();
  initWellnessTabs();
  initDotIndicators();
  initNavbarActions();
  initZoomButtons();
  initToggleButtons();
  initPeriodToggles();

  if (typeof lucide !== 'undefined') lucide.createIcons();

  // Page-specific initialization
  if (path === '/' || path === '/index.html' || path === '') {
    renderDashboard();
    initFeatureCards();
  }

  if (path.includes('/page/chat')) {
    // chat.html has its own controller; avoid attaching a second send handler.
    initChatActions();
  }

  if (path.includes('/page/knowledge')) {
    // knowledge.html owns this page's richer renderer and search controller.
  }

  if (path.includes('/page/reports')) {
    initReportsPage();
    initReportHistory();
  }

  if (path.includes('/page/analytics')) {
    initAnalyticsPage();
  }

  if (path.includes('/page/comparison')) {
    initComparisonPage();
  }

  if (path.includes('/page/languages')) {
    initLanguagesPage();
  }
});
