/* Progressive enhancement: preview a chosen avatar locally before saving. */
document.addEventListener('DOMContentLoaded', function () {
  const input = document.querySelector('.slqs-member-photo-input');
  const preview = document.getElementById('slqs-avatar-preview');
  if (!input || !preview) return;
  let objectUrl = null;
  input.addEventListener('change', function () {
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
    const file = input.files && input.files[0];
    if (!file || !/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > 5 * 1024 * 1024) return;
    objectUrl = URL.createObjectURL(file);
    let img = preview.querySelector('img');
    if (!img) {
      img = document.createElement('img');
      img.alt = 'Profile photo preview';
      img.width = 116;
      img.height = 116;
      preview.replaceChildren(img);
    }
    img.src = objectUrl;
  });
  window.addEventListener('pagehide', function () {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  });
});
