/* Trang Quản lý thiết bị */
(() => {
  'use strict';
  const { $, esc, time, date, label, badge, metric, bpm } = SW;

  const DEFAULT_QUERY = () => ({ status: 'all', facilityId: 'all', battery: 'all', page: 1, pageSize: 10 });
  const FILTERS = { deviceStatus: 'status', deviceFacility: 'facilityId', deviceBattery: 'battery' };

  const params = new URLSearchParams(location.search);
  let query = { ...DEFAULT_QUERY(), ...(params.get('q') ? { search: params.get('q') } : {}) };
  let selected = null;

  function renderRow(d) {
    return `
      <tr data-device="${esc(d.id)}">
        <td><span class="device-glyph"><i class="bi bi-smartwatch"></i></span></td>
        <td><strong>${esc(d.id)}</strong></td>
        <td><strong>${esc(d.wearerName)}</strong><span class="cell-sub">Năm sinh ${d.birthYear ?? '—'}</span></td>
        <td>${esc(d.roomName)} - ${esc(d.facilityName)}</td>
        <td>${badge(d.status)}</td>
        <td class="battery-${d.battery <= 20 ? 'low' : 'good'}"><i class="bi bi-battery-half"></i> ${d.battery}%</td>
        <td class="${d.heartRate > 100 ? 'heart-high' : 'heart-good'}"><i class="bi bi-heart-fill"></i> ${bpm(d.heartRate)}</td>
        <td>${time(d.lastUpdated)}<span class="cell-sub">${date(d.lastUpdated)}</span></td>
        <td><button class="btn-outline-sw small" data-view="${esc(d.id)}"><i class="bi bi-eye"></i></button></td>
      </tr>`;
  }

  async function showDetails(id) {
    if (!id) return;
    const d = await SW.api('/api/devices/' + encodeURIComponent(id));
    selected = id;
    $('#deviceDetails').innerHTML = `
      <div class="detail-title"><h2>Chi tiết thiết bị</h2><button class="icon-button" data-close-details><i class="bi bi-x-lg"></i></button></div>
      <div class="watch-visual">10<br>08<small>SAFEWATCH</small></div>
      <div class="detail-identity">
        <h3>${esc(d.id)}</h3>${badge(d.status)}
        <p>${esc(d.wearerName)}</p>
        <span class="cell-sub">${esc(d.roomName)} - ${esc(d.facilityName)}</span>
      </div>
      <div class="detail-stats">
        <div class="detail-stat"><i class="bi bi-battery-half"></i><span>Pin</span><strong class="battery-${d.battery <= 20 ? 'low' : 'good'}">${d.battery}%</strong></div>
        <div class="detail-stat"><i class="bi bi-heart-fill"></i><span>Nhịp tim hiện tại</span><strong class="${d.heartRate > 100 ? 'heart-high' : 'heart-good'}">${bpm(d.heartRate, '—')}</strong></div>
        <div class="detail-stat"><i class="bi bi-reception-4"></i><span>Chất lượng kết nối</span><strong>${esc(label(d.connectionStatus))}</strong></div>
        <div class="detail-stat"><i class="bi bi-cpu"></i><span>Phiên bản phần mềm</span><strong>${esc(d.firmwareVersion)}</strong></div>
      </div>
      <div class="detail-actions">
        <a class="btn-outline-sw" href="/users?id=${encodeURIComponent(d.userId || '')}"><i class="bi bi-person"></i>Xem hồ sơ</a>
        <button class="btn-primary-sw" id="requestCheck"><i class="bi bi-activity"></i>Gửi kiểm tra</button>
      </div>`;
    $('#requestCheck').onclick = async () => {
      try {
        await SW.api(`/api/devices/${encodeURIComponent(d.id)}/check`, { method: 'POST' });
        SW.toast('Đã gửi yêu cầu kiểm tra', d.id);
      } catch (error) { SW.toast('Không thể gửi yêu cầu', error.message, true); }
    };
  }

  async function load() {
    const search = new URLSearchParams(Object.entries(query).filter(([, v]) => v && v !== 'all'));
    const [data, summary] = await Promise.all([
      SW.api('/api/devices?' + search),
      SW.api('/api/devices/summary'),
    ]);
    const rows = data.items;

    $('#deviceMetrics').innerHTML =
      metric('Tổng thiết bị', summary.total, 'info', 'bi-smartwatch') +
      metric('Đang hoạt động', summary.active, 'success', 'bi-activity') +
      metric('Pin yếu', summary.lowBattery, 'warning', 'bi-battery-half') +
      metric('Mất kết nối', summary.offline, 'danger', 'bi-wifi-off');

    if (!selected || !rows.some(d => d.id === selected)) selected = rows[0]?.id ?? null;
    $('#devicesTable').innerHTML = rows.map(renderRow).join('') ||
      '<tr><td colspan="9" class="text-center py-4">Không có thiết bị phù hợp.</td></tr>';
    $('#devicePageInfo').textContent = `Trang ${data.page}/${data.totalPages} · Hiển thị ${rows.length} trong tổng số ${data.total} thiết bị`;
    SW.pagination($('#devicePagination'), data.page, data.totalPages, next => {
      query.page = next;
      load().catch(SW.fail('Lỗi'));
    });

    if (selected) await showDetails(selected);
    else $('#deviceDetails').innerHTML = '<div class="empty-state">Không có thiết bị phù hợp.</div>';
  }

  function setupControls() {
    Object.entries(FILTERS).forEach(([id, key]) => {
      $('#' + id).onchange = event => {
        query[key] = event.target.value;
        query.page = 1;
        load().catch(SW.fail('Lỗi'));
      };
    });

    $('#resetDeviceFilters').onclick = () => {
      query = DEFAULT_QUERY();
      Object.keys(FILTERS).forEach(id => { $('#' + id).value = 'all'; });
      load().catch(SW.fail('Lỗi'));
    };

    $('#devicesTable').onclick = event => {
      const id = event.target.closest('[data-device]')?.dataset.device;
      if (id) showDetails(id).catch(SW.fail('Lỗi'));
    };

    $('#deviceDetails').addEventListener('click', event => {
      if (event.target.closest('[data-close-details]')) {
        selected = null;
        $('#deviceDetails').innerHTML = '<div class="empty-state">Chọn thiết bị để xem chi tiết.</div>';
      }
    });

    // Thông báo sau khi tạo thiết bị: /devices?created=SW-XXX
    const created = params.get('created');
    if (created) {
      const notice = $('#deviceCreatedNotice');
      notice.textContent = `Đã lưu thiết bị ${created} và hồ sơ bệnh nhân vào JSON.`;
      notice.classList.remove('d-none');
      history.replaceState(null, '', location.pathname);
    }
  }

  document.addEventListener('DOMContentLoaded', setupControls);
  SW.boot(load);
})();
