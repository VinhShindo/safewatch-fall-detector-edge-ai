/* Trang Hồ sơ người dùng */
(() => {
  'use strict';
  const { $, esc, time, date, label, icon, badge, bpm } = SW;

  const LIVE_INTERVAL_MS = 2000;
  const params = new URLSearchParams(location.search);
  let current = params.get('id');
  let heartChart = null;
  let lastPointTime = 0;
  let liveTimer = null;

  const reportError = title => error => SW.toast(title, error.message, true);

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
        <section class="section-card user-kpi battery"><i class="bi bi-battery-half"></i><span>Pin đồng hồ</span><strong>${dev?.battery ?? '—'}${dev ? '%' : ''}</strong><small>${updated}</small></section>
        <section class="section-card user-kpi fall"><i class="bi bi-shield-check"></i><span>Trạng thái</span><strong>${dev?.fallStatus === 'FALL' ? 'NGÃ' : 'KHÔNG NGÃ'}</strong><small>${updated}</small></section>
        <section class="section-card user-kpi time"><i class="bi bi-clock"></i><span>Lần cập nhật</span><strong>${time(dev?.lastUpdated)}</strong><small>${date(dev?.lastUpdated)}</small></section>
      </div>
      <div class="profile-grid">
        <section class="section-card heart-card">
          <div class="card-heading"><h2>Nhịp tim 24 giờ</h2><select class="filter-control compact"><option>24 giờ qua</option></select></div>
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
      const search = new URLSearchParams(Object.entries({ pageSize: 20, ...(params.get('q') ? { search: params.get('q') } : {}) }));
      if ($('#userFacility').value !== 'all') search.set('facilityId', $('#userFacility').value);
      if ($('#userStatus').value !== 'all') search.set('status', $('#userStatus').value);
      const all = await SW.api('/api/users?' + search);
      $('#userProfile').innerHTML = usersListHtml(all.items);
      return;
    }
    const d = await SW.api('/api/users/' + encodeURIComponent(current));
    $('#userProfile').innerHTML = profileHtml(d);
    drawHeartChart(d.heartRateHistory);
    startLive(d.device?.id);
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
    } catch { return; }
    if (!Array.isArray(series) || !series.length) return;

    const samples = series
      .map(s => ({
        at: s.timestamp ?? s.eventAt ?? s.time ?? null,
        heart: s.heart_rate ?? s.heartRate ?? null,
        battery: s.battery ?? null,
        fall: s.fall_status ?? s.fallStatus ?? null,
      }))
      .filter(s => s.at && !Number.isNaN(new Date(s.at).getTime()))
      .sort((a, b) => new Date(a.at) - new Date(b.at));
    if (!samples.length) return;

    applyKpis(samples[samples.length - 1]);
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
