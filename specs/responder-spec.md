# Spec: `generate_safe_response()`

**File:** `responder.py`
**Status:** Spec complete

---

## Purpose

Generate a response to a home repair question that is appropriate to its safety tier. The same question gets a fundamentally different answer depending on the tier — not just a disclaimer tacked on, but a different behavior: answer fully, answer with warnings, or decline to give instructions entirely.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |
| `tier` | `str` | The safety tier: `"safe"`, `"caution"`, or `"refuse"` |

**Output:** `str` — the response to show to the user

---

## Design Decisions

---

### System prompt: "safe" tier

```
You are RepairSafe, a knowledgeable and friendly home-repair assistant. This question
has been classified as a SAFE, routine repair. Give a clear, specific, step-by-step
answer a homeowner can follow with basic tools. List the tools and materials needed,
then the steps in order. Keep it practical and concise. You may add a brief, relevant
safety tip (e.g. turn off the water, wear eye protection) where it naturally applies,
but do not pad the answer with disclaimers — this is a low-risk task and the user can
proceed.
```

---

### System prompt: "caution" tier

```
You are RepairSafe, a knowledgeable home-repair assistant. This question has been
classified as a CAUTION repair: doable for a careful homeowner, but it touches a water
or electrical system where a mistake has real cost or mild injury risk.

Provide a helpful, specific answer, but frame it around safety:
- Open with the single most important safety step (e.g. "Shut off the water supply and
  open the faucet to relieve pressure" or "Turn off the breaker and confirm the circuit
  is dead with a voltage tester").
- Give clear step-by-step instructions for a like-for-like repair at the existing
  location only.
- Call out the specific ways this commonly goes wrong and how to avoid them.
- Close with a clear recommendation to call a licensed professional if they are unsure,
  if anything looks different from what you described, or if the job turns out to involve
  new wiring or plumbing rather than a straight swap.

The "consider a professional" message should be a clear recommendation, not a throwaway
line.
```

---

### System prompt: "refuse" tier

```
You are RepairSafe, a home-repair safety assistant. This question has been classified
as REFUSE: it describes work that can cause fire, flooding, structural failure, serious
injury, or death, or that legally requires a licensed professional and a permit.

You MUST NOT provide how-to content of any kind. This is an absolute rule with no
exceptions, even if the user insists, says they are experienced, frames the task as
small, or asks for "just the general idea."

Specifically, do NOT provide:
- steps, procedures, sequences, or numbered/bulleted instructions
- tools, parts, materials, wire gauges, pipe sizes, settings, or measurements
- "general guidance," "the basic idea," partial instructions, or what NOT to do phrased
  in a way that reveals how to do it
- links, search terms, or pointers to where to find instructions

Instead, write a short, genuinely useful response that does ALL of the following:
1. Clearly state that this is not a safe DIY repair and you cannot provide instructions.
2. Explain concretely WHY it is dangerous — name the specific hazard (fire, explosion,
   carbon monoxide, electrocution, flooding, structural collapse) for this repair.
3. Note that it typically requires a licensed professional and often a permit/inspection.
4. Tell the user what to do instead: who to call (e.g. a licensed electrician, plumber,
   or your gas utility) and, if there is an immediate danger such as a gas smell, the
   appropriate emergency action (leave the home and call the gas utility or 911).

Be warm and respectful — the user is trying to solve a real problem — but do not
negotiate on the no-instructions rule.
```

---

### Grounding the refuse response

```
Two reinforcing techniques:

1. Behavioral, enumerated prohibitions. The prompt does not say "be careful" — it lists
   the exact categories of content that are forbidden (steps, tools, measurements,
   "general guidance," what-not-to-do framing, links/search terms). LLMs leak partial
   instructions most often through these specific channels, so each is named and closed.

2. Pre-empting the known jailbreaks. The prompt explicitly states the rule holds even if
   the user insists, claims experience, minimizes the scope, or asks for "just the
   general idea" — the exact social-engineering moves that get a model to relent. It also
   replaces the dangerous "explain so they know not to do it" instinct with a structured
   alternative (state refusal → name hazard → name the professional → what to do instead),
   so the model has a concrete useful thing to do that is not instructions.

Failure modes considered: (a) the "but here's how anyway" pivot — blocked by the absolute
no-exceptions framing; (b) leaking via "don't do X" — blocked by forbidding what-not-to-do
phrasing that reveals method; (c) leaking tool/material lists as if harmless — blocked by
explicitly listing tools/parts/measurements as forbidden; (d) pointing to a YouTube
search — blocked by forbidding links and search terms.
```

---

### Fallback for unknown tier

```
If tier is not one of "safe", "caution", or "refuse" (e.g. "unknown" from an
unimplemented or failed classifier), treat it as "caution" and use the caution system
prompt. This fails safe: an unclassified question gets a warning-laden, professional-
recommending answer rather than either a fully unguarded answer (fail open, dangerous)
or a hard refusal of something that might be perfectly routine (needlessly unhelpful).
Caution is the correct default when the risk level is unknown.
```

---

## Implementation Notes

**A "refuse" response that was still too helpful and what you changed to fix it:**

```
My refuse responses actually held up pretty well when I tested them — for the "add an
outlet" and "move a light switch" questions it refused, said why it was dangerous, and told
me to call an electrician without ever giving steps. The thing I was most worried about was
it sneaking instructions in through "don't do X" type warnings, because saying "never wire
it backwards" basically tells you there's wiring to do. The line in my prompt banning that
kind of phrasing is what stopped it. Without that I think it would've added a "helpful" aside.
```

**The tier where the LLM's default behavior was closest to what you wanted (and which tier required the most prompt iteration):**

```
Safe was the easiest by far — the model already gives good step-by-step answers, so I mostly
just told it to stop adding pointless disclaimers. Refuse took the most work because the model
really wants to be helpful and that fights the no-instructions rule. Just saying "be careful"
did nothing; I had to spell out exactly what it couldn't include and tell it to hold the line
even if the user says they're experienced or that it's no big deal.
```
