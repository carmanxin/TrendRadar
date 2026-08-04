// trendradar/desktop/webui/assets/app.js
const content = document.getElementById("content");

async function loadStatus() {
  const r = await fetch("/api/system/status");
  return (await r.json()).status;
}

async function loadPartial(name) {
  const r = await fetch(`/partials/${name}.html`);
  content.innerHTML = await r.text();
  if (name === "home") wireHome();
  if (name === "settings") wireSettings();
}

document.querySelectorAll("nav button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    loadPartial(b.dataset.tab);
  });
});

async function init() {
  const status = await loadStatus();
  if (status === "NEED_WIZARD") {
    content.innerHTML = await (await fetch("/partials/wizard.html")).text();
    wireWizard();
  } else {
    document.querySelector('[data-tab="home"]').classList.add("active");
    loadPartial("home");
  }
  fetch("/api/system/info").then((r) => r.json()).then((d) => {
    document.getElementById("version").textContent = "v" + d.version;
  });
}

function wireWizard() {
  const form = document.getElementById("wizard-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = Object.fromEntries(fd.entries());
    const r = await fetch("/api/wizard/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      document.getElementById("wizard-error").hidden = false;
      document.getElementById("wizard-error").textContent = "保存失败: " + r.status;
      return;
    }
    location.reload();
  });
}

async function wireHome() {
  document.getElementById("run-btn").addEventListener("click", async () => {
    const r = await fetch("/api/run/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!r.ok) { alert("启动失败: " + r.status); return; }
    document.getElementById("logs").textContent = "";
    const es = new EventSource("/api/run/logs/stream");
    es.onmessage = (ev) => {
      document.getElementById("logs").textContent += ev.data + "\n";
      document.getElementById("logs").scrollTop = document.getElementById("logs").scrollHeight;
    };
    es.addEventListener("end", () => es.close());
  });
  document.getElementById("stop-btn").addEventListener("click", async () => {
    await fetch("/api/run/stop", { method: "POST" });
  });
  const rep = await (await fetch("/api/reports")).json();
  document.getElementById("report-list").innerHTML = rep.reports
    .slice(0, 5)
    .map((r) => `<li>${r.date} (${r.files.length} 份)</li>`)
    .join("");
}

async function wireSettings() {
  const cfg = await (await fetch("/api/config")).json();
  const kw = await (await fetch("/api/keywords")).json();
  document.getElementById("ai-key").value = cfg.ai?.api_key || "";
  document.getElementById("keywords").value = kw.content;

  document.getElementById("save-key").onclick = async () => {
    const k = document.getElementById("ai-key").value;
    await fetch("/api/config/section/ai", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...(cfg.ai || {}), api_key: k }),
    });
    alert("已保存");
  };
  document.getElementById("save-keywords").onclick = async () => {
    await fetch("/api/keywords", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: document.getElementById("keywords").value }),
    });
    alert("已保存");
  };

  const plats = await (await fetch("/api/sources/platforms")).json();
  document.getElementById("platforms").innerHTML = plats
    .map((p) => `<label><input type="checkbox" data-platform="${p.id}" ${p.enabled !== false ? "checked" : ""}/>${p.name}</label>`)
    .join("");
  document.getElementById("platforms").addEventListener("change", async () => {
    const enabled = [...document.querySelectorAll('[data-platform]:checked')].map((x) => x.dataset.platform);
    await fetch("/api/sources/platforms", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled_ids: enabled }),
    });
  });
  const rss = await (await fetch("/api/sources/rss")).json();
  document.getElementById("rss").innerHTML = rss
    .map((f) => `<label><input type="checkbox" data-rss="${f.id}" ${f.enabled !== false ? "checked" : ""}/>${f.name}</label>`)
    .join("");
  document.getElementById("rss").addEventListener("change", async () => {
    const enabled = [...document.querySelectorAll('[data-rss]:checked')].map((x) => x.dataset.rss);
    await fetch("/api/sources/rss", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled_ids: enabled }),
    });
  });
}

init();
