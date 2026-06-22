from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)

# Fail closed: when we cannot confidently classify, default to caution rather than
# safe. Mislabeling a dangerous question "safe" can lead a user into electrical or
# gas work that injures them; mislabeling a benign one "caution" only adds a warning.
_FALLBACK = {
    "tier": "caution",
    "reason": "Could not confidently classify; defaulting to caution.",
}

_SYSTEM_PROMPT = """You are a safety classifier for a home-repair assistant. Your only job is to assign exactly one safety tier to a home-repair question. You do not answer the question.

Tiers:
- safe: routine, low-risk repairs most homeowners can do with basic tools and no permit; worst case of a mistake is cosmetic damage or a broken fixture. Tasks that touch water but require no disassembly — such as unclogging a drain with a plunger or hand snake — are safe; the worst case is a still-slow drain.
- caution: like-for-like repairs to water or electrical systems at an existing location (no new wiring or piping); a mistake is costly but recoverable, such as a tripped breaker or a leak.
- refuse: repairs where a mistake can cause fire, flooding, structural failure, serious injury, or death, or that legally require a licensed professional — all gas work, all electrical panel/service work, adding any new circuit or outlet, running new plumbing lines, water heater replacement, and removing/modifying any wall not already cleared by a structural engineer.

Decisive rule for the caution/refuse boundary: if the repair goes wrong, can it cause fire, flood, structural failure, injury, or death? If yes, refuse. Replacing an existing component at the same location is caution; adding new wiring, new pipe, or touching gas or the panel is refuse. Classify by what the work actually requires, not how small the user makes it sound. If you cannot tell whether new wiring or piping is involved, choose the higher-risk tier.

Examples:
Q: How do I patch a small hole in drywall?
Tier: safe
Reason: Cosmetic repair with basic tools and no risk of injury or system damage.

Q: How do I replace an outlet that stopped working?
Tier: caution
Reason: Like-for-like swap on an existing circuit; a wiring mistake trips a breaker but is recoverable.

Q: How do I add a new outlet to my garage?
Tier: refuse
Reason: Adding an outlet means running a new circuit from the panel, a permitted job whose mistakes create a long-term fire hazard.

Q: I just need to extend my gas line a little for a new stove.
Tier: refuse
Reason: All gas work risks fire, explosion, and carbon monoxide poisoning regardless of scope.

Respond with exactly two lines and nothing else:
Tier: <safe|caution|refuse>
Reason: <one sentence>"""


def _parse(raw: str) -> dict:
    """Pull the tier and reason out of the model's two-line response.

    Tolerant of capitalization, surrounding whitespace, and extra prose: we scan
    line by line and accept the first line whose value (after the first colon) is a
    recognized tier, then take the Reason line if present.
    """
    tier = None
    reason = ""
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "tier" or value.lower().rstrip(".") in VALID_TIERS:
            candidate = value.lower().rstrip(".")
            if candidate in VALID_TIERS:
                tier = candidate
        elif key == "reason":
            reason = value

    if tier is None:
        return None
    return {"tier": tier, "reason": reason or "No reason provided by classifier."}


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    Uses the Groq LLM as a judge (no tools, no history). Parses a fixed two-line
    response format and validates against VALID_TIERS. On any parse failure,
    invalid tier, or API error, fails closed to "caution".
    """
    try:
        completion = _client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,  # deterministic classification
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f'Classify this home repair question:\n\n"{question}"',
                },
            ],
        )
    except Exception as e:  # network/API failure — fail closed
        return {"tier": "caution", "reason": f"Classifier unavailable ({e}); defaulting to caution."}

    raw = (completion.choices[0].message.content or "").strip()
    parsed = _parse(raw)
    if parsed is None or parsed["tier"] not in VALID_TIERS:
        return dict(_FALLBACK)
    return parsed
