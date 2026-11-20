/* Trang Cài đặt (Telegram) */
(() => {
  'use strict';
  const { $, esc } = SW;

  async function loadStatus() {
    const s = await SW.api('/api/telegram/status');
    $('#telegramStatus').textContent = s.isConfigured
      ? 'Telegram đã được cấu hình trên máy chủ.'
      : 'Telegram chưa có bot token / chat id trên máy chủ (xem file .env).';
    const deliveryStatus = $('#telegramDeliveryStatus');
    if (deliveryStatus) {
      deliveryStatus.textContent = s.lastNotificationStatus
        ? `Lần gửi cảnh báo gần nhất: ${s.lastNotificationStatus}${s.lastNotificationAtUtc ? ` · ${new Date(s.lastNotificationAtUtc).toLocaleString('vi-VN')}` : ''}`
        : 'Chưa có lần gửi cảnh báo nào kể từ khi máy chủ khởi động.';
    }
  }

  async function loadMessages() {
    const box = $('#telegramMessages');
    try {
      const messages = await SW.api('/api/telegram/messages');
      box.innerHTML = messages.length
        ? messages.map(x => `
          <article class="telegram-message">
            <strong>${esc(x.from || 'Telegram')}</strong>
            <small>${x.sentAt ? new Date(x.sentAt).toLocaleString('vi-VN') : ''} · Chat ID: ${esc(x.chatId)}</small>
            <p>${esc(x.text)}</p>
          </article>`).join('')
        : '<div class="empty-state">Chưa có tin nhắn Telegram.</div>';
    } catch {
      box.innerHTML = '<div class="empty-state">Không tải được tin nhắn Telegram.</div>';
    }
  }

  async function loadSupportConfig() {
    const config = await SW.api('/api/support/config');
    const form = $('#supportConfigForm');
    for (const key of ['name', 'phone', 'email', 'hours']) form.elements[key].value = config[key] || '';
  }

  async function loadPortalAccounts() {
    const accounts = await SW.api('/api/portal-accounts');
    $('#portalAccountRows').innerHTML = accounts.length ? accounts.map(account => {
      const scope = account.role === 'family' ? account.residentName : account.facilityName;
      return `<tr><td><strong>${esc(account.username)}</strong>${account.staffName ? `<small class="d-block text-muted">${esc(account.staffName)}</small>` : ''}</td><td>${account.role === 'family' ? 'Người nhà' : 'Nhân viên cơ sở'}</td><td>${esc(scope || 'Chưa gán')}</td><td><button class="btn-outline-sw small" type="button" data-account-toggle data-account-id="${esc(account.id)}" data-active="${account.active}">${account.active ? 'Đang hoạt động · Khóa' : 'Đã khóa · Mở lại'}</button></td></tr>`;
    }).join('') : '<tr><td colspan="4">Chưa có tài khoản portal.</td></tr>';
  }

  function setPortalRoleFields() {
    const family = $('#portalAccountRole').value === 'family';
    SW.$$('.portal-scope-family').forEach(node => node.classList.toggle('d-none', !family));
    SW.$$('.portal-scope-facility').forEach(node => node.classList.toggle('d-none', family));
    $('#portalResidentId').required = family;
    $('#portalFacilityId').required = !family;
  }

  function setup() {
    document.querySelectorAll('[data-password-toggle]').forEach(button => {
      const input = document.getElementById(button.dataset.passwordToggle);
      const icon = button.querySelector('i');
      if (!input || !icon) return;
      button.addEventListener('click', () => {
        const showPassword = input.type === 'password';
        input.type = showPassword ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(showPassword));
        button.setAttribute('aria-label', showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
        button.title = showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu';
        icon.className = showPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
        input.focus({ preventScroll: true });
      });
    });

    $('#portalAccountRows').addEventListener('click', async event => {
      const button = event.target.closest('[data-account-toggle]');
      if (!button) return;
      try {
        await SW.api(`/api/portal-accounts/${encodeURIComponent(button.dataset.accountId)}`, {
          method: 'PATCH',
          body: JSON.stringify({ active: button.dataset.active !== 'true' }),
        });
        await loadPortalAccounts();
        SW.toast('Đã cập nhật trạng thái tài khoản');
      } catch (error) { SW.toast('Không thể cập nhật tài khoản', error.message, true); }
    });
    $('#portalAccountRole').onchange = setPortalRoleFields;
    setPortalRoleFields();
    $('#portalAccountForm').onsubmit = async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      const role = data.get('role');
      const payload = {
        role,
        username: data.get('username'),
        password: data.get('password'),
        residentId: role === 'family' ? data.get('residentId') : null,
        facilityId: role === 'facility' ? data.get('facilityId') : null,
        staffId: role === 'facility' ? (data.get('staffId') || null) : null,
      };
      try {
        await SW.api('/api/portal-accounts', { method: 'POST', body: JSON.stringify(payload) });
        form.reset();
        setPortalRoleFields();
        await loadPortalAccounts();
        SW.toast('Đã tạo tài khoản portal');
      } catch (error) { SW.toast('Không thể tạo tài khoản', error.message, true); }
    };
    $('#supportConfigForm').onsubmit = async event => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(event.currentTarget));
      try {
        const saved = await SW.api('/api/support/config', { method: 'POST', body: JSON.stringify(data) });
        const supportCard = $('.support-card');
        if (supportCard) {
          supportCard.querySelector('strong').textContent = saved.name || 'Chưa cấu hình';
          supportCard.querySelector('em').textContent = saved.phone || saved.email || 'Thêm thông tin hỗ trợ trong Cài đặt';
        }
        SW.toast('Đã lưu thông tin hỗ trợ');
      } catch (error) { SW.toast('Không thể lưu thông tin hỗ trợ', error.message, true); }
    };
    $('#telegramConfigForm').onsubmit = async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      try {
        await SW.api('/api/telegram/config', { method: 'POST', body: JSON.stringify({ enabled: data.get('enabled') === 'on', botToken: data.get('botToken'), chatId: data.get('chatId') }) });
        form.reset();
        SW.toast('Đã lưu cấu hình Telegram');
        await loadStatus();
      } catch (error) { SW.toast('Không thể lưu cấu hình', error.message, true); }
    };
    $('#testTelegram').onclick = async () => {
      try {
        const r = await SW.api('/api/telegram/test', { method: 'POST' });
        SW.toast(r.success ? 'Gửi thành công' : 'Không thể gửi', r.message, !r.success);
        await loadStatus();
      } catch (error) { SW.toast('Lỗi', error.message, true); }
    };
    $('#refreshTelegramMessages').onclick = loadMessages;
  }

  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(async () => { await Promise.all([loadSupportConfig(), loadPortalAccounts(), loadStatus(), loadMessages()]); }, { realtime: false });
})();
