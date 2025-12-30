from fastapi import APIRouter
from repos.supabase_repo import upsert_character, upsert_scenario

router = APIRouter(prefix="/dev", tags=["dev"])

@router.post("/seed")
def seed_minimum_data():
    # 캐릭터 2종
    upsert_character(
        id="char_a",
        name="캐릭터 A",
        persona_prompt=(
            "당신은 캐릭터 A입니다. 말투는 간결하고 정중합니다. "
            "사용자 목표 달성을 돕는 코치 역할을 합니다. "
            "모르는 것은 모른다고 말하고, 추측은 구분합니다."
        ),
        is_active=True,
    )
    upsert_character(
        id="char_b",
        name="캐릭터 B",
        persona_prompt=(
            "당신은 캐릭터 B입니다. 말투는 따뜻하고 공감적입니다. "
            "사용자 감정 케어를 우선하며, 짧은 질문으로 맥락을 확인합니다."
        ),
        is_active=True,
    )

    # 시나리오 2종
    upsert_scenario(
        id="scn_qa",
        name="Q&A 기본",
        scenario_prompt="사용자 질문에 정확하고 짧게 답변합니다. 필요 시 추가 질문 1개만 합니다.",
        first_message="안녕하세요. 무엇을 도와드릴까요?",
        is_active=True,
    )
    upsert_scenario(
        id="scn_coach",
        name="코칭",
        scenario_prompt="사용자 목표를 확인하고, 실행 가능한 단계로 쪼개 제안합니다.",
        first_message="안녕하세요. 오늘 어떤 목표를 함께 정리해볼까요?",
        is_active=True,
    )

    return {"ok": True}
