/* Trang Cài đặt (Telegram) */
(() => {
  'use strict';
  const { $, esc } = SW;

  async function loadStatus() {
    const s = await SW.api('/api/telegram/status');
    $('#telegramStatus').textContent = s.isConfigured
      ? 'Telegram đã được cấu hình trên máy chủ.'
      : 'Telegram chưa có bot token / chat id trên máy chủ (xem file .env).';
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

  function setup() {
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
  SW.boot(async () => { await Promise.all([loadStatus(), loadMessages()]); }, { realtime: false });
})();
