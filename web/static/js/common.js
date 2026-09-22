/* SafeWatch Admin - tiện ích dùng chung cho mọi trang (namespace window.SW). */
(() => {
  'use strict';

  const SW = (window.SW = {});
  const page = document.body.dataset.page || 'overview';
  const charts = {};

  // ---- DOM ---------------------------------------------------------------------
  SW.$ = (selector, root = document) => root.querySelector(selector);
  SW.$$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  // ---- định dạng -------------------------------------------------------------------
  const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  SW.esc = value => String(value ?? '').replace(/[&<>"']/g, c => ESCAPES[c]);

  const timeFormat = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' });
  const dateFormat = new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  SW.time = value => (value ? timeFormat.format(new Date(value)) : '—');
  SW.date = value => (value ? dateFormat.format(new Date(value)) : '—');

  const LABELS = {
    active: 'Đang hoạt động', low_battery: 'Pin yếu', offline: 'Mất kết nối', error: 'Lỗi',
    open: 'Chưa xử lý', acknowledged: 'Đã xác nhận', closed: 'Đã đóng',
    high: 'Nguy hiểm cao', medium: 'Trung bình', low: 'Thấp',
    fall: 'Té ngã', heart_rate: 'Nhịp tim bất thường', connection: 'Mất kết nối',
    good: 'Tốt', weak: 'Yếu',
    created: 'Tạo cảnh báo', marked_urgent: 'Đánh dấu khẩn cấp',
    acknowledge: 'Xác nhận đã xem', urgent: 'Đánh dấu khẩn cấp', close: 'Đóng cảnh báo',
  };
  SW.label = value => LABELS[value] || value || '—';

  const ICONS = {
    fall: 'bi-person-fill-down', heart_rate: 'bi-heart-pulse-fill', connection: 'bi-wifi-off', low_battery: 'bi-battery-half',
  };
  SW.icon = type => ICONS[type] || 'bi-exclamation-triangle';

  SW.badge = value => {
    const kind = ['active', 'normal', 'acknowledged', 'closed'].includes(value) ? 'active'
      : ['low_battery', 'medium', 'low'].includes(value) ? 'low_battery'
      : ['offline', 'high', 'open', 'fall'].includes(value) ? 'high' : 'info';
    return `<span class="status-badge status-${kind}">${SW.esc(SW.label(value))}</span>`;
  };

  SW.metric = (title, value, kind, iconName, note = 'Cập nhật theo thời gian thực') => `
    <article class="metric-card metric-${kind}">
      <span class="metric-icon"><i class="bi ${iconName}"></i></span>
      <div><p>${title}</p><strong>${SW.esc(value)}</strong><small>${note}</small></div>
    </article>`;

  SW.bpm = (value, empty = '--') => (value ? `${value} bpm` : empty);

  // ---- thông báo nhỏ ---------------------------------------------------------------
  SW.toast = (title, message = '', bad = false) => {
    const region = SW.$('.sw-toast-region');
    if (!region) return;
    const item = document.createElement('div');
    item.className = 'toast-item';
    item.innerHTML = `<i class="bi ${bad ? 'bi-exclamation-octagon-fill' : 'bi-check-circle-fill'}"></i>
      <div><strong>${SW.esc(title)}</strong>${message ? `<span>${SW.esc(message)}</span>` : ''}</div>`;
    region.append(item);
    setTimeout(() => item.remove(), 4300);
  };
  SW.fail = title => error => SW.toast(title, error.message, true);

  // ---- gọi API ---------------------------------------------------------------------
  SW.csrf = SW.$('meta[name="csrf-token"]')?.content || '';

  SW.api = async (path, options = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    const headers = {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    };
    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method) && SW.csrf) headers['X-CSRF-Token'] = SW.csrf;

    const response = await fetch(path, { ...options, method, headers, credentials: 'same-origin' });
    if (response.status === 401) {
      location.href = '/account/login?returnUrl=' + encodeURIComponent(location.pathname + location.search);
      throw new Error('Phiên đăng nhập đã hết hạn.');
    }
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.error || 'Không thể xử lý yêu cầu.');
    return data;
  };

  // ---- biểu đồ (Chart.js) ------------------------------------------------------------------
  SW.chart = (name, canvas, config) => {
    charts[name]?.destroy();
    charts[name] = new Chart(canvas, config);
    return charts[name];
  };

  // ---- phân trang ------------------------------------------------------------------------------
  SW.pagination = (element, pageNumber, totalPages, onPage) => {
    if (!element) return;
    const total = Math.max(1, totalPages || 1);
    const current = Math.min(Math.max(1, pageNumber || 1), total);
    const first = Math.max(1, Math.min(current - 2, total - 4));
    const last = Math.min(total, first + 4);
    const buttons = [
      `<button class="btn-outline-sw small" data-page="${current - 1}" ${current <= 1 ? 'disabled' : ''} aria-label="Trang trước"><i class="bi bi-chevron-left"></i></button>`,
    ];
    for (let value = first; value <= last; value++) {
      buttons.push(`<button class="btn-outline-sw small ${value === current ? 'active' : ''}" data-page="${value}">${value}</button>`);
    }
    buttons.push(`<button class="btn-outline-sw small" data-page="${current + 1}" ${current >= total ? 'disabled' : ''} aria-label="Trang sau"><i class="bi bi-chevron-right"></i></button>`);
    element.innerHTML = buttons.join('');
    element.onclick = event => {
      const button = event.target.closest('[data-page]');
      if (!button || button.disabled) return;
      const next = Number(button.dataset.page);
      if (Number.isInteger(next) && next >= 1 && next <= total && next !== current) onPage(next);
    };
  };

  // ---- khung trang (sidebar, tìm kiếm, số cảnh báo) --------------------------------------------------
  const updateNotificationCount = () =>
    SW.api('/api/dashboard/overview')
      .then(data => { const el = SW.$('#notificationCount'); if (el) el.textContent = data.openAlerts; })
      .catch(() => {});

  function setupShell() {
    SW.$('#sidebarToggle')?.addEventListener('click', event => {
      const sidebar = SW.$('#sidebar');
      const mobile = window.matchMedia('(max-width: 991px)').matches;
      if (mobile) {
        sidebar.classList.toggle('mobile-open');
      } else {
        document.body.classList.toggle('collapsed-sidebar');
      }
      event.currentTarget.setAttribute(
        'aria-label',
        mobile && sidebar.classList.contains('mobile-open') ? 'Đóng menu' : 'Mở menu',
      );
    });

    const facilityButton = SW.$('#facilitySwitch');
    const facilityMenu = SW.$('#facilityMenu');
    const facilityName = SW.$('#facilityName');
    if (facilityButton && facilityMenu && facilityName) {
      const closeFacilities = () => {
        facilityMenu.classList.remove('open');
        facilityButton.setAttribute('aria-expanded', 'false');
      };
      const loadFacilities = async () => {
        try {
          const facilities = await SW.api('/api/facilities');
          facilityMenu.innerHTML = facilities.length
            ? facilities.map(f => `<button type="button" role="option" data-facility-name="${SW.esc(f.name)}">${SW.esc(f.name)}</button>`).join('')
            : '<span class="facility-menu-empty">Chưa có cơ sở</span>';
          facilityMenu.onclick = event => {
            const option = event.target.closest('[data-facility-name]');
            if (!option) return;
            facilityName.textContent = option.dataset.facilityName;
            closeFacilities();
          };
        } catch {
          facilityMenu.innerHTML = '<span class="facility-menu-empty">Không tải được danh sách</span>';
        }
      };
      facilityButton.addEventListener('click', async () => {
        const open = facilityMenu.classList.toggle('open');
        facilityButton.setAttribute('aria-expanded', String(open));
        if (open && !facilityMenu.dataset.loaded) {
          await loadFacilities();
          facilityMenu.dataset.loaded = 'true';
        }
      });
      document.addEventListener('click', event => {
        if (!event.target.closest('.facility-picker')) closeFacilities();
      });
    }

    SW.$('#globalSearch')?.addEventListener('submit', event => {
      event.preventDefault();
      const q = SW.$('#globalSearchInput').value.trim();
      if (!q) return;
      const target = /^sw/i.test(q) ? '/devices' : /cảnh|alert/i.test(q) ? '/alerts' : '/users';
      location.href = `${target}?q=${encodeURIComponent(q)}`;
    });

    if (page !== 'overview') updateNotificationCount();
  }

  // ---- thời gian thực (Server-Sent Events) -------------------------------------------------------
  const REALTIME_EVENTS = ['TelemetryUpdated', 'DeviceUpdated', 'AlertCreated', 'AlertUpdated'];

  function startRealtime(refresh) {
    if (!window.EventSource) return;
    let timer;
    const source = new EventSource('/api/events');
    REALTIME_EVENTS.forEach(name =>
      source.addEventListener(name, () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          if (refresh) refresh().catch(() => {});
          if (page !== 'overview') updateNotificationCount();
        }, 500);
      }));
    // EventSource tự kết nối lại khi mất mạng nên không cần xử lý onerror.
  }

  /**
   * Khởi động trang: load() dựng giao diện, được gọi lại mỗi khi có sự kiện realtime.
   * Trang không cần tự làm mới (form, cài đặt) truyền { realtime: false }.
   */
  SW.boot = (load, { realtime = true } = {}) => {
    document.addEventListener('DOMContentLoaded', () => {
      setupShell();
      Promise.resolve(load()).catch(SW.fail('Không thể tải dữ liệu'));
      if (realtime) startRealtime(load);
    });
  };
})();
