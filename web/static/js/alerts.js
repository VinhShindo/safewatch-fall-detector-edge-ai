/* Trang Trung tâm cảnh báo */
(() => {
  'use strict';
  const { $, $$, esc, time, date, label, icon, badge } = SW;

  const params = new URLSearchParams(location.search);
  let filter = { page: 1, pageSize: 10, ...(params.get('q') ? { search: params.get('q') } : {}) };
  let selected = params.get('id');

  const reportError = title => error => SW.toast(title, error.message, true);

  function iconClass(type) {
    return type === 'connection' ? 'connection' : type === 'low_battery' ? 'battery' : type === 'heart_rate' ? 'heart' : '';
  }

  function renderRow(a) {
    return `
      <article class="alert-row ${a.id === selected ? 'selected' : ''}" data-alert="${esc(a.id)}">
        <span class="alert-icon ${iconClass(a.type)}"><i class="bi ${icon(a.type)}"></i></span>
        <span><h3>${esc(a.message)}</h3><p>${esc(a.userName)} &nbsp;•&nbsp; ${esc(a.roomName)} - ${esc(a.facilityName)}</p></span>
        <span class="alert-time">${time(a.eventAt)}<br>${badge(a.severity)}</span>
      </article>`;
  }

  async function showDetail(id) {
    if (!id) return;
    const d = await SW.api('/api/alerts/' + encodeURIComponent(id));
    selected = id;
    const a = d.alert;
    const heart = d.device?.heartRate;
    const latitude = a.latitude ?? d.device?.latitude;
    const longitude = a.longitude ?? d.device?.longitude;
    const hasLaptopLocation = latitude != null && longitude != null;
    const statusKind = a.status === 'closed' ? 'active' : a.status === 'acknowledged' ? 'info' : 'high';

    $('#alertDetails').innerHTML = `
      <div class="alert-detail-head">
        <div><span class="severity-chip">${esc(label(a.severity))}</span><h2>${esc(a.message)}</h2><p>ID cảnh báo: #${esc(a.id)}</p></div>
        <div class="text-end">
          <span class="status-badge status-${statusKind}">${esc(label(a.status))}</span>
          <p class="mt-2">Thời gian xảy ra<br><strong>${time(a.eventAt)}, ${date(a.eventAt)}</strong></p>
        </div>
      </div>
      <div class="alert-person">
        <div class="person-info">
          <span class="person-avatar"><i class="bi bi-person"></i></span>
          <div><strong>${esc(a.userName)}</strong><span>${esc(d.user?.gender || '')} ${d.user?.age ? `• ${d.user.age} tuổi` : ''}<br>${esc(a.roomName)} - ${esc(a.facilityName)}</span></div>
        </div>
        <a class="btn-outline-sw small" href="/users?id=${encodeURIComponent(a.userId || '')}">Xem hồ sơ</a>
      </div>
      <div class="alert-data-row">
        <div><span>Nhịp tim gần nhất</span><strong class="heart-high">${SW.bpm(heart, '—')}</strong></div>
        <div><span>Pin đồng hồ</span><strong class="battery-low">${d.device?.battery ?? '—'}${d.device ? '%' : ''}</strong></div>
        <div><span>Kết nối</span><strong>${esc(label(d.device?.connectionStatus))}</strong></div>
        <div><span>Vị trí laptop tại lúc cảnh báo</span><strong>${hasLaptopLocation
          ? `<a href="https://www.google.com/maps?q=${encodeURIComponent(latitude)},${encodeURIComponent(longitude)}&t=k" target="_blank" rel="noopener noreferrer">${Number(latitude).toFixed(6)}, ${Number(longitude).toFixed(6)} <i class="bi bi-box-arrow-up-right"></i></a>`
          : 'Chưa có vị trí laptop'}</strong></div>
      </div>
      <div class="alert-actions">
        <button class="btn-primary-sw" data-act="acknowledge"><i class="bi bi-check-lg"></i>Xác nhận đã xem</button>
        <button class="btn-danger-sw" data-act="urgent"><i class="bi bi-exclamation-triangle"></i>Đánh dấu khẩn cấp</button>
        <button class="btn-outline-sw" data-act="close"><i class="bi bi-x-lg"></i>Đóng cảnh báo</button>
      </div>
      <h3 class="mt-4 mb-2" style="font-size:15px">Nhật ký xử lý</h3>
      <table class="audit-table">
        <thead><tr><th>Thời gian</th><th>Người xử lý</th><th>Hành động</th><th>Ghi chú</th></tr></thead>
        <tbody>${d.actions.map(x => `
          <tr><td>${time(x.at)}, ${date(x.at)}</td><td>${esc(x.actorName)}</td><td>${esc(label(x.action))}</td><td>${esc(x.note || '—')}</td></tr>`).join('')}
        </tbody>
      </table>`;

    $$('[data-act]', $('#alertDetails')).forEach(button => {
      button.onclick = async () => {
        try {
          await SW.api(`/api/alerts/${encodeURIComponent(a.id)}/${button.dataset.act}`, {
            method: 'POST',
            body: JSON.stringify({ note: 'Thao tác từ SeSide Admin' }),
          });
          SW.toast('Đã cập nhật cảnh báo', label(button.dataset.act));
          await load();
        } catch (error) {
          SW.toast('Không thể cập nhật', error.message, true);
        }
      };
    });
  }

  async function load() {
    const [data, summary] = await Promise.all([
      SW.api('/api/alerts?' + new URLSearchParams(filter)),
      SW.api('/api/alerts/summary'),
    ]);
    const rows = data.items;

    $('#allAlertCount').textContent = summary.total;
    $('#highAlertCount').textContent = summary.high;
    $('#openAlertCount').textContent = summary.open;
    $('#alertCount').textContent = `(${data.total})`;

    if (!selected || !rows.some(a => a.id === selected)) selected = rows[0]?.id ?? null;
    $('#alertsList').innerHTML = rows.map(renderRow).join('') || '<div class="empty-state">Không có cảnh báo phù hợp.</div>';
    $('#alertsPageInfo').textContent = `Trang ${data.page}/${data.totalPages} · Hiển thị ${rows.length} trong tổng số ${data.total} cảnh báo`;
    SW.pagination($('#alertsPagination'), data.page, data.totalPages, next => {
      filter.page = next;
      load().catch(reportError('Lỗi'));
    });

    if (selected) await showDetail(selected);
    else $('#alertDetails').innerHTML = '<div class="empty-state">Không có cảnh báo phù hợp.</div>';
  }

  function applyFilter(next, activeTab) {
    filter = { page: 1, pageSize: 10, ...next };
    $$('button', $('#alertTabs')).forEach(button => button.classList.toggle('active', button === activeTab));
    load().catch(reportError('Lỗi'));
  }

  function setup() {
    $('#alertTabs').onclick = event => {
      const button = event.target.closest('button');
      if (!button) return;
      const next = {};
      if (button.dataset.status) next.status = button.dataset.status;
      if (button.dataset.severity) next.severity = button.dataset.severity;
      applyFilter(next, button);
    };

    $('#alertsList').onclick = event => {
      const id = event.target.closest('[data-alert]')?.dataset.alert;
      if (!id) return;
      selected = id;
      $$('.alert-row').forEach(row => row.classList.toggle('selected', row.dataset.alert === id));
      showDetail(id).catch(reportError('Lỗi'));
    };

    // Bộ lọc nâng cao (mức độ + trạng thái)
    const dialog = $('#advancedAlertDialog');
    const form = $('#advancedAlertForm');
    $('#advancedAlertFilter').onclick = () => dialog.showModal();
    form.querySelector('[data-close]').onclick = () => dialog.close();
    form.onsubmit = event => {
      event.preventDefault();
      const data = new FormData(form);
      const next = {};
      if (data.get('severity')) next.severity = data.get('severity');
      if (data.get('status')) next.status = data.get('status');
      const tab = $$('button', $('#alertTabs')).find(button =>
        Object.keys(next).length === 1 &&
        (next.status ? button.dataset.status === next.status : button.dataset.severity === next.severity));
      dialog.close();
      applyFilter(next, tab || (Object.keys(next).length ? null : $('#alertTabs button')));
    };
  }

  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(load);
})();
