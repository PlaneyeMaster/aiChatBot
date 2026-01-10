// 로그인 가드: 최초 접속 시 로그인 페이지로 보냄
const userId = localStorage.getItem("user_id");
if (!userId) location.href = "./login.html";
const API_BASE = localStorage.getItem("api_base") || "https://aichatbot-ez4g.onrender.com";

const $ = (id) => document.getElementById(id);

let catalog = { characters: [], scenarios: [] };
let currentSession = null;
let streaming = false;
let abortController = null;
let lastScenarioOutline = "";
let lastScenarioStory = "";

// meta state
let meta = {
  model: "-",
  memory_stats: { saved:0, skipped_dup:0, skipped_low:0 },
  last_error: "-"
};

function setPillStatus(text){ $("pillStatus").textContent = text; }
function setApiPill(){
  const base = API_BASE;
  const linkDocs = document.getElementById("linkDocs");
  const linkCharacters = document.getElementById("linkCharacters");
  const linkScenarios = document.getElementById("linkScenarios");
  if (linkDocs) linkDocs.href = base + "/docs";
  if (linkCharacters) linkCharacters.href = base + "/catalog/characters";
  if (linkScenarios) linkScenarios.href = base + "/catalog/scenarios";
}
function setSessionPill(){
  const sid = currentSession?.id || "-";
  const pillSession = document.getElementById("pillSession");
  if (pillSession) pillSession.textContent = sid;
  const statSession = document.getElementById("statSession");
  if (statSession) statSession.textContent = sid;
}
function setError(msg){
  meta.last_error = msg || "-";
  const statError = document.getElementById("statError");
  if (statError) statError.textContent = meta.last_error;
  const dbgLastError = document.getElementById("dbgLastError");
  if (dbgLastError) dbgLastError.textContent = meta.last_error;
}
function setModel(m){
  meta.model = m || "-";
  const statModel = document.getElementById("statModel");
  if (statModel) statModel.textContent = meta.model;
}
function setMemoryStats(obj){
  if (!obj) return;
  meta.memory_stats.saved = obj.saved ?? meta.memory_stats.saved;
  meta.memory_stats.skipped_dup = obj.skipped_dup ?? meta.memory_stats.skipped_dup;
  meta.memory_stats.skipped_low = obj.skipped_low ?? meta.memory_stats.skipped_low;

  const statMemory = document.getElementById("statMemory");
  if (statMemory){
    statMemory.textContent = `saved:${meta.memory_stats.saved} dup:${meta.memory_stats.skipped_dup} low:${meta.memory_stats.skipped_low}`;
  }
  const dbgMemory = document.getElementById("dbgMemoryStats");
  if (dbgMemory) dbgMemory.textContent = JSON.stringify(meta.memory_stats);
}
function setStreaming(v){
  streaming = !!v;
  const dbgStreaming = document.getElementById("dbgStreaming");
  if (dbgStreaming) dbgStreaming.textContent = streaming ? "true" : "false";
  $("btnStop").disabled = !streaming;
  $("btnSend").disabled = streaming;
}

async function apiFetch(path, opts={}){
  setApiPill();
  const base = API_BASE;
  const headers = {
    ...(opts.headers || {}),
  };
  if (path.startsWith("/admin/")) {
    const adminKey = localStorage.getItem("admin_api_key");
    if (adminKey) headers["X-Admin-Key"] = adminKey;
  }
  const res = await fetch(base + path, { ...opts, headers });
  if (!res.ok){
    const t = await res.text().catch(()=> "");
    throw new Error(`HTTP ${res.status} ${res.statusText} :: ${t}`);
  }
  return res;
}

function escapeHtml(s){
  return (s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

function appendMsg(role, text, metaLine=""){
  const box = $("chatBox");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = `
    <div class="role">${role.toUpperCase()}</div>
    <div style="flex:1;">
      <div class="bubble" data-role="${role}">${escapeHtml(text)}</div>
      ${metaLine ? `<div class="metaLine">${escapeHtml(metaLine)}</div>` : ""}
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div.querySelector(".bubble");
}

function updateLastAssistantBubbleText(bubble, text){
  bubble.innerHTML = escapeHtml(text);
  const box = $("chatBox");
  box.scrollTop = box.scrollHeight;
}

// ---------- Catalog ----------
async function loadCatalog(){
  setPillStatus("loading catalog...");
  try{
    const [cRes, sRes] = await Promise.all([
      apiFetch("/catalog/characters"),
      apiFetch("/catalog/scenarios")
    ]);
    const cJson = await cRes.json();
    const sJson = await sRes.json();

    catalog.characters = cJson.items || [];
    catalog.scenarios = sJson.items || [];

    const charSel = $("character");
    const scnSel = $("scenario");

    charSel.innerHTML = "";
    catalog.characters.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.name} (${c.id})`;
      opt.dataset.persona = c.persona_prompt || "";
      opt.dataset.image = c.image_url || "";
      opt.dataset.name = c.name || "";
      opt.dataset.desc = c.description || "";
      charSel.appendChild(opt);
    });

    scnSel.innerHTML = "";
    catalog.scenarios.forEach(s => {
      if (s.id === "scn_qa" || s.id === "scn_coach") return;
      const opt = document.createElement("option");
      opt.value = s.id;
      const hideId = s.id === "scn_folk_01" || s.id === "scn_folk_02";
      opt.textContent = hideId ? `${s.name}` : `${s.name} (${s.id})`;
      opt.dataset.scenario = s.scenario_prompt || "";
      opt.dataset.goal = s.goal || "";
      opt.dataset.outline = s.outline || "";
      opt.dataset.story = s.story || "";
      opt.dataset.first = s.first_message || "";
      scnSel.appendChild(opt);
    });

    updateDebugPrompts();
    setPillStatus("catalog loaded");
  }catch(e){
    setError(e.message);
    setPillStatus("catalog error");
    alert(e.message);
  }
}

function updateDebugPrompts(){
  const charOpt = $("character").selectedOptions[0];
  const scnOpt = $("scenario").selectedOptions[0];
  const dbgPersona = document.getElementById("dbgPersona");
  const dbgScenario = document.getElementById("dbgScenario");
  if (dbgPersona) dbgPersona.value = charOpt?.dataset.persona || "";
  if (dbgScenario) dbgScenario.value = scnOpt?.dataset.scenario || "";
  const imgEl = $("characterImage");
  const nameEl = $("characterName");
  const descEl = $("characterDesc");
  const imgRaw = charOpt?.dataset.image || "";
  const imgUrl = imgRaw && !imgRaw.startsWith("http") && !imgRaw.startsWith("/")
    ? "/" + imgRaw
    : imgRaw;
  if (imgEl) imgEl.src = imgUrl || "";
  if (nameEl) nameEl.textContent = charOpt?.dataset.name || charOpt?.textContent || "-";
  if (descEl) descEl.textContent = charOpt?.dataset.desc || "-";
  const goalEl = $("scenarioGoal");
  const outlineEl = $("scenarioOutline");
  const goalText = scnOpt?.dataset.goal || "-";
  if (goalEl) goalEl.textContent = goalText;
  const storyText = scnOpt?.dataset.story || "";
  const outlineText = scnOpt?.dataset.outline || "-";
  if (outlineEl) outlineEl.textContent = outlineText;
  if (currentSession) return;
  if (!scnOpt) return;
}
$("character").addEventListener("change", updateDebugPrompts);
$("scenario").addEventListener("change", updateDebugPrompts);

$("btnReloadCatalog").addEventListener("click", () => loadCatalog());

// ---------- Session ----------
async function createSession(){
  const user_id = localStorage.getItem("user_id");
  if (!user_id) return alert("로그인 후 이용하세요.");

  const character_id = $("character").value;
  const scenario_id = $("scenario").value;

  setPillStatus("creating session...");
  setError("-");
  try{
    const res = await apiFetch("/session/create", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ user_id, character_id, scenario_id })
    });
    const json = await res.json();
    currentSession = json.session;
    setSessionPill();
    setPillStatus("session active");

    // first message
    const scn = json.scenario;
    if (scn?.first_message){
      appendMsg("system", scn.first_message, `scenario: ${scn.name || scenario_id}`);
    }
    await sendMessage("시작", { silentUser: true });
  }catch(e){
    setError(e.message);
    setPillStatus("session error");
    alert(e.message);
  }
}
$("btnCreateSession").addEventListener("click", () => createSession());

// ---------- Streaming (POST SSE) ----------
function parseSseLines(buffer){
  // returns [events, restBuffer]
  const events = [];
  let rest = buffer;

  while (true){
    const idx = rest.indexOf("\n\n");
    if (idx === -1) break;
    const rawEvent = rest.slice(0, idx);
    rest = rest.slice(idx + 2);

    // collect data: lines
    const lines = rawEvent.split("\n");
    const dataLines = lines
      .filter(l => l.startsWith("data:"))
      .map(l => l.slice(5).trimStart());

    if (dataLines.length){
      const dataStr = dataLines.join("\n");
      events.push(dataStr);
    }
  }
  return [events, rest];
}

async function sendMessage(text, opts = {}){
  if (!currentSession?.id) return alert("먼저 세션을 생성하세요.");
  const cleaned = (text || "").trim();
  if (!cleaned) return;

  setError("-");
  setStreaming(true);
  setPillStatus("streaming...");

  // Render user bubble unless auto intro
  if (!opts.silentUser){
    appendMsg("user", cleaned, `session: ${currentSession.id}`);
  }

  // Prepare assistant bubble for incremental updates
  let assistantAccum = "";
  const assistantBubble = appendMsg("assistant", "", "");

  // Abort controller
  abortController = new AbortController();

  try{
    const payload = { session_id: currentSession.id, text: cleaned };

    const res = await apiFetch("/chat/stream", {
      method:"POST",
      headers:{
        "Content-Type":"application/json",
        "Accept":"text/event-stream"
      },
      body: JSON.stringify(payload),
      signal: abortController.signal
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true){
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream:true });

      const [events, rest] = parseSseLines(buffer);
      buffer = rest;

      for (const ev of events){
        // server sends JSON per data:
        let obj = null;
        try{
          obj = JSON.parse(ev);
        }catch{
          // ignore malformed data
          continue;
        }

        if (obj.type === "meta"){
          if (obj.event === "start"){
            setModel(obj.model || "-");
            // show debug
          }
          if (obj.event === "memory_saved"){
            // increment saved optimistically if stats not provided
            setMemoryStats({ saved: (meta.memory_stats.saved + 1) });
          }
          if (obj.event === "memory_stats"){
            setMemoryStats(obj);
          }
        }else if (obj.type === "delta"){
          assistantAccum += (obj.text || "");
          updateLastAssistantBubbleText(assistantBubble, assistantAccum);
        }else if (obj.type === "error"){
          setError(obj.message || "stream error");
          // show in assistant bubble if nothing
          if (!assistantAccum){
            assistantAccum = "[Error] " + (obj.message || "unknown");
            updateLastAssistantBubbleText(assistantBubble, assistantAccum);
          }
        }
      }
    }

    setPillStatus("done");

  }catch(e){
    if (e.name === "AbortError"){
      setPillStatus("stopped");
    }else{
      setError(e.message);
      setPillStatus("stream error");
      alert(e.message);
    }
  }finally{
    setStreaming(false);
    abortController = null;
  }
}

$("btnSend").addEventListener("click", async () => {
  const t = $("inputText").value;
  $("inputText").value = "";
  await sendMessage(t);
});

$("btnStop").addEventListener("click", () => {
  if (abortController){
    abortController.abort();
  }
});

// Enter to send (Shift+Enter newline)
$("inputText").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey){
    e.preventDefault();
    $("btnSend").click();
  }
});

// links
const linkDocs = document.getElementById("linkDocs");
const linkCharacters = document.getElementById("linkCharacters");
const linkScenarios = document.getElementById("linkScenarios");
if (linkDocs) linkDocs.addEventListener("click", () => { setApiPill(); });
if (linkCharacters) linkCharacters.addEventListener("click", () => { setApiPill(); });
if (linkScenarios) linkScenarios.addEventListener("click", () => { setApiPill(); });
$("logoutBtn").addEventListener("click", () => {
  localStorage.removeItem("user_id");
  location.href = "./login.html";
});

// init
window.addEventListener("load", async () => {
  setApiPill();
  setSessionPill();
  setModel("-");
  setMemoryStats({ saved:0, skipped_dup:0, skipped_low:0 });
  setError("-");

  await loadCatalog();
});
