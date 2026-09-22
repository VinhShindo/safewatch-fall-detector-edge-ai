/* Trang Điều hành nhiều cơ sở */
(() => {
  'use strict';
  const { $, esc, metric } = SW;

  const FACILITY_COLORS = ['#ef4b4e', '#ff9725', '#ffc42e', '#7fc277'];
  const FACILITY_PAGE_SIZE = 3;
  let facilityPage = 1;

  function renderFacilityTable(facilities) {
    const totalPages = Math.max(1, Math.ceil(facilities.length / FACILITY_PAGE_SIZE));
    facilityPage = Math.min(facilityPage, totalPages);
    const start = (facilityPage - 1) * FACILITY_PAGE_SIZE;
    const visible = facilities.slice(start, start + FACILITY_PAGE_SIZE);
    $('#facilityTable').innerHTML = visible.map(x => `
      <tr>
        <td><strong><i class="bi bi-building text-success"></i> ${esc(x.name)}</strong></td>
        <td>${x.totalDevices}</td><td>${x.totalUsers}</td><td class="heart-high">${x.openAlerts}</td>
        <td>${esc(x.onDutyStaff?.fullName || '—')}<span class="cell-sub">${esc(x.onDutyStaff?.shiftStart || '')} - ${esc(x.onDutyStaff?.shiftEnd || '')}</span></td>
      </tr>`).join('') || '<tr><td colspan="5" class="text-center py-4">Chưa có cơ sở.</td></tr>';
    $('#facilityPageInfo').textContent = `Trang ${facilityPage}/${totalPages} · Hiển thị ${visible.length} trong tổng số ${facilities.length} cơ sở`;
    SW.pagination($('#facilityPagination'), facilityPage, totalPages, next => {
      facilityPage = next;
      renderFacilityTable(facilities);
    });
  }

  async function load() {
    const d = await SW.api('/api/dashboard/overview');
    const f = d.facilities;
    const count = status => d.deviceStatus.find(x => x.status === status)?.count || 0;

    $('#reportMetrics').innerHTML =
      metric('Tổng số cơ sở', f.length, 'success', 'bi-building') +
      metric('Tổng đồng hồ', d.totalDevices, 'success', 'bi-smartwatch') +
      metric('Người đang theo dõi', d.monitoredUsers, 'info', 'bi-people') +
      metric('Té ngã hôm nay', d.fallsToday, 'danger', 'bi-exclamation-triangle');

    $('#campusPlan').innerHTML = f.map(x => `
      <article class="campus-zone">
        <h3><i class="bi bi-building text-success"></i> ${esc(x.name)}</h3>
        <p><span>● Bình thường</span><b>${x.normalDevices}</b></p>
        <p><span class="text-warning">● Cảnh báo</span><b>${x.alertDevices}</b></p>
        <p><span class="text-danger">● Ngoại tuyến</span><b>${x.offlineDevices}</b></p>
      </article>`).join('');

    SW.chart('facility', $('#facilityChart'), {
      type: 'doughnut',
      data: {
        labels: f.map(x => x.name),
        datasets: [{ data: f.map(x => x.openAlerts), backgroundColor: FACILITY_COLORS, borderColor: '#fff', borderWidth: 2, cutout: '67%' }],
      },
      options: { plugins: { legend: { display: false } }, responsive: true, maintainAspectRatio: false },
    });
    $('#facilityAlertTotal').textContent = f.reduce((sum, x) => sum + x.openAlerts, 0);
    $('#facilityLegend').innerHTML = f.map((x, i) =>
      `<div class="legend-row"><span class="legend-dot" style="background:${FACILITY_COLORS[i % FACILITY_COLORS.length]}"></span><span>${esc(x.name)}</span><b>${x.openAlerts}</b></div>`).join('');

    renderFacilityTable(f);

    $('#quickAlerts').innerHTML = `
      <div class="quick-alert"><i class="bi bi-bell"></i><span>Cảnh báo mở</span><strong>${d.openAlerts}</strong></div>
      <div class="quick-alert"><i class="bi bi-smartwatch text-success"></i><span>Đồng hồ ngoại tuyến</span><strong>${count('offline')}</strong></div>
      <div class="quick-alert"><i class="bi bi-battery-half text-warning"></i><span>Pin yếu</span><strong>${count('low_battery')}</strong></div>`;
    $('#notificationCount').textContent = d.openAlerts;
  }

  function setup() {
    $('#refreshReports').onclick = () =>
      load().then(() => SW.toast('Đã làm mới', 'Dữ liệu các cơ sở đã được cập nhật.')).catch(SW.fail('Lỗi'));

    $('#telegramConnect').onclick = async () => {
      try {
        const result = await SW.api('/api/telegram/test', { method: 'POST' });
        SW.toast(result.success ? 'Đã gửi Telegram' : 'Telegram chưa sẵn sàng', result.message, !result.success);
      } catch (error) { SW.toast('Lỗi', error.message, true); }
    };
  }

  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(load);
})();
