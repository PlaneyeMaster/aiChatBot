const $ = (id) => document.getElementById(id);
const setStatus = (s) => $("status").textContent = s;

let activeTab = "users";
let selectedSessionId = null;

function apiBase() { return $("apiBase").value.trim(); }
function setApiPill() { $("apiPill").textContent = "API: " + apiBase(); }

async function apiFetch(path, opts={}) {
  setApiPill();
  const headers = {
    ...(opts.headers || {}),
    "X-Admin-Key": $("adminKey").value.trim(),
  };
  const res = await fetch(apiBase() + path, { ...opts, headers });
  if (!res.ok) {
    const t = await res.text().catch(()=> "");
    throw new Error(`HTTP ${res.status} ${res.statusText} :: ${t}`);
  }
  return res;
}

function escapeHtml(s) {
  return (s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

// -------- Tabs --------
function showTab(name) {
  activeTab = name;
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  $("tab-users").style.display = (name === "users") ? "" : "none";
  $("tab-sessions").style.display = (name === "sessions") ? "" : "none";
  $("tab-memory").style.display = (name === "memory") ? "" : "none";
  setStatus("tab: " + name);
}

document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => showTab(t.dataset.tab));
});

$("btnRefresh").addEventListener("click", async () => {
  if (activeTab === "users") return loadUser();
  if (activeTab === "sessions") return loadSessions();
  if (activeTab === "memory") return loadMemory();
});

// -------- Users --------
async function loadUser() {
  const userId = $("userId").value.trim();
  if (!userId) return alert("user_id를 입력하세요.");
  setStatus("loading user...");
  const res = await apiFetch(`/admin/users/${encodeURIComponent(userId)}`);
  const json = await res.json();
  const u = json.user || {};
  $("tone").value = u.tone || "";
  $("goal").value = u.goal || "";
  $("expertise").value = u.expertise || "";
  $("age_band").value = u.age_band || "";
  setStatus("user loaded");
}

async function saveUser() {
  const id = $("userId").value.trim();
  if (!id) return alert("user_id를 입력하세요.");

  setStatus("saving user...");
  const body = {
    id,
    tone: $("tone").value.trim() || null,
    goal: $("goal").value.trim() || null,
    expertise: $("expertise").value || null,
    age_band: $("age_band").value || null,
  };

  const res = await apiFetch(`/admin/users/upsert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await res.json();
  setStatus("user saved");
}

$("btnLoadUser").addEventListener("click", () => loadUser().catch(e => { alert(e.message); setStatus("error"); }));
$("btnSaveUser").addEventListener("click", () => saveUser().catch(e => { alert(e.message); setStatus("error"); }));

// -------- Sessions --------
async function loadSessions() {
  const userId = $("userId").value.trim();
  if (!userId) return alert("user_id를 입력하세요.");
  setStatus("loading sessions...");
  const res = await apiFetch(`/admin/sessions?user_id=${encodeURIComponent(userId)}&limit=50`);
  const json = await res.json();

  const list = $("sessionList");
  list.innerHTML = "";
  selectedSessionId = null;
  $("btnLoadMessages").disabled = true;
  $("messageList").innerHTML = "";

  (json.items || []).forEach((s) => {
    const div = document.createElement("div");
    div.className = "item";
    div.dataset.id = s.id;
    div.innerHTML = `
      <div><b>${escapeHtml(s.id)}</b></div>
      <div class="muted">created: ${escapeHtml((s.created_at||"").slice(0,19).replace("T"," "))}</div>
      <div class="muted">char: ${escapeHtml(s.character_id||"")} / scn: ${escapeHtml(s.scenario_id||"")}</div>
      <div class="muted">status: ${escapeHtml(s.status||"")}</div>
    `;
    div.addEventListener("click", () => {
      document.querySelectorAll("#sessionList .item").forEach(x => x.classList.remove("active"));
      div.classList.add("active");
      selectedSessionId = s.id;
      $("btnLoadMessages").disabled = false;
      setStatus("selected session");
    });
    list.appendChild(div);
  });

  setStatus(`sessions loaded (${(json.items||[]).length})`);
}

async function loadMessages() {
  if (!selectedSessionId) return alert("세션을 선택하세요.");
  setStatus("loading messages...");
  const res = await apiFetch(`/admin/sessions/${encodeURIComponent(selectedSessionId)}/messages?limit=400`);
  const json = await res.json();

  const box = $("messageList");
  box.innerHTML = "";
  (json.items || []).forEach((m) => {
    const role = (m.role || "user").toUpperCase();
    const t = (m.created_at || "").slice(0,19).replace("T"," ");
    const div = document.createElement("div");
    div.className = "item";
    div.style.cursor = "default";
    div.innerHTML = `<div class="muted">${t} | ${role}</div><div>${escapeHtml(m.content||"")}</div>`;
    box.appendChild(div);
  });

  setStatus(`messages loaded (${(json.items||[]).length})`);
}

$("btnLoadSessions").addEventListener("click", () => loadSessions().catch(e => { alert(e.message); setStatus("error"); }));
$("btnLoadMessages").addEventListener("click", () => loadMessages().catch(e => { alert(e.message); setStatus("error"); }));

// -------- Memory --------
async function loadMemory() {
  const userId = $("userId").value.trim();
  if (!userId) return alert("user_id를 입력하세요.");
  setStatus("loading memory...");
  const res = await apiFetch(`/admin/memory?user_id=${encodeURIComponent(userId)}&limit=200`);
  const json = await res.json();

  const tbody = $("memTbody");
  tbody.innerHTML = "";

  (json.items || []).forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml((m.created_at||"").slice(0,19).replace("T"," "))}</td>
      <td>${escapeHtml(m.text || "")}</td>
      <td><span class="muted">${escapeHtml(m.pinecone_vector_id || "")}</span></td>
      <td><button class="danger" data-id="${escapeHtml(m.id)}">삭제</button></td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button.danger").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      if (!confirm("Supabase + Pinecone에서 모두 삭제합니다. 진행할까요?")) return;
      try {
        setStatus("deleting...");
        await apiFetch(`/admin/memory/${encodeURIComponent(id)}`, { method: "DELETE" });
        setStatus("deleted");
        await loadMemory();
      } catch (e) {
        alert(e.message);
        setStatus("error");
      }
    });
  });

  setStatus(`memory loaded (${(json.items||[]).length})`);
}

$("btnLoadMemory").addEventListener("click", () => loadMemory().catch(e => { alert(e.message); setStatus("error"); }));

// -------- Init --------
window.addEventListener("load", () => {
  setApiPill();
  showTab("users");
});
