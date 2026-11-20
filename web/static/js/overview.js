/* Trang Tổng quan */
(() => {
  'use strict';
  const { $, esc, time, label, icon, badge, metric, bpm } = SW;

  const STATUS_COLORS = ['#55bd67', '#2878e8', '#ff9a19', '#ef3838'];

  function alertIconClass(type) {
    return type === 'connection' ? 'connection' : type === 'low_battery' ? 'battery' : '';
  }

  async function load() {
    const data = await SW.api('/api/dashboard/overview');

    $('#overviewMetrics').innerHTML =
      metric('Đồng hồ đang hoạt động', data.activeDevices, 'success', 'bi-smartwatch', '↑ cập nhật theo thời gian thực') +
      metric('Cảnh báo đang mở', data.openAlerts, 'warning', 'bi-exclamation-triangle', 'Cần theo dõi') +
      metric('Người dùng đang theo dõi', data.monitoredUsers, 'info', 'bi-people', 'Đang được giám sát') +
      metric('Sự kiện té ngã hôm nay', data.fallsToday, 'danger', 'bi-person-fill-down', 'Dữ liệu hôm nay');

    SW.chart('trend', $('#alertsTrendChart'), {
      type: 'line',
      data: {
        labels: data.alertsTrend.map(x => x.label),
        datasets: [{
          data: data.alertsTrend.map(x => x.value),
          borderColor: '#1266e9', backgroundColor: 'rgba(18,102,233,.10)',
          fill: true, tension: 0.38, pointRadius: 4, pointBackgroundColor: '#1266e9',
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 5 } }, x: { grid: { display: false } } },
      },
    });

    SW.chart('status', $('#deviceStatusChart'), {
      type: 'doughnut',
      data: {
        labels: data.deviceStatus.map(x => label(x.status)),
        datasets: [{ data: data.deviceStatus.map(x => x.count), backgroundColor: STATUS_COLORS, borderWidth: 2, borderColor: '#fff', cutout: '70%' }],
      },
      options: { plugins: { legend: { display: false } }, responsive: true, maintainAspectRatio: false },
    });
    $('#deviceTotal').textContent = data.totalDevices;
    $('#deviceLegend').innerHTML = data.deviceStatus.map((x, i) =>
      `<div class="legend-row"><span class="legend-dot" style="background:${STATUS_COLORS[i]}"></span><span>${esc(label(x.status))}</span><b>${x.count} (${x.percentage}%)</b></div>`).join('');

    $('#latestAlerts').innerHTML = data.latestAlerts.map(a => `
      <a class="latest-alert-item" href="/alerts?id=${encodeURIComponent(a.id)}">
        <span class="alert-icon ${alertIconClass(a.type)}"><i class="bi ${icon(a.type)}"></i></span>
        <span><strong>${esc(a.message)}</strong><small>${esc(a.userName)}<br>${esc(a.roomName)} - ${esc(a.facilityName)}</small></span>
        <span class="alert-time">${time(a.eventAt)}</span>
      </a>`).join('') || '<div class="empty-state">Chưa có cảnh báo mới.</div>';

    $('#liveDevices').innerHTML = data.liveDevices.map(d => `
      <tr>
        <td><span class="device-code"><span class="device-glyph"><i class="bi bi-smartwatch"></i></span><strong>${esc(d.id)}</strong></span></td>
        <td><strong>${esc(d.wearerName)}</strong><span class="cell-sub">${esc(d.roomName)} - ${esc(d.facilityName)}</span></td>
        <td>${badge(d.status)}</td>
        <td class="battery-${d.battery <= 20 ? 'low' : 'good'}"><i class="bi bi-battery-${d.battery > 70 ? 'full' : 'half'}"></i> ${d.battery}%</td>
        <td class="${d.heartRate > 100 ? 'heart-high' : 'heart-good'}"><i class="bi bi-heart-fill"></i> ${bpm(d.heartRate)}</td>
        <td>${d.spo2 != null ? `${d.spo2}%` : '—'}</td>
        <td>${d.connectionStatus === 'offline' ? '<i class="bi bi-reception-0 text-danger"></i>' : '<i class="bi bi-reception-4 text-success"></i>'}</td>
        <td>${time(d.lastUpdated)}</td>
      </tr>`).join('');
    $('#liveSummary').textContent = `Hiển thị ${data.liveDevices.length} trong tổng số ${data.totalDevices} thiết bị`;
    $('#notificationCount').textContent = data.openAlerts;
  }

  SW.boot(load);
})();
