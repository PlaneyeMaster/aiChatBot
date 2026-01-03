def build_system_prompt(
    persona_prompt: str,
    scenario_prompt: str,
    story: str | None = None,
    outline: str | None = None,
    goal: str | None = None,
    user_profile: dict | None = None,
    memories: list[str] | None = None,
) -> str:
    parts = []
    if persona_prompt:
        parts.append(f"[Persona]\n{persona_prompt}")

    scenario_parts = []
    if story:
        scenario_parts.append(f"Story: {story}")
    if outline:
        scenario_parts.append(f"Outline: {outline}")
    if goal:
        scenario_parts.append(f"Goal: {goal}")
    if scenario_parts:
        parts.append("[Scenario]\n" + "\n".join(scenario_parts))

    if scenario_prompt:
        parts.append("[Flow Rules]\n" + scenario_prompt)

    if user_profile:
        parts.append("[User Profile]")
        for k in ["tone", "goal", "expertise", "age_band"]:
            v = user_profile.get(k)
            if v:
                parts.append(f"- {k}: {v}")
    if memories:
        parts.append("[Personal Memory]\n" + "\n".join([f"- {m}" for m in memories]))

    return "\n\n".join(parts).strip()
