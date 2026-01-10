const DEFAULT_API_BASE = "https://aichatbot-ez4g.onrender.com";
const ID_RE = /^[A-Za-z]+$/;
const PW_RE = /^[0-9]+$/;

const $ = (id)=>document.getElementById(id);
const msg = (t)=>{$("msg").textContent=t||""};
const already = localStorage.getItem("user_id");
if (already) location.href = "./index.html";

$("btnLogin").addEventListener("click", async ()=>{
  const base = localStorage.getItem("api_base") || DEFAULT_API_BASE;
  const id = $("userId").value.trim();
  const password = $("password").value.trim();

  if (!ID_RE.test(id)) return msg("ID는 영문(A-Z, a-z)만 입력 가능합니다.");
  if (!PW_RE.test(password)) return msg("비밀번호는 숫자(0-9)만 입력 가능합니다.");

  msg("로그인 요청 중...");

  try{
    const res = await fetch(base + "/auth/login", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ id, password })
    });

    const json = await res.json().catch(()=> ({}));
    if (!res.ok){
      return msg(json.detail || ("로그인 실패: HTTP " + res.status));
    }
  }catch{
    return msg("로그인 실패: 네트워크 오류");
  }

  // MVP: user_id 저장(세션/토큰 없음)
  localStorage.setItem("user_id", id);
  localStorage.setItem("api_base", base);

  msg("로그인 성공. 채팅으로 이동합니다.");
  setTimeout(()=> location.href="./index.html", 500);
});
