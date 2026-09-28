(() => {
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);

  const relationLabels = { self: 'Primary account', spouse: 'Spouse', child: 'Child', parent: 'Parent', other: 'Family' };
  const main = document.querySelector('.main-content');
  if (!main || !document.querySelector('.navbar')) return;

  const toolbar = document.createElement('section');
  toolbar.className = 'family-switcher';
  toolbar.setAttribute('aria-label', 'Family health profiles');
  toolbar.innerHTML = `
    <div class="family-switcher-label"><span>Household</span><strong>Health profiles</strong></div>
    <div class="family-members" id="familyMembers" role="group" aria-label="Choose who this health activity is for"></div>
    <button class="family-add-button" type="button" id="familyAddButton">+ Add family member</button>
    <div class="family-status" id="familyStatus" aria-live="polite">Loading family profiles...</div>
  `;
  main.prepend(toolbar);

  const isDashboard = window.location.pathname === '/' || window.location.pathname === '/index.html';
  let dashboard;
  if (isDashboard) {
    dashboard = document.createElement('section');
    dashboard.className = 'family-dashboard';
    dashboard.setAttribute('aria-label', 'Family health overview');
    dashboard.innerHTML = `
      <div class="family-dashboard-header">
        <div><h2 id="familyOverviewTitle">Household health</h2><p id="familyOverviewSubtitle">Health history stays organized by person.</p></div>
        <span class="lime-pill" id="familyMemberCount">1 profile</span>
      </div>
      <div id="familyAlerts"></div>
      <div class="family-dashboard-grid">
        <section class="family-dashboard-panel" aria-labelledby="familyHistoryHeading">
          <h3 id="familyHistoryHeading">Selected member's health history</h3>
          <div id="familyHistoryList" class="family-empty">No saved health entries for this profile yet.</div>
        </section>
        <section class="family-dashboard-panel" aria-labelledby="familyVaccinationsHeading">
          <h3 id="familyVaccinationsHeading">Shared vaccination calendar</h3>
          <form id="familyVaccinationForm" class="family-vaccine-form">
            <label>Vaccine or dose<input name="name" maxlength="100" required placeholder="e.g. Booster dose" /></label>
            <label>For<input name="member_name" id="familyVaccineMember" list="familyMemberOptions" required placeholder="Member name" /></label>
            <datalist id="familyMemberOptions"></datalist>
            <label>Due date<input name="due_date" type="date" required /></label>
            <button type="submit">Add date</button>
          </form>
          <div id="familyVaccinationList" class="family-empty">No vaccination dates added yet.</div>
        </section>
      </div>
    `;
    toolbar.insertAdjacentElement('afterend', dashboard);
  }

  const dialog = document.createElement('dialog');
  dialog.className = 'family-dialog';
  dialog.setAttribute('aria-labelledby', 'familyDialogTitle');
  dialog.innerHTML = `
    <form class="family-dialog-form" id="familyMemberForm">
      <h2 id="familyDialogTitle">Add family member</h2>
      <p>Create a separate health profile under this household login.</p>
      <label>Full name<input name="name" maxlength="80" autocomplete="name" required /></label>
      <div class="family-form-grid">
        <label>Age<input name="age" type="number" min="0" max="120" inputmode="numeric" /></label>
        <label>Relation<select name="relation" required><option value="">Choose</option><option value="spouse">Spouse</option><option value="child">Child</option><option value="parent">Parent</option><option value="other">Other family</option></select></label>
      </div>
      <label>Gender (optional)<select name="gender"><option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></select></label>
      <div class="family-status" id="familyFormStatus" role="status"></div>
      <div class="family-dialog-actions"><button type="button" id="familyCancelButton">Cancel</button><button type="submit">Save profile</button></div>
    </form>
  `;
  document.body.appendChild(dialog);

  const status = document.getElementById('familyStatus');
  const membersElement = document.getElementById('familyMembers');
  const memberForm = document.getElementById('familyMemberForm');
  let family = null;

  function renderMembers() {
    const selectedId = family.selected_member_id;
    membersElement.innerHTML = family.members.map(member => {
      const relation = relationLabels[member.relation] || 'Family';
      const selected = member.id === selectedId;
      return `<button type="button" class="family-member-button" data-member-id="${escapeHtml(member.id)}" aria-pressed="${selected}">
        <span class="family-avatar" aria-hidden="true">${escapeHtml(member.name.trim().charAt(0).toUpperCase() || '?')}</span>
        <span class="family-member-copy"><strong>${escapeHtml(member.name)}</strong><small>${escapeHtml(relation)}${member.age === null || member.age === undefined ? '' : ` · ${escapeHtml(member.age)} yrs`}</small></span>
      </button>`;
    }).join('');
    const selectedMember = family.members.find(member => member.id === selectedId);
    status.textContent = selectedMember ? `Health activity will be saved for ${selectedMember.name}.` : 'Choose a family profile.';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  function renderDashboard() {
    if (!dashboard) return;
    const selectedMember = family.members.find(member => member.id === family.selected_member_id);
    document.getElementById('familyOverviewTitle').textContent = selectedMember ? `${selectedMember.name}'s health overview` : 'Household health';
    document.getElementById('familyOverviewSubtitle').textContent = selectedMember ? `Records and check-ins saved for ${selectedMember.name}.` : 'Health history stays organized by person.';
    document.getElementById('familyMemberCount').textContent = `${family.members.length} ${family.members.length === 1 ? 'profile' : 'profiles'}`;

    const alerts = document.getElementById('familyAlerts');
    alerts.innerHTML = family.alerts.map(alert => `<div class="family-alert"><strong>Family symptom pattern:</strong> ${escapeHtml(alert.symptom)} was reported for ${alert.member_count} family members in the last two days (${alert.member_names.map(escapeHtml).join(', ')}). This is a prompt to check in, not a diagnosis.</div>`).join('');

    const history = family.records[family.selected_member_id] || [];
    const historyList = document.getElementById('familyHistoryList');
    historyList.className = history.length ? '' : 'family-empty';
    historyList.innerHTML = history.length ? history.slice(0, 5).map(record => `
      <div class="family-record-row"><div><strong>${escapeHtml(record.title || record.type || 'Health record')}</strong><p>${escapeHtml(record.summary || record.symptom || '')}</p></div><small>${escapeHtml((record.created_at || '').slice(0, 10))}</small></div>
    `).join('') : 'No saved health entries for this profile yet.';

    const options = document.getElementById('familyMemberOptions');
    options.innerHTML = family.members.map(member => `<option value="${escapeHtml(member.name)}"></option>`).join('');
    const vaccinationList = document.getElementById('familyVaccinationList');
    const vaccinations = family.vaccinations.slice().sort((first, second) => first.due_date.localeCompare(second.due_date));
    vaccinationList.className = vaccinations.length ? '' : 'family-empty';
    vaccinationList.innerHTML = vaccinations.length ? vaccinations.slice(0, 5).map(item => `
      <div class="family-vaccine-row"><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.member_name || 'Family member')}</small></div><small>${escapeHtml(item.due_date)}</small></div>
    `).join('') : 'No vaccination dates added yet.';
  }

  async function loadFamily() {
    try {
      const response = await fetch('/api/family', { credentials: 'include' });
      if (!response.ok) throw new Error('Family profiles could not be loaded.');
      family = await response.json();
      renderMembers();
      renderDashboard();
    } catch (error) {
      status.textContent = error.message || 'Family profiles could not be loaded.';
    }
  }

  toolbar.addEventListener('click', async event => {
    const memberButton = event.target.closest('[data-member-id]');
    if (memberButton && family && memberButton.dataset.memberId !== family.selected_member_id) {
      memberButton.disabled = true;
      try {
        const response = await fetch('/api/family/active', {
          method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ member_id: memberButton.dataset.memberId })
        });
        if (!response.ok) throw new Error('Could not switch family profile.');
        window.location.reload();
      } catch (error) {
        memberButton.disabled = false;
        status.textContent = error.message;
      }
      return;
    }
    if (event.target.closest('#familyAddButton')) dialog.showModal();
  });

  document.getElementById('familyCancelButton').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
  memberForm.addEventListener('submit', async event => {
    event.preventDefault();
    const submitButton = memberForm.querySelector('[type="submit"]');
    const formStatus = document.getElementById('familyFormStatus');
    const fields = new FormData(memberForm);
    const payload = Object.fromEntries(fields.entries());
    submitButton.disabled = true;
    formStatus.textContent = 'Saving profile...';
    try {
      const response = await fetch('/api/family/members', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'Could not save this profile.');
      window.location.reload();
    } catch (error) {
      formStatus.textContent = error.message;
      submitButton.disabled = false;
    }
  });

  if (dashboard) {
    document.getElementById('familyVaccinationForm').addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const payload = Object.fromEntries(new FormData(form).entries());
      const member = family.members.find(item => item.name.toLowerCase() === payload.member_name.trim().toLowerCase());
      if (!member) {
        document.getElementById('familyVaccineMember').setCustomValidity('Choose a name from this household.');
        document.getElementById('familyVaccineMember').reportValidity();
        return;
      }
      document.getElementById('familyVaccineMember').setCustomValidity('');
      payload.member_id = member.id;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        const response = await fetch('/api/family/vaccinations', {
          method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Could not save vaccination date.');
        form.reset();
        await loadFamily();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  }

  loadFamily();
})();