/* Role-scoped SeSide portals for family and care facilities. */
(() => {
  'use strict';
  const { $, esc, time, date, label, badge, bpm } = SW;
  const page = document.body.dataset.page;
  let portalMap = null;

  function safeCoord(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function mapStatus(text) {
    const node = $('#portalMapStatus');
    if (node) node.textContent = text;
  }

  function createMap(node, center, zoom) {
    portalMap?.remove();
    if (!node || !window.L) return null;
    const map = L.map(node).setView(center, zoom);
    const tiles = SW.satelliteTileLayer(map);
    const refreshMapSize = () => {
      if (map === portalMap) map.invalidateSize({ pan: false });
    };
    portalMap = map;
    requestAnimationFrame(() => requestAnimationFrame(refreshMapSize));
    setTimeout(refreshMapSize, 250);
    setTimeout(refreshMapSize, 800);
    tiles.on('tileerror', () => mapStatus('Không tải được bản đồ nền. Hãy kiểm tra kết nối Internet.'));
    return map;
  }

  function renderFamily(data) {
    const user = data.user;
    const device = data.device;
    const history = data.heartRateHistory || [];
    const facilityLocation = data.facilityLocation || {};
    $('#familyPortal').innerHTML = `
      <section class="portal-welcome section-card">
        <div><small>Hồ sơ được chia sẻ với tài khoản này</small><h2>${esc(user.fullName)}</h2><p>${esc(user.roomName)} · ${esc(user.facilityName)}</p></div>
        <span class="status-badge status-active">${user.monitoringStatus === 'active' ? 'Đang theo dõi' : 'Tạm dừng'}</span>
      </section>
      <div class="metrics-grid family-metrics">
        ${SW.metric('Nhịp tim gần nhất', bpm(device?.heartRate, 'Chưa có dữ liệu'), 'heart', 'bi-heart-pulse-fill', `Cập nhật ${time(device?.lastUpdated)}`)}
        ${SW.metric('SpO₂ ước tính', device?.spo2 != null ? `${device.spo2}%` : 'Chưa có dữ liệu', 'spo2', 'bi-droplet-half', 'Tham khảo; không thay thế thiết bị y tế')}
        ${SW.metric('Pin đồng hồ', device ? `${device.battery}%` : '—', 'battery', 'bi-battery-half', device ? label(device.connectionStatus) : 'Chưa gán đồng hồ')}
        ${SW.metric('Trạng thái té ngã', device?.fallStatus === 'FALL' ? 'CẦN HỖ TRỢ' : 'BÌNH THƯỜNG', 'fall', 'bi-shield-check', device?.fallProbability != null ? `Độ tin cậy ${(device.fallProbability * 100).toFixed(1)}%` : 'Chưa có cảnh báo')}
      </div>
      <div class="portal-content-grid">
        <section class="section-card portal-chart-card"><div class="card-heading"><span><h2>Nhịp tim 24 giờ</h2><small>${history.some(point => point.dataSource === 'demo') ? 'Có dữ liệu mô phỏng để xem giao diện.' : `${history.length} lần ghi nhận`}</small></span></div><div class="portal-heart-wrap"><canvas id="familyHeartChart"></canvas></div></section>
        <section class="section-card portal-events-card"><div class="card-heading"><h2>Cảnh báo gần đây</h2></div><div class="portal-event-list">${(data.recentEvents || []).map(event => `<article class="portal-event-row"><span>${esc(time(event.at))}</span><strong>${esc(label(event.type))}</strong><small>${esc(event.description)}</small></article>`).join('') || '<div class="empty-state">Chưa có cảnh báo gần đây.</div>'}</div></section>
      </div>
      <section class="section-card portal-map-card"><div class="card-heading"><span><h2>Vị trí đồng hồ</h2><small id="portalMapStatus">Đang xác định vị trí gần nhất…</small></span></div><div id="portalMap" class="sw-map portal-map"></div></section>
      <section class="section-card portal-contact-card"><div class="card-heading"><h2>Liên hệ hỗ trợ</h2></div><div class="portal-contact-details"><strong>${esc(data.contact?.name || 'Chưa có người liên hệ')}</strong><span>${esc(data.contact?.relation || '')}</span><a href="tel:${esc(data.contact?.phone || '')}">${esc(data.contact?.phone || 'Chưa có số điện thoại')}</a><span>${esc(data.responsibleStaff?.fullName || 'Chưa có nhân viên phụ trách')}</span></div></section>`;

    SW.chart('family-heart', $('#familyHeartChart'), {
      type: 'line',
      data: { labels: history.map(point => time(point.timestamp)), datasets: [{
        label: 'Nhịp tim', data: history.map(point => point.heartRate),
        borderColor: '#dc4d63', backgroundColor: 'rgba(220,77,99,.12)',
        fill: true, tension: .35, pointRadius: 2,
      }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { suggestedMin: 45, suggestedMax: 125, title: { display: true, text: 'BPM' } } } },
    });

    const lat = safeCoord(device?.latitude);
    const lng = safeCoord(device?.longitude);
    const centerLat = lat ?? safeCoord(facilityLocation.latitude) ?? 16.0471;
    const centerLng = lng ?? safeCoord(facilityLocation.longitude) ?? 108.2068;
    const map = createMap($('#portalMap'), [centerLat, centerLng], lat !== null && lng !== null ? 16 : 12);
    if (map && lat !== null && lng !== null) {
      L.marker([lat, lng]).addTo(map).bindPopup(`Đồng hồ ${esc(device.id)}`).openPopup();
      mapStatus(`Cập nhật ${time(device.lastUpdated)} · ${lat.toFixed(5)}, ${lng.toFixed(5)}`);
    } else if (map && safeCoord(facilityLocation.latitude) !== null) {
      L.marker([centerLat, centerLng]).addTo(map).bindPopup(esc(user.facilityName));
      mapStatus('Chưa có GPS đồng hồ; đang hiển thị vị trí cơ sở.');
    } else {
      mapStatus('Chưa có GPS của đồng hồ hoặc tọa độ cơ sở.');
    }
  }

  function renderFacility(data) {
    const facility = data.facility;
    const devices = data.devices || [];
    const deviceByUser = new Map(devices.map(device => [device.userId, device]));
    $('#facilityPortal').innerHTML = `
      <section class="portal-welcome section-card"><div><small>Cơ sở được phân quyền</small><h2>${esc(facility.name)}</h2><p>${esc(facility.address || 'Chưa có địa chỉ')}</p></div><span class="status-badge status-info">${esc(facility.phone || 'Đang quản lý')}</span></section>
      <div class="metrics-grid facility-portal-metrics">
        ${SW.metric('Người đang theo dõi', data.metrics.users, 'users', 'bi-people-fill', 'Trong cơ sở')}
        ${SW.metric('Đồng hồ', data.metrics.devices, 'devices', 'bi-smartwatch', 'Được gán trong cơ sở')}
        ${SW.metric('Cảnh báo đang mở', data.metrics.openAlerts, 'alerts', 'bi-bell-fill', 'Cần nhân viên xem xét')}
        ${SW.metric('Sự kiện té ngã', data.metrics.fallAlerts, 'falls', 'bi-person-fill-down', 'Lịch sử cơ sở')}
      </div>
      <section class="section-card portal-map-card"><div class="card-heading"><span><h2>Bản đồ thiết bị trong cơ sở</h2><small id="portalMapStatus">Vị trí GPS mới nhất được lấy từ telemetry của đồng hồ.</small></span></div><div id="portalMap" class="sw-map portal-map"></div></section>
      <div class="portal-content-grid facility-portal-grid">
        <section class="section-card portal-table-card"><div class="card-heading"><h2>Người được theo dõi</h2></div><div class="table-responsive"><table class="table sw-table mb-0"><thead><tr><th>Người dùng</th><th>Phòng</th><th>Đồng hồ</th><th>Nhịp tim</th><th>SpO₂</th><th>Pin</th><th>Trạng thái</th></tr></thead><tbody>${(data.users || []).map(user => { const device = deviceByUser.get(user.id); return `<tr><td>${esc(user.fullName)}</td><td>${esc(user.roomName)}</td><td>${esc(device?.id || user.deviceId || 'Chưa gán')}</td><td>${esc(bpm(device?.heartRate, '—'))}</td><td>${device?.spo2 != null ? `${device.spo2}%` : '—'}</td><td>${device ? `${device.battery}%` : '—'}</td><td>${badge(device?.status || user.monitoringStatus)}</td></tr>`; }).join('') || '<tr><td colspan="7">Chưa có người được theo dõi.</td></tr>'}</tbody></table></div></section>
        <section class="section-card portal-events-card"><div class="card-heading"><h2>Cảnh báo gần đây</h2></div><div class="portal-event-list">${(data.alerts || []).map(alert => `<article class="portal-event-row"><span>${esc(date(alert.eventAt))} ${esc(time(alert.eventAt))}</span><strong>${esc(alert.userName)} · ${esc(label(alert.type))}</strong><small>${esc(alert.message)} · ${badge(alert.status)}</small></article>`).join('') || '<div class="empty-state">Cơ sở chưa có cảnh báo.</div>'}</div></section>
      </div>`;

    const facilityLat = safeCoord(facility.latitude);
    const facilityLng = safeCoord(facility.longitude);
    const positions = devices.filter(device => safeCoord(device.latitude) !== null && safeCoord(device.longitude) !== null);
    const center = positions.length ? [Number(positions[0].latitude), Number(positions[0].longitude)]
      : facilityLat !== null && facilityLng !== null ? [facilityLat, facilityLng] : [16.0471, 108.2068];
    const map = createMap($('#portalMap'), center, positions.length ? 13 : facilityLat !== null ? 14 : 5);
    if (map) {
      if (facilityLat !== null && facilityLng !== null) L.marker([facilityLat, facilityLng]).addTo(map).bindPopup(esc(facility.name));
      positions.forEach(device => L.marker([device.latitude, device.longitude]).addTo(map).bindPopup(`${esc(device.id)} · ${esc(device.wearerName)}`));
      mapStatus(positions.length ? `${positions.length} đồng hồ có GPS gần nhất.` : 'Chưa có GPS đồng hồ; bản đồ đang ở vị trí cơ sở hoặc Việt Nam.');
    }
  }

  async function load() {
    const root = page === 'family' ? $('#familyPortal') : $('#facilityPortal');
    try {
      const data = await SW.api(page === 'family' ? '/api/portal/family' : '/api/portal/facility');
      if (page === 'family') renderFamily(data);
      else renderFacility(data);
    } catch (error) {
      root.innerHTML = `<section class="section-card"><div class="empty-state">Không tải được dữ liệu portal: ${esc(error.message)}</div></section>`;
    }
  }

  SW.boot(load, { realtime: false });
})();
