# Pitfalls Research

**Domain:** Executive summaries about AI-assisted development (stakeholder/management audience)
**Researched:** 2026-03-02
**Confidence:** MEDIUM — based on established technical writing principles and knowledge of stakeholder communication patterns; web search unavailable, no contradictory sources to resolve

---

## Critical Pitfalls

### Pitfall 1: Unverifiable or Inflated Productivity Claims

**What goes wrong:**
The document makes headline claims like "10x faster" or "saved 6 months of work" without grounding them in specifics. Stakeholders who scrutinize the numbers cannot validate them, and skeptical readers dismiss the whole document as marketing.

**Why it happens:**
Authors reach for dramatic framing to make impact feel tangible. Productivity comparisons are genuinely hard to make (counterfactual: how long would this have taken without AI?), so vague multiples fill the gap. The real data — 113 commits, ~23k lines of new source, 16 to 56 source files, 29 terminal types — is impressive on its own and does not need inflation.

**How to avoid:**
Anchor every claim in a specific, verifiable fact from the repository. "113 commits over ~2 weeks by one developer" is verifiable. "Equivalent to 6 months of traditional development" is not. Where comparison is attempted, make the reasoning explicit: "A conservative estimate for hand-authoring 14,276 lines of YAML plus the associated Python would be..." — and show the reasoning, not just the conclusion.

**Warning signs:**
- Any sentence with "X times faster" that does not reference a specific baseline measurement
- Claims framed as certainties when they are estimates ("this saved N months")
- Numbers that appear only in the summary paragraph and do not trace back to git history or file counts

**Phase to address:**
Drafting phase — establish a facts-first constraint before writing prose. Every claim must link to a concrete artifact (commit count, file count, line count, terminal count).

---

### Pitfall 2: Treating AI as the Hero Instead of the Developer

**What goes wrong:**
The narrative frames Claude as the agent that delivered the work, sidelining the developer's judgment, direction, and verification. This reads as either naive (the AI "just did it") or as undermining the developer's skill contribution. Technically informed stakeholders will question whether unreviewed AI output is safe in production systems.

**Why it happens:**
Advocacy framing tempts writers to emphasise the tool rather than the outcome. AI tools are novel and generate curiosity, so they attract disproportionate attention in the narrative.

**How to avoid:**
Frame AI as a force-multiplier under human direction. The developer (Giles Knap) made all architectural decisions, validated outputs, and maintained quality. Claude accelerated implementation. An analogy: a compiler makes a programmer faster; we do not say the compiler "wrote" the software. The document should follow this logic: "The developer directed, Claude executed at scale."

**Warning signs:**
- Passive constructions that omit the developer's agency ("the code was generated," "the architecture emerged")
- Any claim that AI made architectural decisions rather than the developer
- Absence of any acknowledgement of the developer's review or oversight role

**Phase to address:**
Drafting phase — review every sentence for subject and agency. The developer should be the grammatical subject of decisions; Claude should be the subject of execution tasks.

---

### Pitfall 3: Failing to Acknowledge Limitations and Context

**What goes wrong:**
The document presents AI-assisted development as universally applicable without noting the conditions under which it succeeded here. Stakeholders who attempt to replicate the approach in a different context are set up for disappointment, which damages the credibility of the original claims retrospectively.

**Why it happens:**
Advocacy tone tempts authors to omit caveats that might weaken the case. However, honest framing of scope and conditions actually strengthens credibility.

**How to avoid:**
Explicitly note that this work predates structured agent workflows and relied on a developer with deep domain knowledge of the EtherCAT/TwinCAT/ADS stack. The document already plans to reference builder2ibek as a more mature example — use that contrast to frame the evolution rather than claiming the approach is complete. State what was not done with AI (test infrastructure, documentation), which shows the developer exercised selective judgment.

**Warning signs:**
- No mention of the developer's pre-existing domain expertise
- No acknowledgement of what AI was not used for (tests, doc cleanup)
- Absence of any "lessons learned" or "what we'd do differently" framing
- builder2ibek referenced only as a positive example with no contrast

**Phase to address:**
Drafting phase — add a short "Scope and Conditions" section or integrate caveats into the "what we learned" framing.

---

### Pitfall 4: Confusing Quantity Metrics with Quality Evidence

**What goes wrong:**
The document leads with scale metrics (23k lines, 113 commits, 56 source files) without demonstrating that the output is correct, maintainable, and production-ready. Sophisticated stakeholders know that large quantities of AI-generated code can be low quality. If quality evidence is absent, the scale metrics backfire and raise concerns.

**Why it happens:**
Scale is easy to measure from git; quality is harder to articulate. Authors default to what is measurable.

**How to avoid:**
Pair each scale metric with a quality indicator. Examples:
- "113 commits" paired with "the test suite covers N scenarios including a full ADS simulator"
- "29 terminal types in YAML" paired with "these definitions were validated against Beckhoff's official ESI XML"
- "56 source files" paired with "the architecture is documented in five explanation pages now part of the project's Sphinx docs"

The before/after architecture comparison (hard-coded Python classes vs YAML-driven dynamic controllers) is itself quality evidence — use it explicitly.

**Warning signs:**
- Scale metrics in the introduction with no quality follow-through anywhere in the document
- Absence of any mention of testing, validation, or review processes
- No before/after architecture comparison even though the PROJECT.md specifies it as a requirement

**Phase to address:**
Drafting phase — for each quantity claim, ask: "What does this prove about quality?" If the answer is nothing, add a paired quality claim or reorder the evidence.

---

### Pitfall 5: Over-Claiming Generalisability from a Single Case

**What goes wrong:**
The document implies that one successful project proves AI-assisted development works broadly. Stakeholders with skeptical inclinations will note that a single anecdote is not evidence of a systematic effect, and this weakens the advocacy case.

**Why it happens:**
The author has strong evidence from one project and naturally wants that to speak broadly. The temptation is to generalise without flagging the limitation.

**How to avoid:**
Frame the document as reporting evidence, not proving a universal claim. "This project demonstrates that a single developer with AI assistance can deliver architectural changes of this scale and quality in two weeks. The more structured workflows now in use (see builder2ibek) suggest this is reproducible and improvable." This is honest and still advocates — it positions the work as evidence in an ongoing trajectory rather than a closed proof.

**Warning signs:**
- Language like "AI-assisted development enables..." (universal claim) rather than "this project shows..." (evidential claim)
- No acknowledgement that conditions (domain expertise, clear requirements, experienced developer) contributed to success

**Phase to address:**
Review/revision phase — check the conclusion and abstract for universal claims and reframe as evidential claims.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Writing the summary without reading the commit history | Faster first draft | Claims not grounded in verifiable specifics; credibility risk if challenged | Never — the git history is the primary evidence base |
| Omitting caveats about AI limitations | Stronger-sounding advocacy | Backlash when readers identify the omissions; sets unrealistic expectations | Never for a stakeholder document |
| Reusing commit count as the primary metric | Easy to state | Commits vary enormously in scope; a commit could be one line or one thousand | Only as a secondary metric, never the headline |
| Deferring the before/after architecture comparison | Shorter document | The comparison is the strongest structural argument; without it the scale numbers are unsupported | Never — PROJECT.md already requires it |

---

## Integration Gotchas

These apply to the integration of the executive summary into the Sphinx documentation system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| MyST/Sphinx format | Using GitHub-flavoured Markdown features (collapsible sections, GitHub alerts) that do not render in Sphinx | Check existing explanation pages for the subset of Markdown features CATio's Sphinx build supports |
| Cross-references | Using bare URLs to source files instead of Sphinx cross-reference directives | Use `` {ref} `` and doc directives for internal links; check how `architecture-overview.md` handles its "See Also" section |
| Mermaid diagrams | Including a complex diagram the Sphinx build does not have the mermaid extension configured for | Verify mermaid renders in the current build before adding new diagrams; fallback is a text-based architecture description |
| builder2ibek references | Linking to builder2ibek's repo or docs without checking the link is stable and accessible to the target audience | Confirm the URL is public and that it represents the intended "more mature example" |

---

## "Looks Done But Isn't" Checklist

- [ ] **Before/after architecture comparison:** Often drafted as a vague assertion — verify that the comparison explicitly names what changed (hard-coded Python classes in catio_hardware.py → YAML-driven dynamic controllers) with specifics
- [ ] **Quantified scale of changes:** Often only commit count is listed — verify that all four metrics from PROJECT.md are present (113 commits, ~23k lines new source, 16 to 56 source files, 29 terminal types in YAML)
- [ ] **Quality evidence paired with scale:** Often a draft reads as pure quantity — verify that each scale claim is paired with at least one quality indicator (test coverage, architecture docs, validation against Beckhoff XML)
- [ ] **Attribution clarity:** Often passive voice obscures who made decisions — verify that the developer's role in directing AI is explicit throughout
- [ ] **builder2ibek reference:** Often mentioned as a footnote — verify it is integrated into the narrative as a forward-looking trajectory, not just a link dump
- [ ] **MyST format compliance:** Often written in isolation — verify it renders correctly in the Sphinx build alongside existing explanation pages

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Inflated productivity claims identified after stakeholder review | MEDIUM | Return to git history, replace vague multiples with specific measurements, restate comparison with explicit reasoning |
| Developer agency absent from draft | LOW | Find all passive constructions about AI generating/creating code; rewrite with developer as subject and AI as tool |
| Quality evidence absent | MEDIUM | Survey test suite, architecture docs, and YAML validation process; add a "Quality and Validation" subsection |
| Format incompatible with Sphinx | LOW | Test render locally; replace non-supported syntax with supported equivalents from existing explanation pages |
| builder2ibek reference broken or inaccessible | LOW | Verify URL, add fallback description that does not depend on the link |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Unverifiable productivity claims | Drafting — facts-first constraint | Every claim traces to a specific git artifact or file count |
| AI treated as hero instead of developer | Drafting — agency review | Developer is grammatical subject of all decision sentences |
| Limitations not acknowledged | Drafting — scope framing | Document includes explicit "conditions for success" or equivalent |
| Quantity without quality evidence | Drafting — paired evidence rule | Each scale metric has a corresponding quality indicator |
| Over-generalisation from single case | Revision — language audit | Conclusion uses evidential language, not universal claims |
| Sphinx/MyST format issues | Finalisation — local render test | Document renders cleanly alongside existing explanation pages |

---

## Sources

- Project context: `.planning/PROJECT.md` — requirements and constraints for the executive summary
- Existing docs: `docs/explanations/architecture-overview.md` — establishes the technical baseline and the before/after story
- Existing docs: `docs/explanations/fastcs-epics-ioc.md` and `terminal-yaml-definitions.md` — inform what claims about the architecture are verifiable
- Technical writing principles: Established practice for credibility in stakeholder documents (training data, MEDIUM confidence — no external sources available)
- AI-assisted development communication: Common patterns in post-mortems and retrospectives for AI-aided engineering projects (training data, MEDIUM confidence — no external sources verified)

---
*Pitfalls research for: executive summaries about AI-assisted development*
*Researched: 2026-03-02*
