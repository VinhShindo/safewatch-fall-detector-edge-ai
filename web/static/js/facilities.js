(() => {
  'use strict';
  const { $, esc } = SW;
  let facilities = [];
  let selectedId = null;
  let facilityMap = null;
  let facilityMarker = null;

  function coordinate(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function setFacilityMarker(lat, lng) {
    if (!facilityMap) return;
    if (facilityMarker) facilityMarker.remove();
    facilityMarker = L.marker([lat, lng]).addTo(facilityMap);
    facilityMap.setView([lat, lng], 15);
    $('#facilityLatitude').value = lat.toFixed(6);
    $('#facilityLongitude').value = lng.toFixed(6);
    $('#facilityMapPosition').textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
  }

  function mountFacilityMap(facility) {
    facilityMap?.remove();
    facilityMarker = null;
    const mapNode = $('#facilityMap');
    if (!mapNode || !window.L) return;
    const lat = coordinate(facility.latitude);
    const lng = coordinate(facility.longitude);
    const center = lat !== null && lng !== null ? [lat, lng] : [16.0471, 108.2068];
    facilityMap = L.map(mapNode).setView(center, lat !== null && lng !== null ? 15 : 5);
    SW.satelliteTileLayer(facilityMap);
    if (lat !== null && lng !== null) {
      facilityMarker = L.marker([lat, lng]).addTo(facilityMap);
      $('#facilityMapPosition').textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    } else {
      $('#facilityMapPosition').textContent = 'Chưa có tọa độ. Nhấn lên bản đồ để chọn vị trí.';
    }
    facilityMap.on('click', event => setFacilityMarker(event.latlng.lat, event.latlng.lng));
    setTimeout(() => facilityMap?.invalidateSize(), 50);
  }

  function render() {
    const selected = facilities.find(f => f.id === selectedId) || facilities[0];
    selectedId = selected?.id || null;
    $('#facilityManagement').innerHTML = facilities.length ? `
      <div class="facility-management-grid">
        <section class="section-card facility-list-card"><div class="card-heading"><h2>Các cơ sở</h2></div><div class="facility-list">${facilities.map(f => `<button type="button" class="facility-list-item ${f.id === selectedId ? 'active' : ''}" data-facility="${esc(f.id)}"><i class="bi bi-building"></i><span><strong>${esc(f.name)}</strong><small>${esc(f.address || 'Chưa có địa chỉ')}</small></span><b>${f.totalUsers} người</b></button>`).join('')}</div></section>
        <section class="section-card facility-detail-card">${selected ? `<div class="card-heading"><h2>${esc(selected.name)}</h2><button class="btn-primary-sw small" id="addStaff"><i class="bi bi-person-plus"></i>Thêm nhân viên</button></div><div class="facility-detail-meta"><span><i class="bi bi-geo-alt"></i>${esc(selected.address || 'Chưa có địa chỉ')}</span><span><i class="bi bi-telephone"></i>${esc(selected.phone || 'Chưa có số điện thoại')}</span></div><div class="facility-stat-row"><strong>${selected.totalUsers}<small>Người dùng</small></strong><strong>${selected.totalDevices}<small>Thiết bị</small></strong><strong>${selected.openAlerts}<small>Cảnh báo mở</small></strong></div><div class="facility-map-section"><div class="card-heading"><span><h2>Vị trí cơ sở</h2><small id="facilityMapPosition"></small></span></div><div id="facilityMap" class="sw-map facility-map" role="application" aria-label="Bản đồ vị trí cơ sở"></div><form id="facilityLocationForm" class="facility-location-form"><label>Vĩ độ<input id="facilityLatitude" name="latitude" type="number" step="any" min="-90" max="90" value="${selected.latitude ?? ''}" required></label><label>Kinh độ<input id="facilityLongitude" name="longitude" type="number" step="any" min="-180" max="180" value="${selected.longitude ?? ''}" required></label><button class="btn-outline-sw small" type="submit"><i class="bi bi-geo"></i>Lưu vị trí</button></form></div><div class="card-heading staff-heading"><h2>Đội ngũ nhân viên y tế</h2></div><div id="staffList" class="staff-list"><div class="empty-state">Đang tải nhân viên...</div></div></div>` : ''}</section>
      </div>` : '<div class="empty-state">Chưa có cơ sở. Hãy thêm cơ sở đầu tiên.</div>';
    if (selected) {
      mountFacilityMap(selected);
      loadStaff(selected.id);
    }
  }

  async function loadStaff(facilityId) {
    try {
      const staff = await SW.api('/api/users/staff?facilityId=' + encodeURIComponent(facilityId));
      $('#staffList').innerHTML = staff.length ? staff.map(s => `<article class="staff-item"><span class="staff-avatar"><i class="bi bi-person-badge"></i></span><span><strong>${esc(s.fullName)}</strong><small>${esc(s.role || 'Nhân viên y tế')}</small><small>${esc(s.phone || 'Chưa có điện thoại')} · ${esc(s.shiftStart)} - ${esc(s.shiftEnd)}</small></span></article>`).join('') : '<div class="empty-state">Chưa có nhân viên tại cơ sở này.</div>';
    } catch (error) { SW.toast('Không tải được nhân viên', error.message, true); }
  }

  async function load() { facilities = await SW.api('/api/facilities'); render(); }

  function setup() {
    $('#facilityManagement').onclick = event => {
      const item = event.target.closest('[data-facility]');
      if (item) { selectedId = item.dataset.facility; render(); return; }
      if (event.target.closest('#addStaff')) { const form = $('#staffForm'); form.facilityId.value = selectedId; $('#staffDialog').showModal(); }
    };
    $('#addFacility').onclick = () => $('#facilityDialog').showModal();
    document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => button.closest('dialog').close());
    $('#facilityForm').onsubmit = async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const dialog = form.closest('dialog');
      try {
        const data = Object.fromEntries(new FormData(form));
        data.latitude = data.latitude ? Number(data.latitude) : null;
        data.longitude = data.longitude ? Number(data.longitude) : null;
        await SW.api('/api/facilities', { method: 'POST', body: JSON.stringify(data) });
        dialog.close();
        await load();
        SW.toast('Đã thêm cơ sở');
      } catch (error) { SW.toast('Không thể thêm cơ sở', error.message, true); }
    };
    $('#facilityManagement').addEventListener('submit', async event => {
      if (event.target.id !== 'facilityLocationForm') return;
      event.preventDefault();
      const data = new FormData(event.target);
      try {
        await SW.api(`/api/facilities/${encodeURIComponent(selectedId)}/location`, {
          method: 'POST',
          body: JSON.stringify({ latitude: Number(data.get('latitude')), longitude: Number(data.get('longitude')) }),
        });
        await load();
        SW.toast('Đã lưu vị trí cơ sở');
      } catch (error) { SW.toast('Không thể lưu vị trí', error.message, true); }
    });
    $('#staffForm').onsubmit = async event => { event.preventDefault(); try { const data = Object.fromEntries(new FormData(event.currentTarget)); await SW.api('/api/users/staff', { method: 'POST', body: JSON.stringify(data) }); event.currentTarget.closest('dialog').close(); await loadStaff(selectedId); SW.toast('Đã thêm nhân viên'); } catch (error) { SW.toast('Không thể thêm nhân viên', error.message, true); } };
  }
  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(load, { realtime: false });
})();
