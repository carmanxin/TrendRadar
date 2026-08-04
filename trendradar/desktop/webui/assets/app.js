// trendradar/desktop/webui/assets/app.js
async function loadStatus() {
  try {
    const r = await fetch("/api/system/status");
    const data = await r.json();
    document.getElementById("status").textContent = data.status;
  } catch (e) {
    document.getElementById("status").textContent = "无法连接后端";
  }
}
loadStatus();
