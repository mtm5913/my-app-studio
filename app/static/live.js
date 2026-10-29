/* Development-only saved-file refresh. Never stores credentials or form values. */
(() => {
  let current;
  async function check() {
    try {
      const response = await fetch('/__studio/revision', {cache: 'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      if (current && data.revision !== current) window.location.reload();
      current = data.revision;
    } catch { /* The Python reloader may briefly stop the server. */ }
  }
  check();
  window.setInterval(check, 800);
})();
