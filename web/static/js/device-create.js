/* Trang Thêm thiết bị & bệnh nhân */
(() => {
  'use strict';
  const { $ } = SW;

  function setup() {
    const form = $('#deviceForm');
    const errorBox = $('#deviceFormError');
    const submit = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async event => {
      event.preventDefault();
      errorBox.textContent = '';
      errorBox.classList.remove('show');

      const data = new FormData(form);
      const text = name => String(data.get(name) ?? '').trim();
      const payload = {
        id: text('id'),
        patientName: text('patientName'),
        birthYear: Number(data.get('birthYear') || 0),
        facilityId: text('facilityId'),
        roomId: text('roomId'),
        battery: Number(data.get('battery') || 100),
        contactName: text('contactName'),
        contactRelation: text('contactRelation'),
        contactPhone: text('contactPhone'),
        doctorName: text('doctorName'),
        doctorPhone: text('doctorPhone'),
      };

      submit.disabled = true;
      try {
        const device = await SW.api('/api/devices', { method: 'POST', body: JSON.stringify(payload) });
        location.href = `/devices?created=${encodeURIComponent(device.id)}`;
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.classList.add('show');
        errorBox.scrollIntoView({ block: 'nearest' });
        submit.disabled = false;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', setup);
  SW.boot(async () => {}, { realtime: false });
})();
