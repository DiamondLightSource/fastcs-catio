# Project Research Summary

**Project:** AI-Assisted Development Executive Summary — CATio/fastcs-catio
**Domain:** Technical advocacy documentation (Sphinx/MyST explanation page)
**Researched:** 2026-03-02
**Confidence:** MEDIUM

## Executive Summary

The deliverable is a single Sphinx/MyST explanation page in `docs/explanations/` that makes the case to management and stakeholders for AI-assisted development, using the CATio architectural transformation as a concrete case study. This is not a software engineering project in the conventional sense — it is a persuasion document with a specific rhetorical architecture: hook, before-state, quantified evidence, mechanism, after-state, trajectory. The recommended approach is to lead with the outcome (one developer, ~2–3 weeks, architectural transformation of significant scale), present the hard numbers prominently in a table, and follow with an honest account of how AI was used and where human judgment was essential. The infrastructure needed to write and publish this page is entirely in place — no new dependencies, no new tools.

The primary evidence base is already fully verified: 113 commits, approximately 23,000 new source lines, source files growing from 16 to 56, 29 terminal types defined in YAML (14,276 lines), and a codebase that moved from hard-coded Python classes (~1,200 lines per terminal family in `catio_hardware.py`) to YAML-driven dynamic controller generation. All of these figures are accessible from the git history and `PROJECT.md`. The document does not need to generate or infer new metrics — it needs to structure existing evidence into a credible argument.

The principal risk is credibility damage from one of three failure modes: inflating claims beyond what the repository evidence supports, framing the AI as the agent that "did" the work rather than the developer who directed it, or failing to qualify scale metrics with quality evidence. All three risks are fully addressable in the drafting phase and are not architectural problems — they are discipline problems. A secondary risk is Sphinx/MyST format non-compliance (the document must render cleanly alongside the existing explanation pages with `--fail-on-warning`), which is low-risk given that the house format is well-established and the build tooling is already configured.

## Key Findings

### Recommended Stack

The documentation stack is already fully configured. The project uses Sphinx with pydata-sphinx-theme, MyST Markdown via myst-parser (with `colon_fence` enabled for `:::` admonitions), sphinxcontrib-mermaid (with `mermaid_output_format = "raw"`), and sphinx-design (for grid cards and badges). All of these are present in `pyproject.toml` and in active use in other explanation pages. The correct output format is `docs/explanations/ai-assisted-development.md` added to the existing toctree. No setup work is required.

The content "stack" — the structural components the page needs — is also well-defined by the research: a quantified metrics section, a before/after comparison (table format), an account of how AI was used, and a trajectory section referencing builder2ibek as a more mature example. The live preview tool (`tox -e docs-autobuild`) and full build validation (`tox -e docs`) are already configured.

**Core technologies:**
- MyST Markdown: page authoring format — already used by all explanation pages, zero setup
- Sphinx + pydata-sphinx-theme: documentation engine and visual presentation — already configured and deployed
- sphinxcontrib-mermaid: architecture diagrams — already configured, usable without mmdc
- sphinx-design: callout boxes, metric highlights — already enabled

### Expected Features

Research draws a clear line between content that is required for credibility (table stakes) and content that strengthens the case (differentiators). The MVP for a credible AI development case study is well-defined.

**Must have (table stakes):**
- Concrete numbers — 113 commits, ~23k new source lines, 16 to 56 source files, 29 terminal types; without these the claims are unverifiable anecdote
- Before/after architectural comparison — hard-coded Python classes in `catio_hardware.py` vs YAML-driven dynamic controller generation; this is the core argument
- Context paragraph — what CATio does and why the architecture change mattered; orients non-technical readers
- Where AI was used (specific tasks) — architecture docs, refactoring, module decomposition, symbol handling; avoids vagueness
- Honest framing of AI role — "pair programmer under developer direction" not "autonomous agent"; prevents credibility loss with technical readers
- Advocacy conclusion — clear recommendation to adopt AI-assisted development; without it the document is neutral, not advocacy

**Should have (differentiators):**
- Trajectory arc + builder2ibek reference — shows institutional learning, not a one-off experiment; positions the approach as ongoing and maturing
- Acknowledgement of limitations — what AI was not used for, where developer domain knowledge was essential; counterintuitively strengthens the advocacy case

**Defer (v2+):**
- Scale-to-team-equivalent estimate — requires author to commit to a specific comparative claim and defend it; high risk of sounding like marketing
- Before/after Mermaid architecture diagram — useful visual, but the before/after table may be sufficient; defer unless text comparison proves insufficient after stakeholder review

### Architecture Approach

The document follows a persuasion architecture: each section builds on the previous to move the reader from context to evidence to conclusion. The section order is non-negotiable — it is determined by rhetorical dependency (the before-state must precede the evidence so that the evidence is meaningful; the mechanism must follow the evidence so that the AI-use claim is grounded rather than speculative). The writing order differs from the reading order: write the metrics table first (all other sections reference it), then the before-state, then the after-state, then the mechanism, then the introduction, then the trajectory close.

**Major sections (in reading order):**
1. Introduction paragraph — orients the reader; must stand alone for scan readers
2. The Challenge — before-state, establishes what problem was solved
3. The Transformation — quantified metrics table at the centre; all key numbers here
4. How AI Assistance Enabled This — mechanism, specific tasks, pre-GSD context acknowledged
5. Architecture Impact — before/after comparison table; links to technical docs for depth
6. What This Means Going Forward — builder2ibek reference, advocacy close

### Critical Pitfalls

1. **Inflated or unverifiable productivity claims** — anchor every claim to a verifiable git artifact (commit count, file count, line count, terminal count); "113 commits by one developer in ~2 weeks" is verifiable; "equivalent to N months of traditional development" is not unless the reasoning is shown explicitly
2. **Framing AI as the agent, developer as passive** — the developer (Giles Knap) made all architectural decisions and validated all outputs; Claude executed at scale under direction; review every sentence for subject and agency; the developer should be the grammatical subject of all decision sentences
3. **Scale metrics without quality evidence** — pair each scale metric with a quality indicator (e.g., "113 commits" + "test suite includes full ADS simulator"; "29 terminal types in YAML" + "validated against Beckhoff ESI XML"); the before/after architecture comparison is itself quality evidence
4. **Failing to acknowledge limitations and conditions** — state what predates structured workflows, what AI was not used for, and that the developer's pre-existing domain expertise was essential; this framing increases credibility rather than undermining it
5. **Over-generalising from a single case** — use evidential language throughout: "this project demonstrates..." not "AI-assisted development enables..."; the trajectory arc (builder2ibek) partially addresses this by showing the approach is reproducible

## Implications for Roadmap

Based on research, the document has a clear sequential writing dependency chain. Three phases are suggested.

### Phase 1: Evidence Verification and Metrics Baseline

**Rationale:** All writing depends on having verified, agreed numbers. Write the metrics table first and confirm the figures with the author (Giles Knap) before any prose is drafted. This avoids rework if numbers are disputed or scoped differently (e.g., architecture-only vs. all commits including tests and docs).

**Delivers:** A verified, agreed metrics table that all subsequent prose references. Author sign-off on which numbers to use and how to scope them (e.g., 113 commits vs. 114; ~23k new source lines vs. 35,406 total insertions). Author input on the scale-to-team-equivalent estimate (if included) and the builder2ibek trajectory context.

**Addresses:** "Concrete numbers" (P1 feature); prevents the Pitfall 1 failure mode (unverifiable claims). Author must also provide: acknowledgement of AI limitations, builder2ibek description for the trajectory close.

**Avoids:** The "writing summary without reading commit history" technical debt pattern identified in PITFALLS.md.

### Phase 2: Core Document Drafting

**Rationale:** With metrics verified, draft all six sections in writing-dependency order (metrics table → before-state → after-state → mechanism → introduction → trajectory). The architecture research specifies this order explicitly because introduction cannot be written well until all other sections exist.

**Delivers:** A complete draft of `docs/explanations/ai-assisted-development.md` with all P1 features present: context paragraph, scale of changes, before/after architectural comparison, where AI was used, honest framing of AI role, advocacy conclusion.

**Uses:** MyST Markdown in the house style established by existing explanation pages; no new format features needed. The before/after comparison uses a table (Pattern 2 from ARCHITECTURE.md). Metrics use a table block (Pattern 3). Each paragraph in the evidence sections uses the Claim-Evidence-Implication pattern (Pattern 1).

**Implements:** All six document sections. Applies the five anti-pattern avoidance rules: lead with achievement not process; show impact not task list; metrics in a table not buried in prose; architecture diagram not code; clear advocacy conclusion.

**Avoids:** Pitfalls 2 (AI as hero), 3 (no limitations), 4 (quantity without quality).

### Phase 3: Validation, Revision, and Integration

**Rationale:** After drafting, two categories of review are needed: language audit (check universal claims, check agency, check limitation acknowledgements) and technical validation (Sphinx build, format compliance, cross-reference correctness). These must happen after drafting, not during, to avoid premature optimisation.

**Delivers:** A document that renders cleanly in the existing Sphinx build, passes `tox -e docs` with `--fail-on-warning`, is compliant with MyST house style, and has been reviewed for evidential language (vs. universal claims) and developer agency (vs. passive AI-hero framing). P2 features (trajectory arc, limitations acknowledgement) finalized. builder2ibek reference verified as accessible.

**Avoids:** Pitfall 5 (over-generalisation); Sphinx/MyST format integration gotchas (GitHub-flavoured Markdown features, non-supported cross-reference syntax, unverified Mermaid rendering).

### Phase Ordering Rationale

- Phase 1 must precede Phase 2: prose cannot be written accurately without agreed numbers; author input cannot be retrofitted without rework
- Phase 2 must precede Phase 3: language audit requires the full draft to exist; Sphinx build validation requires a draft to render
- The writing-dependency order within Phase 2 (metrics table first, introduction last) is specified by ARCHITECTURE.md and reflects rhetorical dependencies within the document itself

### Research Flags

Phases needing deeper research or author input during planning:
- **Phase 1:** Author (Giles Knap) must confirm: (a) which commit and line count figures to use, (b) whether the scale-to-team-equivalent estimate is included and what the number is, (c) what the builder2ibek trajectory description should say, (d) which limitations to acknowledge
- **Phase 2:** The "How AI Assistance Enabled This" section requires the author's retrospective account of specific tasks — this cannot be accurately drafted from the commit history alone without risking misattribution

Phases with standard patterns where research is not needed:
- **Phase 3:** Sphinx build validation, MyST format compliance, and language audit are standard review steps with clear checklists already defined in PITFALLS.md; no additional research required

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified directly in `pyproject.toml`, `conf.py`, and existing explanation pages; no inference required |
| Features | MEDIUM | MVP content list is well-grounded in project evidence and established advocacy document patterns; web search unavailable to verify against current external practice |
| Architecture | HIGH | Document section structure and rhetorical patterns are derived from first principles of persuasion architecture; verified against existing explanation pages for format; writing-order dependency chain is directly extractable from the content relationships |
| Pitfalls | MEDIUM | All five critical pitfalls are grounded in project-specific evidence and established technical writing principles; web search unavailable to verify against recent AI advocacy document failures |

**Overall confidence:** MEDIUM-HIGH. The infrastructure and evidence base are fully verified (HIGH). The content and rhetorical recommendations are well-grounded but draw on training knowledge rather than current external sources (MEDIUM). No decisions here require LOW-confidence information.

### Gaps to Address

- **Author input required before drafting:** The metrics scoping decision (architecture-only vs. all work), the scale-to-team-equivalent estimate (if included), the builder2ibek trajectory description, and the limitations acknowledgement all require input from Giles Knap and cannot be derived from the repository alone.
- **Mermaid diagram decision:** The before/after architecture diagram is deferred to v2+ but should be revisited after the text comparison table is drafted; if stakeholders or reviewers find the text comparison insufficient, the Mermaid diagram moves to Phase 2.
- **builder2ibek accessibility:** The builder2ibek reference must be verified as accessible to the target audience (DLS management/stakeholders) before the document is published; if it is not publicly accessible, the trajectory section must be rewritten to describe the project without linking to it.

## Sources

### Primary (HIGH confidence)
- `/scratch/hgv27681/work/fastcs-catio/.planning/PROJECT.md` — project requirements, audience definition, known metrics, constraints
- `/scratch/hgv27681/work/fastcs-catio/docs/conf.py` — Sphinx configuration, verified extensions
- `/scratch/hgv27681/work/fastcs-catio/docs/explanations/` — existing explanation page house format (architecture-overview.md, ads-client.md, fastcs-epics-ioc.md, terminal-yaml-definitions.md)
- `/scratch/hgv27681/work/fastcs-catio/CLAUDE_NOTES.md` — first-person account of AI-assisted workflow
- `/scratch/hgv27681/work/fastcs-catio/SKILLS.md` — MyST/Mermaid patterns validated in project
- Git history (`git log`, `git diff df5c3c4..HEAD --stat`) — commit counts, file counts, timeline (verified)

### Secondary (MEDIUM confidence)
- Established persuasion architecture principles (training knowledge) — document section order and rhetorical patterns
- Technical writing practice for stakeholder advocacy documents (training knowledge) — what management audiences require to find claims credible

### Tertiary (LOW confidence)
- None: no low-confidence sources used; where training knowledge was applied it is flagged as MEDIUM

---
*Research completed: 2026-03-02*
*Ready for roadmap: yes*
