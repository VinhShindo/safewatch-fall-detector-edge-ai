(() => {
  'use strict';
  const { $, esc } = SW;
  let facilities = [];
  let selectedId = null;

  function render() {
    const selected = facilities.find(f => f.id === selectedId) || facilities[0];
    selectedId = selected?.id || null;
    $('#facilityManagement').innerHTML = facilities.length ? `
      <div class="facility-management-grid">
        <section class="section-card facility-list-card"><div class="card-heading"><h2>Các cơ sở</h2></div><div class="facility-list">${facilities.map(f => `<button type="button" class="facility-list-item ${f.id === selectedId ? 'active' : ''}" data-facility="${esc(f.id)}"><i class="bi bi-building"></i><span><strong>${esc(f.name)}</strong><small>${esc(f.address || 'Chưa có địa chỉ')}</small></span><b>${f.totalUsers} người</b></button>`).join('')}</div></section>
        <section class="section-card facility-detail-card">${selected ? `<div class="card-heading"><h2>${esc(selected.name)}</h2><button class="btn-primary-sw small" id="addStaff"><i class="bi bi-person-plus"></i>Thêm nhân viên</button></div><div class="facility-detail-meta"><span><i class="bi bi-geo-alt"></i>${esc(selected.address || 'Chưa có địa chỉ')}</span><span><i class="bi bi-telephone"></i>${esc(selected.phone || 'Chưa có số điện thoại')}</span></div><div class="facility-stat-row"><strong>${selected.totalUsers}<small>Người dùng</small></strong><strong>${selected.totalDevices}<small>Thiết bị</small></strong><strong>${selected.openAlerts}<small>Cảnh báo mở</small></strong></div><div class="card-heading staff-heading"><h2>Đội ngũ nhân viên y tế</h2></div><div id="staffList" class="staff-list"><div class="empty-state">Đang tải nhân viên...</div></div></div>` : ''}</section>
      </div>` : '<div class="empty-state">Chưa có cơ sở. Hãy thêm cơ sở đầu tiên.</div>';
    if (selected) loadStaff(selected.id);
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
    $('#facilityForm').onsubmit = async event => { event.preventDefault(); try { const data = Object.fromEntries(new FormData(event.currentTarget)); await SW.api('/api/facilities', { method: 'POST', body: JSON.stringify(data) }); event.currentTarget.closest('dialog').close(); await load(); SW.toast('Đã thêm cơ sở'); } catch (error) { SW.toast('Không thể thêm cơ sở', error.message, true); } };
    $('#staffForm').onsubmit = async event => { event.preventDefault(); try { const data = Object.fromEntries(new FormData(event.currentTarget)); await SW.api('/api/users/staff', { method: 'POST', body: JSON.stringify(data) }); event.currentTarget.closest('dialog').close(); await loadStaff(selectedId); SW.toast('Đã thêm nhân viên'); } catch (error) { SW.toast('Không thể thêm nhân viên', error.message, true); } };
  }
  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(load, { realtime: false });
})();
