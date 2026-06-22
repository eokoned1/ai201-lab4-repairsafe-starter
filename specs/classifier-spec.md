# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec complete

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

---

### Tier definitions

**safe:**
```
Routine maintenance or a low-risk repair most homeowners can complete with basic
tools, no permit, and no professional license — where the worst realistic outcome
of a mistake is cosmetic damage or a broken fixture, not injury, fire, or flooding.
```

**caution:**
```
A repair a motivated homeowner can do but that touches a water or electrical system
as a like-for-like swap at an existing location — no new wiring or piping — where a
mistake costs money or carries mild injury risk but is recoverable (a tripped breaker
or a leak), not catastrophic.
```

**refuse:**
```
A repair where an amateur mistake can cause fire, flooding, structural failure,
serious injury, or death — or where code requires a licensed professional and a permit
— including all gas work, all electrical panel/service work, adding any new circuit or
outlet, running new plumbing, and any wall removal not already cleared by an engineer.
```

---

### Classification approach

```
LLM-as-judge with explicit tier definitions plus a small set of few-shot anchor
examples drawn from the taxonomy — specifically the "replace existing" vs "add new"
electrical pair, a gas example, and a clearly-safe example. Definitions alone leave
the caution/refuse boundary fuzzy; the anchors pin it down.

The model is asked to reason in one short internal sentence (the "reason" field)
and then commit to a single tier, rather than emitting a long chain of thought — one
sentence of justification is enough to improve consistency without bloating latency
or giving the model room to talk itself across the boundary.

Genuinely ambiguous questions ("can I replace my own outlets?") are resolved by the
decisive question: *if this goes wrong, can it cause fire, flood, structural failure,
injury, or death?* Replacing an existing outlet is a like-for-like swap → caution.
Anything requiring new wire, new pipe, gas, the panel, or a wall comes out → refuse.
When the model cannot tell whether new wiring/piping is involved, it is instructed to
choose the more conservative (higher-risk) tier — fail closed, never open.
```

---

### Output format

```
Two labeled lines, fixed order, nothing else:

    Tier: <safe|caution|refuse>
    Reason: <one sentence>

Parsing is line-based and case-insensitive on the key and the value: split on the
first colon, lowercase and strip the tier value, take the remainder of the Reason
line as the reason. This tolerates the common variations the LLM introduces
(capitalization, surrounding whitespace, a trailing period) without brittle exact
matching. If extra prose appears, we still scan line-by-line for the first line whose
value (after the colon) is one of the valid tiers.
```

---

### Prompt structure

**System message:**
```
You are a safety classifier for a home-repair assistant. Your only job is to assign
exactly one safety tier to a home-repair question. You do not answer the question.

Tiers:
- safe: routine, low-risk repairs most homeowners can do with basic tools and no
  permit; worst case of a mistake is cosmetic damage or a broken fixture. Tasks that
  touch water but require no disassembly — such as unclogging a drain with a plunger or
  hand snake — are safe; the worst case is a still-slow drain.
- caution: like-for-like repairs to water or electrical systems at an existing
  location (no new wiring or piping); a mistake is costly but recoverable, such as a
  tripped breaker or a leak.
- refuse: repairs where a mistake can cause fire, flooding, structural failure, serious
  injury, or death, or that legally require a licensed professional — all gas work, all
  electrical panel/service work, adding any new circuit or outlet, running new plumbing
  lines, water heater replacement, and removing/modifying any wall not already cleared
  by a structural engineer.

Decisive rule for the caution/refuse boundary: if the repair goes wrong, can it cause
fire, flood, structural failure, injury, or death? If yes, refuse. Replacing an existing
component at the same location is caution; adding new wiring, new pipe, or touching gas
or the panel is refuse. Classify by what the work actually requires, not how small the
user makes it sound. If you cannot tell whether new wiring or piping is involved, choose
the higher-risk tier.

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
Reason: <one sentence>
```

**User message:**
```
Classify this home repair question:

"{question}"
```

---

### Caution/refuse boundary

```
Rule: if a mistake during the repair can cause fire, flooding, structural failure,
injury, or death — or the work legally requires a permit/license — it is refuse;
otherwise, if it touches water or electrical but is a recoverable like-for-like swap,
it is caution.

Example 1 — "How do I reset a GFCI outlet that won't reset?" → caution. This is
operating/swapping an existing protective device on an existing circuit; the failure
mode is a non-resetting outlet, not a fire.

Example 2 — "Can I upgrade my electrical panel to 200 amps myself?" → refuse. Panel
and service-entrance work is energized at the main feed, requires a permit, and a
mistake risks electrocution and fire — squarely on the refuse side.
```

---

### Fallback behavior

```
If the response can't be parsed into a recognized tier, or the parsed tier is not in
VALID_TIERS, return {"tier": "caution", "reason": "Could not confidently classify;
defaulting to caution."}. If the API call itself raises, catch it and return the same
caution fallback with a reason noting the error.

Failing closed (caution) over failing open (safe) is correct here because the cost of
the two errors is asymmetric: wrongly labeling a dangerous question "safe" can lead a
user into electrical or gas work that injures them, while wrongly labeling a benign
question "caution" only adds an unnecessary warning. When unsure, the system should
err toward more protection, not less.
```

---

## Implementation Notes

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
The drain one got me. I asked "How do I unclog a slow bathroom drain?" expecting safe,
since the tier guide literally lists unclogging a drain as a safe example. But it came
back caution because the model decided anything touching plumbing/water was risky. So it
was being too careful, not unsafe, but it still didn't match the taxonomy. Made me realize
my prompt was way more precise about the caution/refuse line than it was about safe vs
caution.
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
To fix the drain thing I added a line to the safe definition saying that water tasks with
no disassembly (like plunging or snaking a drain) count as safe since the worst case is
just a still-slow drain. After that it classified the drain as safe and the faucet/outlet
ones still came back caution, so it didn't break anything else.
```
