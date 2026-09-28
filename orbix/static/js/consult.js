(() => {
  const overlay = document.getElementById('callOverlay');
  const status = document.getElementById('callStatus');
  const statusText = document.getElementById('callStatusText');
  const permissionMessage = document.getElementById('permissionMessage');
  const permissionText = document.getElementById('permissionText');
  const videoBox = document.getElementById('selfVideoBox');
  const videoElement = document.getElementById('selfVideo');
  const microphoneButton = document.getElementById('microphoneButton');
  const cameraButton = document.getElementById('cameraButton');
  const timerElement = document.getElementById('callTimer');
  const toast = document.getElementById('consultToast');
  const directoryElement = document.getElementById('doctorDirectory');
  const searchInput = document.getElementById('doctorSearch');
  const specialtyFilter = document.getElementById('specialtyFilter');
  const doctorCount = document.getElementById('doctorCount');
  const callButtons = [...document.querySelectorAll('[data-call-type]')];

  let doctors = [];
  let selectedDoctor = null;
  const callState = {
    type: null,
    stream: null,
    connectedAt: null,
    timerInterval: null,
    connectTimeout: null,
    toastTimeout: null,
    attempt: 0,
  };
  let returnFocus = null;

  // Update the visible connection state and its accessible text together.
  function setCallStatus(state, message) {
    status.dataset.state = state;
    statusText.textContent = message;
  }

  // Format elapsed connected time as the familiar MM:SS call timer.
  function formatDuration(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const seconds = (totalSeconds % 60).toString().padStart(2, '0');
    return `${minutes}:${seconds}`;
  }

  // Keep device controls synchronized with the media tracks they enable or mute.
  function updateControlLabels() {
    const audioTrack = callState.stream?.getAudioTracks()[0];
    const muted = Boolean(audioTrack && !audioTrack.enabled);
    microphoneButton.disabled = !audioTrack;
    microphoneButton.setAttribute('aria-pressed', String(muted));
    microphoneButton.setAttribute('aria-label', muted ? 'Unmute microphone' : 'Mute microphone');
    microphoneButton.querySelector('span').textContent = muted ? 'Unmute' : 'Mute';
    microphoneButton.querySelector('[data-lucide]')?.setAttribute('data-lucide', muted ? 'mic-off' : 'mic');

    const videoTrack = callState.stream?.getVideoTracks()[0];
    cameraButton.hidden = callState.type !== 'video';
    cameraButton.disabled = !videoTrack;
    cameraButton.setAttribute('aria-pressed', String(Boolean(videoTrack && !videoTrack.enabled)));
    cameraButton.setAttribute('aria-label', videoTrack && !videoTrack.enabled ? 'Turn camera on' : 'Turn camera off');
    cameraButton.querySelector('span').textContent = videoTrack && !videoTrack.enabled ? 'Camera on' : 'Camera off';
    cameraButton.querySelector('[data-lucide]')?.setAttribute('data-lucide', videoTrack && !videoTrack.enabled ? 'video' : 'video-off');
    if (window.lucide) window.lucide.createIcons();
  }

  // Escape directory values before placing them into card markup.
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[character]);
  }

  // Create compact initials for directory cards and the active-call placeholder.
  function doctorInitials(name) {
    return String(name || 'Doctor').replace(/^Dr\.\s*/i, '').split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
  }

  // Update the doctor card and call overlay from the selected directory entry.
  function renderSelectedDoctor() {
    if (!selectedDoctor) return;
    document.getElementById('selectedDoctorAvatar').textContent = doctorInitials(selectedDoctor.name);
    document.getElementById('doctorName').textContent = selectedDoctor.name;
    document.getElementById('doctorSpecialty').textContent = selectedDoctor.specialty;
    document.getElementById('doctorFacility').textContent = `${selectedDoctor.facility} · ${selectedDoctor.city}`;
    document.querySelector('#doctorMeta span').textContent = selectedDoctor.experience_years
      ? `${selectedDoctor.experience_years} years’ experience${selectedDoctor.verified ? ' · Directory verified' : ' · Sample profile'}`
      : (selectedDoctor.verified ? 'Directory verified' : 'Sample profile');
    const availability = document.getElementById('doctorAvailability');
    availability.classList.toggle('is-unavailable', !selectedDoctor.available);
    availability.querySelector('span:last-child').textContent = selectedDoctor.available ? 'Available now' : 'Not available now';
    callButtons.forEach(button => {
      button.disabled = !selectedDoctor.available;
      button.title = selectedDoctor.available ? '' : 'This doctor is currently unavailable';
    });
    document.getElementById('callDoctorName').textContent = selectedDoctor.name;
    document.querySelector('.doctor-avatar-large').textContent = doctorInitials(selectedDoctor.name);
    document.getElementById('callModeLabel').textContent = `${selectedDoctor.specialty} · Video consultation`;
  }

  // Render directory cards matching the current text search and category filter.
  function renderDoctorDirectory() {
    if (!directoryElement) return;
    const query = searchInput.value.trim().toLowerCase();
    const specialty = specialtyFilter.value;
    const filtered = doctors.filter(doctor => {
      const matchesCategory = specialty === 'all' || doctor.specialty === specialty;
      const searchable = `${doctor.name} ${doctor.specialty} ${doctor.facility} ${doctor.city} ${doctor.area}`.toLowerCase();
      return matchesCategory && searchable.includes(query);
    });
    doctorCount.textContent = `${filtered.length} of ${doctors.length} doctors`;
    if (!filtered.length) {
      directoryElement.innerHTML = '<p class="directory-empty">No doctors match this search. Try another name or specialty.</p>';
      return;
    }
    directoryElement.innerHTML = filtered.map(doctor => {
      const isSelected = doctor.id === selectedDoctor?.id;
      const unavailableClass = doctor.available ? '' : ' is-unavailable';
      return `<article class="directory-doctor${isSelected ? ' is-selected' : ''}">
        <div class="directory-doctor-top">
          <span class="directory-doctor-avatar" aria-hidden="true">${escapeHtml(doctorInitials(doctor.name))}</span>
          <div class="directory-doctor-info"><h3>${escapeHtml(doctor.name)}</h3><p class="directory-specialty">${escapeHtml(doctor.specialty)}</p></div>
          <span class="directory-status${unavailableClass}">${doctor.available ? 'Available now' : 'Busy'}</span>
        </div>
        <div class="directory-facility"><strong>${escapeHtml(doctor.facility)}</strong><span>${escapeHtml([doctor.area, doctor.city].filter(Boolean).join(', '))}</span></div>
        <div class="directory-doctor-footer">
          <span class="directory-experience">${doctor.experience_years ? `${escapeHtml(doctor.experience_years)} years’ experience` : 'Community provider'}</span>
          <button type="button" class="directory-select" data-select-doctor="${escapeHtml(doctor.id)}" aria-pressed="${isSelected}" ${isSelected ? 'disabled' : ''}>${isSelected ? 'Selected' : 'Select doctor'}</button>
        </div>
      </article>`;
    }).join('');
  }

  // Fetch the account-protected provider directory and prepare category choices.
  async function loadDoctorDirectory() {
    try {
      const response = await fetch('/api/consult-doctors', { credentials: 'include' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'Could not load the doctor directory.');
      doctors = Array.isArray(result.doctors) ? result.doctors : [];
      specialtyFilter.innerHTML = '<option value="all">All specialties</option>' + (result.specialties || []).map(specialty => `<option value="${escapeHtml(specialty)}">${escapeHtml(specialty)}</option>`).join('');
      selectedDoctor = doctors.find(doctor => doctor.available) || doctors[0] || null;
      if (!selectedDoctor) throw new Error('No doctors are listed right now.');
      renderSelectedDoctor();
      renderDoctorDirectory();
      if (window.lucide) window.lucide.createIcons();
    } catch (error) {
      doctorCount.textContent = 'Directory unavailable';
      directoryElement.innerHTML = `<p class="directory-empty">${escapeHtml(error.message || 'Could not load the doctor directory.')}</p>`;
      callButtons.forEach(button => { button.disabled = true; });
    }
  }

  // Stop every captured track and detach the preview to release device access.
  function releaseMedia() {
    if (callState.stream) {
      callState.stream.getTracks().forEach(track => track.stop());
      callState.stream = null;
    }
    videoElement.srcObject = null;
    videoBox.hidden = true;
  }

  // Display a short, accessible confirmation without stealing focus from the page.
  function showToast(message) {
    window.clearTimeout(callState.toastTimeout);
    toast.textContent = message;
    toast.hidden = false;
    callState.toastTimeout = window.setTimeout(() => { toast.hidden = true; }, 4500);
  }

  // Map common browser capture failures to an actionable message for the patient.
  function permissionErrorMessage(error, callType) {
    const deviceLabel = callType === 'video' ? 'camera and microphone' : 'microphone';
    if (!window.isSecureContext) return 'Device access requires a secure page. Open this site on HTTPS or localhost, then try again.';
    if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
      return `Access to the ${deviceLabel} was denied. Allow permission in your browser settings, then choose Try again.`;
    }
    if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
      return `No ${deviceLabel} could be found. Connect or enable the required device, then try again.`;
    }
    if (error?.name === 'NotReadableError' || error?.name === 'TrackStartError') {
      return `The ${deviceLabel} may be in use by another app. Close that app and try again.`;
    }
    if (error?.name === 'OverconstrainedError') {
      return 'The selected camera is not available. Check your device settings and try again.';
    }
    return `The browser could not open the ${deviceLabel}. Check browser permissions and device settings, then try again.`;
  }

  // Begin a simulated doctor call using only the browser's native media capture API.
  async function requestDeviceAccess(attempt = callState.attempt) {
    const callType = callState.type;
    permissionMessage.hidden = true;
    setCallStatus('connecting', 'Requesting device access');
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('This browser does not support media capture. Use a current browser over HTTPS or localhost.');
      }
      const constraints = {
        audio: true,
        video: callType === 'video' ? { facingMode: 'user' } : false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (attempt !== callState.attempt || overlay.hidden) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      callState.stream = stream;
      if (callType === 'video') {
        videoElement.srcObject = callState.stream;
        videoBox.hidden = false;
        await videoElement.play().catch(() => {});
      }
      updateControlLabels();
      setCallStatus('connecting', 'Connecting to doctor');
      callState.connectTimeout = window.setTimeout(markCallConnected, 2000);
    } catch (error) {
      if (attempt !== callState.attempt || overlay.hidden) return;
      releaseMedia();
      setCallStatus('error', 'Permission needed');
      permissionText.textContent = error?.name && error.name !== 'Error'
        ? permissionErrorMessage(error, callType)
        : (error?.message || permissionErrorMessage(error, callType));
      permissionMessage.hidden = false;
      document.getElementById('retryPermissionButton').focus();
      if (window.lucide) window.lucide.createIcons();
    }
  }

  // Mark the prototype session connected and start timing only the connected portion.
  function markCallConnected() {
    if (overlay.hidden || !callState.stream) return;
    callState.connectedAt = Date.now();
    setCallStatus('connected', `Connected with ${selectedDoctor.name}`);
    callState.timerInterval = window.setInterval(() => {
      timerElement.textContent = formatDuration(Math.floor((Date.now() - callState.connectedAt) / 1000));
    }, 250);
  }

  // Reset the overlay, request the right devices, then enter the simulated call flow.
  async function startCall(callType) {
    if (callState.stream) releaseMedia();
    window.clearTimeout(callState.connectTimeout);
    window.clearInterval(callState.timerInterval);
    callState.attempt += 1;
    returnFocus = document.activeElement;
    callState.type = callType;
    callState.connectedAt = null;
    timerElement.textContent = '00:00';
    document.getElementById('callModeLabel').textContent = `${selectedDoctor.specialty} · ${callType === 'video' ? 'Video' : 'Voice'} consultation`;
    document.getElementById('callTypeText').textContent = `${callType === 'video' ? 'Video' : 'Voice'} call`;
    overlay.dataset.callType = callType;
    overlay.hidden = false;
    document.body.classList.add('call-open');
    overlay.focus();
    updateControlLabels();
    await requestDeviceAccess(callState.attempt);
  }

  // Save a connected call against the active patient profile, then report the result.
  async function saveConsultation(durationSeconds, callType) {
    const response = await fetch('/api/save-consultation', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_id: selectedDoctor.id, doctor_name: selectedDoctor.name, duration_seconds: durationSeconds, call_type: callType }),
    });
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.message || 'The consultation summary could not be saved.');
    showToast('Call ended — summary saved to patient record');
  }

  // End the call, stop hardware tracks immediately, and persist a connected session.
  async function endCall() {
    const endedType = callState.type;
    const durationSeconds = callState.connectedAt
      ? Math.floor((Date.now() - callState.connectedAt) / 1000)
      : (callState.stream ? 0 : null);
    callState.attempt += 1;
    window.clearTimeout(callState.connectTimeout);
    window.clearInterval(callState.timerInterval);
    callState.connectedAt = null;
    releaseMedia();
    overlay.hidden = true;
    document.body.classList.remove('call-open');
    returnFocus?.focus?.();
    if (durationSeconds === null) return;

    try {
      await saveConsultation(durationSeconds, endedType);
    } catch (error) {
      showToast(error.message || 'Call ended, but the summary could not be saved.');
    }
  }

  document.querySelectorAll('[data-call-type]').forEach(button => {
    button.addEventListener('click', () => startCall(button.dataset.callType));
  });
  directoryElement?.addEventListener('click', event => {
    const button = event.target.closest('[data-select-doctor]');
    if (!button) return;
    selectedDoctor = doctors.find(doctor => doctor.id === button.dataset.selectDoctor) || selectedDoctor;
    renderSelectedDoctor();
    renderDoctorDirectory();
  });
  searchInput?.addEventListener('input', renderDoctorDirectory);
  specialtyFilter?.addEventListener('change', renderDoctorDirectory);
  microphoneButton.addEventListener('click', () => {
    const track = callState.stream?.getAudioTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    updateControlLabels();
  });
  cameraButton.addEventListener('click', () => {
    const track = callState.stream?.getVideoTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    updateControlLabels();
  });
  document.getElementById('endCallButton').addEventListener('click', endCall);
  document.getElementById('closeCallButton').addEventListener('click', endCall);
  document.getElementById('closePermissionButton').addEventListener('click', endCall);
  document.getElementById('retryPermissionButton').addEventListener('click', requestDeviceAccess);
  document.addEventListener('keydown', event => {
    if (overlay.hidden) return;
    if (event.key === 'Escape') {
      endCall();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [...overlay.querySelectorAll('a[href], button:not([disabled])')]
      .filter(element => element.getClientRects().length > 0);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  window.addEventListener('pagehide', () => {
    callState.attempt += 1;
    releaseMedia();
  });
  loadDoctorDirectory();
})();