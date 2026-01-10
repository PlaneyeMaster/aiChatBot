const DEFAULT_API_BASE = "https://aichatbot-ez4g.onrender.com";
const ID_RE = /^[A-Za-z]+$/;
const PW_RE = /^[0-9]+$/;

const $ = (id)=>document.getElementById(id);
const msg = (t)=>{$("msg").textContent=t||""};
const userId = localStorage.getItem("user_id");
if (userId && document.getElementById("userId")) {
  document.getElementById("userId").value = userId;
}

$("btnSignup").addEventListener("click", async ()=>{
  const base = localStorage.getItem("api_base") || DEFAULT_API_BASE;
  const id = $("userId").value.trim();
  const password = $("password").value.trim();

  if (!ID_RE.test(id)) return msg("ID는 영문(A-Z, a-z)만 입력 가능합니다.");
  if (!PW_RE.test(password)) return msg("비밀번호는 숫자(0-9)만 입력 가능합니다.");

  msg("가입 요청 중...");

  const res = await fetch(base + "/auth/signup", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ id, password })
  });

  const json = await res.json().catch(()=> ({}));
  if (!res.ok){
    return msg(json.detail || ("가입 실패: HTTP " + res.status));
  }

  msg("가입 성공. 로그인 페이지로 이동합니다.");
  setTimeout(()=> location.href="./login.html", 700);
});
