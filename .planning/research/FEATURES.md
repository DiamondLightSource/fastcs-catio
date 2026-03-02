# Feature Research

**Domain:** Executive summary document — AI-assisted software development advocacy
**Researched:** 2026-03-02
**Confidence:** MEDIUM

## Context

This document's "features" are content sections and rhetorical elements. The product is a Sphinx
explanation page targeting management and stakeholders. The research question is: what content does
this kind of document need to be credible (table stakes) and what makes it compelling
(differentiators)?

Research method: Analysed the actual CATio development evidence (commits, code diffs, before/after
architecture), examined the existing Sphinx explanation pages for format patterns, and applied
understanding of what management audiences require when making investment decisions about AI tooling.

No web search was available during research. Confidence is MEDIUM because findings draw on
established patterns in technical advocacy documents rather than a current literature survey.

## Feature Landscape

### Table Stakes (Readers Expect These)

Features that any credible AI development case study must include. Missing these = the document
lacks credibility and readers dismiss it as anecdote.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Concrete numbers | Stakeholders cannot evaluate "significant improvement" without scale; numbers like line counts, commit counts, and timeline give the claim weight | LOW | Available: 113 commits, ~3 weeks, 14,276-line YAML, 30+ new source files, 146 files changed, 35,406 insertions |
| Before/after comparison | Without the "before" state, the "after" has no context; readers need to understand what problem existed | MEDIUM | Before: 1,199-line catio_hardware.py with 20 explicit Python classes covering ~20 terminal types. After: 29 terminal types in YAML, dynamic generation, no manual class writing |
| Description of what changed architecturally | The summary must describe the key architectural transformation, not just that code was written; readers need to understand what was built | MEDIUM | YAML-driven dynamic controller generation replaced hand-coded Python classes; catio-terminals NiceGUI application added |
| Where AI was used | Readers want to know specifically what role AI played — code generation? refactoring? architecture? — not a vague "we used AI" | MEDIUM | Evidence: commit "Generate and refine Architecture Docs with Claude"; refactoring into smaller modules; dynamic controller pattern development |
| Time investment statement | A single developer in two weeks is the core claim; it must be stated explicitly with a timeframe | LOW | Available: Jan 13–Feb 5 2026, approximately three weeks of commits by Giles Knap |
| Honest scope of AI involvement | Claiming AI did everything undermines trust; acknowledging where the developer drove decisions and where AI assisted is more credible | LOW | The work predates GSD workflows and structured agent features; Claude was used as a pair programmer, not autonomous agent |

### Differentiators (Competitive Advantage)

Content choices that elevate this from "we tried AI" to "you should adopt AI." These are the
elements that make the case compelling rather than merely informative.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Trajectory arc (from ad-hoc to structured) | Showing that the team has continued to improve AI usage — not just a one-off experiment — demonstrates institutional learning and makes future ROI credible | MEDIUM | This work was pre-GSD, pre-agent-skills; builder2ibek represents more mature usage; presenting this arc shows progression |
| Reference to builder2ibek as maturity example | Gives readers a concrete next step to examine; avoids the document looking like a single data point; shows ongoing commitment | LOW | builder2ibek is a sibling project built with proper agent features, structured workflows, and agent skills |
| Specific AI tasks (not just "we used Claude") | Naming specific tasks — module decomposition, architecture documentation generation, refactoring, symbol handling — lets readers understand what kinds of work AI accelerates | HIGH | Need to be specific without inventing details; evidence available in commit messages and the shape of the code changes |
| Scale translation to team-equivalent effort | Estimating that the same work would typically require N developers or M months gives management a cost-benefit frame | MEDIUM | This is an inference, not a measured claim; must be framed as estimate, not assertion. LOW confidence — flag for author validation |
| Quality observation, not just speed | If the resulting code is well-structured and maintainable, that matters; speed without quality regression is the credible combination | MEDIUM | Evidence: the dynamic controller architecture is more flexible and maintainable than the hardcoded class approach; refactoring into smaller modules happened |
| Acknowledgement of limitations | Stating what AI was NOT good at — or where human judgment was essential — makes the advocacy more credible than uncritical boosterism | MEDIUM | Author must provide this; examples might include: architecture decisions, domain knowledge of EtherCAT/TwinCAT, deciding which terminal symbols matter |
| Sphinx/MyST formatting that matches the house style | For this audience (DLS), the document lives alongside technical architecture docs; matching the format signals that this is substantive documentation, not a marketing insert | LOW | Existing pages use: H1 title, prose sections, mermaid diagrams where useful, tables, bullet lists. No emojis. No "hero" marketing language |

### Anti-Features (Commonly Requested, Often Problematic)

Content choices that seem helpful but undermine the document's purpose.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Step-by-step AI usage tutorial | "Show us exactly how to do it" is a natural follow-on | This is explicitly out of scope (PROJECT.md); it changes the audience and tone from executive summary to how-to guide; buries the advocacy message | A brief "how AI was used" paragraph is sufficient; link to tooling docs elsewhere if needed |
| Detailed code examples | Developers want to see the actual code | Management audience does not; detailed code shifts the document from accessible to technical; it belongs in how-to or reference docs | Reference architecture diagram, keep code mentions at the pattern level (e.g., "dynamic class generation") not the implementation level |
| AI performance benchmarks or accuracy metrics | "How good was Claude?" is a reasonable question | CATio data doesn't support this claim; manufactured metrics are worse than no metrics; LLM benchmarks are also context-dependent and often misleading | Use the concrete outcome metrics (scale, timeline, architecture quality) instead |
| Coverage of test/doc commits | Feels comprehensive to include everything | Dilutes the architecture story; test infrastructure and documentation cleanup are harder to attribute to AI in a compelling way; PROJECT.md explicitly excludes this | Focus on the four substantive architectural changes: dynamic controllers, YAML definitions, catio-terminals GUI, module decomposition |
| Criticism of the "old way" | Contrast helps the story | Stakeholders who commissioned the old approach may be in the room; framing as "problem/solution" is better than "bad/good" | Frame as "the architecture before the constraints that drove the change" rather than "the old approach was wrong" |
| Unqualified productivity claims | "10x faster" is tempting | Without a controlled comparison, such claims are unverifiable and damage credibility if challenged | Use qualified framing: "a single developer delivered in three weeks what typically requires..." and note this is an estimate |
| Claiming Claude wrote all the code | Simplifies the story | Inaccurate — Giles drove architecture decisions, reviewed output, chose what to keep; misrepresenting AI contribution undermines trust when readers ask follow-up questions | "Claude was used to accelerate implementation of patterns the developer designed" |

## Feature Dependencies

```
[Concrete numbers] ──enables──> [Before/after comparison]
    (numbers need to be chosen before the comparison can be framed)

[Before/after comparison]
    └──requires──> [Description of architectural change]
                       └──enhances──> [Where AI was used]

[Trajectory arc]
    └──requires──> [Reference to builder2ibek]
                       (the arc needs an endpoint to be meaningful)

[Specific AI tasks] ──enhances──> [Where AI was used]
    (specifics make the general claim credible)

[Acknowledgement of limitations] ──enhances──> [Scale translation]
    (limiting the claim makes the positive claim more credible)
```

### Dependency Notes

- **Concrete numbers requires verification by author:** The PROJECT.md states 113 commits and ~23k lines new source; git evidence shows 114 Giles commits and 35,406 insertions total (including tests, docs, config). Author should confirm which set of numbers to use and how to scope them (architecture-only vs all work).
- **Scale translation requires author input:** Only the author (Giles Knap) can estimate what the equivalent team effort would have been; the document should not manufacture this figure.
- **Trajectory arc requires builder2ibek description:** The arc is inert without a concrete description of what "more mature" AI usage looks like in builder2ibek; at minimum, a sentence identifying what features that project uses.

## MVP Definition

### Launch With (v1)

Minimum content for a credible executive summary.

- [ ] **Context paragraph** — What is CATio, what was the goal, why did it need changing; establishes stakes for non-technical readers
- [ ] **Scale of changes** — Concrete numbers (commits, timeline, lines, file counts, terminal types); the anchor for all claims
- [ ] **Before/after architectural comparison** — Hard-coded Python classes vs YAML-driven dynamic generation; this is the core claim
- [ ] **Where AI was used** — Specific tasks: architecture docs, refactoring, module decomposition, symbol handling, controller generation pattern; avoids vagueness
- [ ] **Honest framing of AI role** — "Pair programmer" not "autonomous agent"; pre-GSD context acknowledged
- [ ] **Advocacy conclusion** — Clear recommendation that AI-assisted development is worth adopting; without this, the document is neutral rather than advocacy

### Add After Validation (v1.x)

Features to add after the core document is reviewed by stakeholders.

- [ ] **Trajectory arc + builder2ibek reference** — Once the core story lands, the "we've continued improving" angle reinforces the conclusion; needs builder2ibek context to be useful
- [ ] **Limitations acknowledgement** — Strengthens credibility; best positioned after the positive case is established so it reads as honesty rather than hedging

### Future Consideration (v2+)

Features to defer; may not be needed if the v1 achieves its goal.

- [ ] **Scale-to-team-equivalent estimate** — Useful if stakeholders push back; requires the author to commit to a specific claim and be prepared to defend it
- [ ] **Mermaid before/after architecture diagram** — Visual comparison would help; medium complexity; defer unless text comparison proves insufficient

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Concrete numbers | HIGH | LOW | P1 |
| Before/after architectural comparison | HIGH | MEDIUM | P1 |
| Context paragraph | HIGH | LOW | P1 |
| Where AI was used (specific) | HIGH | MEDIUM | P1 |
| Honest framing of AI role | HIGH | LOW | P1 |
| Advocacy conclusion | HIGH | LOW | P1 |
| Trajectory arc + builder2ibek | MEDIUM | LOW | P2 |
| Acknowledgement of limitations | MEDIUM | LOW | P2 |
| Scale-to-team-equivalent estimate | MEDIUM | HIGH | P3 |
| Before/after architecture diagram | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

Comparable documents in this domain are internal AI adoption reports, case studies from research
institutions, and developer advocacy posts from AI tool vendors. This project is a Sphinx
documentation page, which constrains format more than most.

| Feature | Academic case study | Vendor advocacy post | Our Approach |
|---------|--------------|--------------|--------------|
| Concrete metrics | Always present, peer-reviewed | Often present, sometimes inflated | Use verified git data; scope clearly |
| Before/after comparison | Standard | Sometimes omitted | Include; it's the core claim |
| Limitations | Required for credibility | Often absent or minimised | Include; builds trust with technical readers in the room |
| Code examples | Common | Common | Exclude per PROJECT.md (wrong audience) |
| Future trajectory | Rarely | Common (vendor interest) | Include; shows institutional learning |
| Tone | Neutral | Advocacy | Advocacy (matches PROJECT.md intent) |

## Sources

- PROJECT.md: project context, requirements, constraints, audience definition
- Git log (df5c3c4..HEAD): commit counts, timeline, author breakdown (114 Giles, 11 copilot-swe-agent, 2 Gregory Gay)
- `git show df5c3c4:src/catio/catio_hardware.py`: 1,199-line file with 20 explicit Python terminal classes — establishes "before" state
- `git diff df5c3c4..HEAD --stat`: 146 files changed, 35,406 insertions, 1,839 deletions; src/catio_terminals/ entirely new; 48 Python source files changed
- `docs/explanations/architecture-overview.md`: Mermaid diagrams, section headings, tone — establishes house format style
- Existing explanation pages: ads-client.md, fastcs-epics-ioc.md, terminal-yaml-definitions.md — format reference

---
*Feature research for: Executive summary — AI-assisted development advocacy*
*Researched: 2026-03-02*
