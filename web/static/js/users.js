/* Trang Hồ sơ người dùng */
(() => {
  'use strict';
  const { $, esc, time, date, label, icon, badge, bpm } = SW;

  const LIVE_INTERVAL_MS = 2000;
  const params = new URLSearchParams(location.search);
  let current = params.get('id');
  let heartChart = null;
  let deviceMap = null;
  let deviceMarker = null;
  let lastPointTime = 0;
  let liveTimer = null;
  let laptopLocationDeviceId = null;
  let lastLaptopLocationSentAt = 0;
  const LAPTOP_LOCATION_MIN_INTERVAL_MS = 15000;
  let telemetryLocationHandler = null;

  const reportError = title => error => SW.toast(title, error.message, true);

  function mountDeviceMap(device, facilityLocation) {
    deviceMap?.remove();
    deviceMarker = null;
    const node = $('#deviceLocationMap');
    if (!node || !window.L) return;
    const lat = Number.isFinite(Number(device?.latitude)) ? Number(device.latitude) : null;
    const lng = Number.isFinite(Number(device?.longitude)) ? Number(device.longitude) : null;
    const facilityLat = facilityLocation?.latitude == null ? null : Number(facilityLocation.latitude);
    const facilityLng = facilityLocation?.longitude == null ? null : Number(facilityLocation.longitude);
    const hasDevicePosition = lat !== null && lng !== null && device?.latitude != null && device?.longitude != null;
    const center = hasDevicePosition ? [lat, lng]
      : facilityLat !== null && facilityLng !== null ? [facilityLat, facilityLng] : [16.0471, 108.2068];
    deviceMap = L.map(node).setView(center, hasDevicePosition ? 16 : facilityLat !== null ? 14 : 5);
    SW.satelliteTileLayer(deviceMap);
    if (hasDevicePosition) {
      deviceMarker = L.marker([lat, lng]).addTo(deviceMap).bindPopup(`Đồng hồ ${esc(device.id)}`).openPopup();
      $('#deviceLocationStatus').textContent = `Vị trí gần nhất: ${lat.toFixed(6)}, ${lng.toFixed(6)} · ${time(device.locationUpdatedAt || device.lastUpdated)}`;
    } else {
      $('#deviceLocationStatus').textContent = 'Đang chờ vị trí laptop. Cấp quyền định vị cho trình duyệt để cập nhật bản đồ.';
    }
    setTimeout(() => deviceMap?.invalidateSize(), 50);
  }

  function stopLaptopLocationTracking() {
    if (telemetryLocationHandler) window.removeEventListener('sw:telemetry-updated', telemetryLocationHandler);
    telemetryLocationHandler = null;
    laptopLocationDeviceId = null;
    lastLaptopLocationSentAt = 0;
  }

  async function sendLaptopLocation(deviceId, position) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;
    const device = await SW.api(`/api/devices/${encodeURIComponent(deviceId)}/location`, {
      method: 'POST',
      body: JSON.stringify({ latitude, longitude }),
    });
    if (deviceMap) {
      const point = [latitude, longitude];
      if (deviceMarker) deviceMarker.setLatLng(point);
      else deviceMarker = L.marker(point).addTo(deviceMap).bindPopup(`Đồng hồ ${esc(device.id)}`);
      deviceMap.setView(point, Math.max(deviceMap.getZoom(), 15));
    }
    $('#deviceLocationStatus').textContent = `Vị trí laptop: ${latitude.toFixed(6)}, ${longitude.toFixed(6)} · ${time(device.locationUpdatedAt)}`;
  }

  function laptopLocationError(error) {
    const message = error.code === 1
      ? 'Bạn chưa cấp quyền vị trí cho trang web.'
      : 'Không lấy được vị trí laptop. Hãy kiểm tra dịch vụ vị trí của máy.';
    $('#deviceLocationStatus').textContent = message;
  }

  function startLaptopLocationTracking(deviceId) {
    stopLaptopLocationTracking();
    if (!deviceId) {
      return;
    }
    if (!navigator.geolocation) {
      $('#deviceLocationStatus').textContent = 'Trình duyệt không hỗ trợ định vị.';
      return;
    }
    if (!window.isSecureContext) {
      $('#deviceLocationStatus').textContent = 'Định vị cần HTTPS hoặc mở trang trên chính laptop bằng http://localhost.';
      return;
    }

    laptopLocationDeviceId = deviceId;
    $('#deviceLocationStatus').textContent = 'Vị trí laptop sẽ cập nhật khi đồng hồ gửi dữ liệu.';
    telemetryLocationHandler = event => {
      if (String(event.detail?.deviceId || '').toLowerCase() !== laptopLocationDeviceId.toLowerCase()) return;
      const now = Date.now();
      if (now - lastLaptopLocationSentAt < LAPTOP_LOCATION_MIN_INTERVAL_MS) return;
      lastLaptopLocationSentAt = now;
      navigator.geolocation.getCurrentPosition(position => {
        sendLaptopLocation(deviceId, position).catch(error => {
          $('#deviceLocationStatus').textContent = `Không gửi được vị trí: ${error.message}`;
        });
      }, laptopLocationError, { enableHighAccuracy: true, timeout: 20000, maximumAge: 10000 });
    };
    window.addEventListener('sw:telemetry-updated', telemetryLocationHandler);
  }

  // ---- vẽ hồ sơ ------------------------------------------------------------------
  function profileHtml(d) {
    const u = d.user;
    const dev = d.device;
    const contact = d.contact;
    const staff = d.responsibleStaff;
    const updated = `Cập nhật: ${time(dev?.lastUpdated)}`;

    return `
      <button class="btn-outline-sw user-back-button" type="button" data-back-users><i class="bi bi-arrow-left"></i>Danh sách người dùng</button>
      <div class="user-top">
        <section class="section-card profile-card">
          <span class="person-avatar"><i class="bi bi-person"></i></span>
          <div class="profile-main">
            <h2>${esc(u.fullName)}</h2>
            <span class="status-badge status-active">${u.monitoringStatus === 'active' ? 'Đang theo dõi' : 'Tạm dừng'}</span>
            <p><i class="bi bi-building"></i> ${esc(u.roomName)} - ${esc(u.facilityName)}</p>
            <div class="profile-meta">
              <div>Tuổi<strong>${u.age}</strong></div>
              <div>Người liên hệ chính<strong>${esc(contact.name)} (${esc(contact.relation)})<br>${esc(contact.phone)}</strong></div>
              <div>Mã đồng hồ<strong>${esc(u.deviceId || 'Chưa gán')}</strong></div>
            </div>
          </div>
        </section>
        <section class="section-card user-kpi heart"><i class="bi bi-heart-fill"></i><span>Nhịp tim hiện tại</span><strong>${bpm(dev?.heartRate, '—')}</strong><small>${updated}</small></section>
        <section class="section-card user-kpi spo2"><i class="bi bi-droplet-half"></i><span>SpO₂ ước tính</span><strong>${dev?.spo2 != null ? `${dev.spo2}%` : '—'}</strong><small>${updated}</small></section>
        <section class="section-card user-kpi battery"><i class="bi bi-battery-half"></i><span>Pin đồng hồ</span><strong>${dev?.battery ?? '—'}${dev ? '%' : ''}</strong><small>${updated}</small></section>
        <section class="section-card user-kpi fall"><i class="bi bi-shield-check"></i><span>Trạng thái</span><strong>${dev?.fallStatus === 'FALL' ? 'NGÃ' : 'KHÔNG NGÃ'}</strong><small>${updated}</small></section>
        <section class="section-card user-kpi time"><i class="bi bi-clock"></i><span>Lần cập nhật</span><strong>${time(dev?.lastUpdated)}</strong><small>${date(dev?.lastUpdated)}</small></section>
      </div>
      <section class="section-card user-location-section">
        <div class="user-location-heading"><span><h2>Vị trí đồng hồ</h2><p id="deviceLocationStatus">Đang kiểm tra vị trí gần nhất…</p></span></div>
        <div id="deviceLocationMap" class="sw-map user-location-map" role="application" aria-label="Bản đồ vị trí đồng hồ"></div>
      </section>
      <div class="profile-grid">
        <section class="section-card heart-card">
          <div class="card-heading"><span><h2>Nhịp tim 24 giờ</h2><small id="heartRateDataSource"></small><small id="liveTelemetryStatus" role="status" aria-live="polite"></small></span><select class="filter-control compact"><option>24 giờ qua</option></select></div>
          <div class="heart-wrap"><canvas id="heartChart"></canvas></div>
        </section>
        <section class="section-card events-card">
          <div class="card-heading"><h2>Lịch sử sự kiện</h2><a href="/alerts">Xem tất cả</a></div>
          <div class="events-list">${d.recentEvents.map(x => `
            <div class="event-row"><time>${time(x.at)}</time><div><strong>${esc(label(x.type))}</strong><span>${esc(x.description)}</span></div><span>${esc(label(x.status))}</span></div>`).join('')
            || '<div class="empty-state">Chưa có sự kiện.</div>'}</div>
        </section>
      </div>
      <div class="contacts-history">
        <section class="section-card contact-card">
          <div class="card-heading"><h2>Thông tin người thân / nhân viên phụ trách</h2></div>
          <div class="contact-list">
            <div class="contact-row">
              <span class="person-avatar"><i class="bi bi-person"></i></span>
              <div><strong>${esc(contact.name)} <span class="status-badge status-info">${esc(contact.relation)}</span></strong>
              <span><i class="bi bi-telephone"></i> ${esc(contact.phone)} &nbsp; <i class="bi bi-envelope"></i> ${esc(contact.email)}</span></div>
            </div>
            ${staff ? `
            <div class="contact-row">
              <span class="person-avatar"><i class="bi bi-person-badge"></i></span>
              <div><strong>${esc(staff.fullName)} <span class="status-badge status-active">${esc(staff.role)}</span></strong>
              <span><i class="bi bi-telephone"></i> ${esc(staff.phone)} &nbsp; ${esc(staff.email)}</span></div>
            </div>` : ''}
          </div>
        </section>
        <section class="section-card history-card">
          <div class="card-heading"><h2>Lịch sử té ngã &amp; cảnh báo</h2><a href="/alerts">Xem tất cả</a></div>
          <div class="table-responsive">
            <table class="table sw-table mb-0">
              <thead><tr><th>Thời gian</th><th>Loại sự kiện</th><th>Mức độ</th><th>Trạng thái xử lý</th><th>Người xử lý</th></tr></thead>
              <tbody>${d.alertHistory.map(a => `
                <tr><td>${date(a.eventAt)} ${time(a.eventAt)}</td><td><i class="bi ${icon(a.type)}"></i> ${esc(label(a.type))}</td><td>${badge(a.severity)}</td><td>${badge(a.status)}</td><td>${esc(a.handledByName || 'Hệ thống')}</td></tr>`).join('')}
              </tbody>
            </table>
          </div>
        </section>
      </div>`;
  }

  function usersListHtml(items) {
    if (!items.length) return '<div class="empty-state">Chưa có người dùng phù hợp.</div>';
    return `<div class="user-list-grid">${items.map(u => `
      <button type="button" class="user-list-item" data-user-id="${esc(u.id)}">
        <span class="person-avatar"><i class="bi bi-person"></i></span>
        <span class="user-list-copy"><strong>${esc(u.fullName)}</strong><small>${esc(u.roomName)} - ${esc(u.facilityName)}</small><small>${esc(u.deviceId || 'Chưa gán thiết bị')}</small></span>
        <span class="user-list-status">${badge(u.monitoringStatus)}</span><i class="bi bi-chevron-right"></i>
      </button>`).join('')}</div>`;
  }

  function drawHeartChart(history) {
    const dataSourceNote = $('#heartRateDataSource');
    if (dataSourceNote) {
      const demoRows = history.filter(point => point.dataSource === 'demo').length;
      dataSourceNote.textContent = demoRows
        ? `Dữ liệu mô phỏng (${demoRows} mẫu), không phải số đo thực tế.`
        : '';
    }
    heartChart = SW.chart('heart', $('#heartChart'), {
      type: 'line',
      data: {
        labels: history.map(x => time(x.timestamp)),
        datasets: [{
          data: history.map(x => x.heartRate),
          borderColor: '#1266e9', backgroundColor: 'rgba(18,102,233,.1)',
          fill: true, tension: 0.35, pointRadius: 3,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { suggestedMin: 40, suggestedMax: 130 } },
      },
    });
    lastPointTime = history.length ? new Date(history[history.length - 1].timestamp).getTime() : 0;
  }

  async function load() {
    if (!current) {
      clearInterval(liveTimer);
      stopLaptopLocationTracking();
      const search = new URLSearchParams(Object.entries({ pageSize: 20, ...(params.get('q') ? { search: params.get('q') } : {}) }));
      if ($('#userFacility').value !== 'all') search.set('facilityId', $('#userFacility').value);
      if ($('#userStatus').value !== 'all') search.set('status', $('#userStatus').value);
      const all = await SW.api('/api/users?' + search);
      $('#userProfile').innerHTML = usersListHtml(all.items);
      return;
    }
    const d = await SW.api('/api/users/' + encodeURIComponent(current));
    $('#userProfile').innerHTML = profileHtml(d);
    mountDeviceMap(d.device, d.facilityLocation);
    drawHeartChart(d.heartRateHistory);
    startLive(d.device?.id);
    startLaptopLocationTracking(d.device?.id);
  }

  // ---- cập nhật trực tiếp (dữ liệu mô phỏng / telemetry mới) --------------------------
  function startLive(deviceId) {
    clearInterval(liveTimer);
    if (!deviceId) return;
    liveTimer = setInterval(() => {
      if (!document.hidden) pollLatest(deviceId);
    }, LIVE_INTERVAL_MS);
  }

  async function pollLatest(deviceId) {
    let series;
    try {
      series = await SW.api('/api/simulated/' + encodeURIComponent(deviceId));
    } catch (error) {
      const status = $('#liveTelemetryStatus');
      if (status) status.textContent = `Không đọc được telemetry: ${error.message}`;
      return;
    }
    if (!Array.isArray(series) || !series.length) {
      const status = $('#liveTelemetryStatus');
      if (status) status.textContent = 'Chưa có dữ liệu telemetry trong 24 giờ gần nhất.';
      return;
    }

    const samples = series
      .map(s => ({
        at: s.timestamp ?? s.eventAt ?? s.time ?? null,
        heart: s.heart_rate ?? s.heartRate ?? null,
        battery: s.battery ?? null,
        fall: s.fall_status ?? s.fallStatus ?? null,
        latitude: s.latitude ?? null,
        longitude: s.longitude ?? null,
      }))
      .filter(s => s.at && !Number.isNaN(new Date(s.at).getTime()))
      .sort((a, b) => new Date(a.at) - new Date(b.at));
    if (!samples.length) {
      const status = $('#liveTelemetryStatus');
      if (status) status.textContent = 'Không có mẫu telemetry hợp lệ trong 24 giờ qua.';
      return;
    }

    const latest = samples[samples.length - 1];
    const status = $('#liveTelemetryStatus');
    if (status) status.textContent = `Đã tải ${samples.length} mẫu · mới nhất ${time(latest.at)}`;
    applyKpis(latest);
    if (latest.latitude != null && latest.longitude != null) {
      const lat = Number(latest.latitude);
      const lng = Number(latest.longitude);
      if (Number.isFinite(lat) && Number.isFinite(lng) && deviceMap) {
        if (deviceMarker) deviceMarker.setLatLng([lat, lng]);
        else deviceMarker = L.marker([lat, lng]).addTo(deviceMap);
        deviceMap.setView([lat, lng], Math.max(deviceMap.getZoom(), 15));
        $('#deviceLocationStatus').textContent = `Vị trí gần nhất: ${lat.toFixed(6)}, ${lng.toFixed(6)} · ${time(latest.at)}`;
      }
    }
    appendHeartPoints(samples);
  }

  function applyKpis(sample) {
    const set = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
    const updated = `Cập nhật: ${time(sample.at)}`;

    if (sample.heart != null) set('.user-kpi.heart strong', bpm(sample.heart, '—'));
    if (sample.battery != null) set('.user-kpi.battery strong', `${sample.battery}%`);
    if (sample.fall != null) set('.user-kpi.fall strong', String(sample.fall).toUpperCase() === 'FALL' ? 'NGÃ' : 'KHÔNG NGÃ');
    ['heart', 'battery', 'fall'].forEach(kind => set(`.user-kpi.${kind} small`, updated));
    set('.user-kpi.time strong', time(sample.at));
    set('.user-kpi.time small', date(sample.at));
  }

  function appendHeartPoints(samples) {
    if (!heartChart) return;
    const fresh = samples.filter(s => s.heart != null && new Date(s.at).getTime() > lastPointTime);
    if (!fresh.length) return;
    fresh.forEach(s => {
      heartChart.data.labels.push(time(s.at));
      heartChart.data.datasets[0].data.push(s.heart);
      lastPointTime = new Date(s.at).getTime();
    });
    heartChart.update();
  }

  // ---- tìm hồ sơ ------------------------------------------------------------------------------
  async function findUser() {
    const query = new URLSearchParams({ pageSize: 1 });
    const search = $('#userSearchText').value.trim();
    if (search) query.set('search', search);
    if ($('#userFacility').value !== 'all') query.set('facilityId', $('#userFacility').value);
    if ($('#userStatus').value !== 'all') query.set('status', $('#userStatus').value);

    current = null;
    history.replaceState(null, '', `/users?${query}`);
    await load();
  }

  // ---- thêm bệnh nhân --------------------------------------------------------------------------------
  async function fillStaff() {
    const select = $('#patientStaff');
    try {
      const staff = await SW.api('/api/users/staff');
      select.innerHTML = '<option value="">Chọn người phụ trách</option>' +
        staff.map(x => `<option value="${esc(x.id)}">${esc(x.fullName)} — ${esc(x.role)}</option>`).join('');
    } catch (error) {
      select.innerHTML = '<option value="">Không tải được danh sách</option>';
      SW.toast('Lỗi', error.message, true);
    }
  }

  function setupPatientDialog() {
    const dialog = $('#patientDialog');
    const form = $('#patientForm');

    $('#addPatient').onclick = async () => { dialog.showModal(); await fillStaff(); };
    form.querySelector('[data-close]').onclick = () => dialog.close();
    form.onsubmit = async event => {
      event.preventDefault();
      const f = new FormData(form);
      const payload = {
        fullName: f.get('fullName'), gender: f.get('gender'), birthYear: Number(f.get('birthYear') || 0),
        facilityId: f.get('facilityId'), roomId: f.get('roomId'), deviceId: f.get('deviceId'),
        contactName: f.get('contactName'), contactRelation: f.get('contactRelation'),
        contactPhone: f.get('contactPhone'), contactEmail: f.get('contactEmail'),
        staffId: f.get('staffId') || null,
      };
      try {
        const result = await SW.api('/api/users', { method: 'POST', body: JSON.stringify(payload) });
        dialog.close();
        location.href = `/users?id=${encodeURIComponent(result.user.id)}`;
      } catch (error) {
        SW.toast('Không thể thêm bệnh nhân', error.message, true);
      }
    };
  }

  function setup() {
    const q = params.get('q');
    if (q) $('#userSearchText').value = q;

    $('#userSearch').onsubmit = event => { event.preventDefault(); findUser().catch(reportError('Lỗi')); };
    $('#userFacility').onchange = () => findUser().catch(reportError('Lỗi'));
    $('#userStatus').onchange = () => findUser().catch(reportError('Lỗi'));
    $('#userProfile').addEventListener('click', event => {
      const user = event.target.closest('[data-user-id]');
      if (user) {
        current = user.dataset.userId;
        history.replaceState(null, '', `/users?id=${encodeURIComponent(current)}`);
        load().catch(reportError('Lỗi'));
        return;
      }
      if (event.target.closest('[data-back-users]')) {
        current = null;
        history.replaceState(null, '', '/users');
        load().catch(reportError('Lỗi'));
      }
    });
    setupPatientDialog();

    if (q) $('#userSearchText').value = q;
  }

  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(async () => {
    if (params.get('q') && !current) return; // findUser() sẽ tự tải hồ sơ
    await load();
  });
})();
