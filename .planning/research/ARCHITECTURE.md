# Architecture Research

**Domain:** Executive summary document — AI-assisted technical development
**Researched:** 2026-03-02
**Confidence:** HIGH

## Standard Architecture

### System Overview

An executive summary for a technical achievement targeted at management stakeholders
follows a persuasion architecture — it is not a reference document, it is a case. Each
section builds on the previous to move the reader from context to evidence to conclusion.

```
┌─────────────────────────────────────────────────────────────┐
│                      HOOK / CONTEXT                          │
│  What is CATio? Why does the architecture matter?            │
│  Stakes established. Reader oriented.                        │
├─────────────────────────────────────────────────────────────┤
│                    BEFORE STATE                              │
│  Hard-coded Python classes, manual maintenance burden.       │
│  Reader understands the problem being solved.                │
├─────────────────────────────────────────────────────────────┤
│                 WHAT CHANGED (EVIDENCE)                      │
│  Quantified: 113 commits, ~23k new lines, 16→56 files,      │
│  29 terminal types in YAML, GUI editor, dynamic generation. │
│  Reader sees the scale of transformation.                   │
├─────────────────────────────────────────────────────────────┤
│              HOW AI ENABLED THIS SCALE                       │
│  Code generation, refactoring, module decomposition.         │
│  Reader sees the mechanism — AI as force multiplier.         │
├─────────────────────────────────────────────────────────────┤
│                  AFTER STATE                                 │
│  Maintainability improvements. New terminal = YAML edit.     │
│  Reader sees the lasting value delivered.                    │
├─────────────────────────────────────────────────────────────┤
│             TRAJECTORY / WHAT COMES NEXT                     │
│  builder2ibek — more mature AI agent usage (GSD, skills).   │
│  Reader sees this as the beginning of a practice.            │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Section | Responsibility | What Reader Gains |
|---------|---------------|-------------------|
| Hook / Context | Orient reader to CATio domain | Understands the stakes |
| Before State | Show the pre-AI architecture pain | Understands what problem was solved |
| Evidence | Quantified scale of work | Concrete evidence of delivery |
| AI Mechanism | How Claude was actually used | Understands WHY this worked |
| After State | Architecture and maintainability | Sees lasting value |
| Trajectory | builder2ibek reference | Confidence this scales to future work |

## Recommended Document Structure

```
docs/explanations/ai-assisted-development.md
│
├── [Title] — signals what the page is about
│
├── [Introduction paragraph]
│       Purpose: orient the reader in 3-5 sentences.
│       What CATio does, why the architecture change mattered,
│       and that a single developer achieved this with AI assistance.
│
├── ## The Challenge
│       The before state — hard-coded Python classes,
│       ~1200 lines per terminal family in catio_hardware.py,
│       the maintenance burden of adding new terminal types.
│
├── ## The Transformation
│       What changed: YAML-driven dynamic controller generation,
│       catio-terminals GUI, elimination of per-terminal Python code.
│       Present the quantified evidence here (metrics table).
│
├── ## How AI Assistance Enabled This
│       Not a tutorial — explain WHAT types of AI help were used:
│       code generation, refactoring, module decomposition, design.
│       Acknowledge this predates GSD workflows and agent skills.
│
├── ## Architecture Impact
│       Before/after comparison (side-by-side or table).
│       Adding a new terminal: before vs after.
│       Maintainability, flexibility, single source of truth.
│
└── ## What This Means Going Forward
        Reference to builder2ibek as example of more mature AI usage.
        Advocacy close — make the case directly.
```

### Structure Rationale

- **Hook first:** Management readers scan. The opening paragraph must answer
  "why should I read this?" immediately. Lead with what was achieved, not how.

- **Before state before evidence:** Evidence only lands if the reader first
  understands what problem was being solved. Presenting metrics without context
  produces no persuasion.

- **Quantified evidence as the centre:** The numbers (113 commits, ~23k lines,
  29 terminal types, 16→56 files) are the strongest material. They belong in
  the middle — after context, before interpretation.

- **Mechanism after evidence:** Explaining HOW the AI was used (code generation,
  refactoring, decomposition) is more credible after the reader has seen the
  evidence of what was produced. Don't lead with "we used AI to generate code" —
  lead with what that produced.

- **Trajectory last:** The builder2ibek reference works best as a close — it
  signals that this is not a one-off experiment but the beginning of a practice
  that is already maturing.

## Architectural Patterns

### Pattern 1: Claim — Evidence — Implication

**What:** Each substantive paragraph makes a claim, supports it with concrete
evidence, and states the implication for the reader.
**When to use:** Every paragraph in the Evidence and Mechanism sections.
**Trade-offs:** Forces discipline — no claim without backing. Can feel repetitive
if overused, so paragraph-level not sentence-level.

**Example:**
```
CLAIM: The architectural change reduced the cost of adding new terminal types.
EVIDENCE: Before, each new terminal family required ~1200 lines of Python.
          After, adding the 29th terminal type is a YAML edit taking minutes.
IMPLICATION: The team can respond to new hardware requirements at a fraction of
             the previous effort.
```

### Pattern 2: Before / After as a Table

**What:** A structured comparison of the before and after states for a specific
dimension (e.g., "Adding a new terminal type").
**When to use:** The Architecture Impact section. One table maximum — more dilutes
the impact.
**Trade-offs:** Highly scannable for management readers. Risks oversimplification
if dimensions are chosen poorly. Choose dimensions that are unambiguously better.

**Example:**
```
| Task | Before | After |
|------|--------|-------|
| Add a new terminal type | Write ~1200 lines of Python | Edit terminal_types.yaml |
| Source of truth | Code and documentation diverge | Single YAML file |
| Terminal types supported | Hard-coded set | Any type with YAML definition |
```

### Pattern 3: Metrics Block

**What:** A concise set of quantified metrics presented together, not scattered
through prose.
**When to use:** The Transformation section. Present all key numbers in one place
so they land as a group and can be referenced easily.
**Trade-offs:** High impact. If any number is wrong, the whole block is damaged.
Verify all figures before finalising.

**Example:**
```
| Metric | Value |
|--------|-------|
| Commits in the work period | 113 (100 by Giles, 11 by copilot-swe-agent) |
| New source lines | ~23,000 |
| Source files | 16 → 56 |
| Terminal types defined in YAML | 29 |
| Time elapsed | ~2 weeks |
```

## Data Flow — Narrative Build

The document's narrative flows in one direction: from problem to proof to advocacy.

```
Reader enters knowing nothing
    ↓
[Introduction] — context established
    ↓
[The Challenge] — problem understood
    ↓
[The Transformation] — evidence absorbed
    ↓
[How AI Enabled This] — mechanism understood
    ↓
[Architecture Impact] — value assessed
    ↓
[What This Means] — reader is persuaded or informed, decision possible
```

No section should loop back. Forward-only narrative. Each section assumes
the reader has absorbed the prior sections.

### Key Data Flows

1. **Context to evidence:** The Challenge section feeds directly into The
   Transformation — the reader needs to know the problem before the solution
   numbers are meaningful.

2. **Evidence to mechanism:** The quantified output (What Changed) comes
   before the explanation of method (How AI Helped) — this is intentional.
   Evidence first removes the defensive reaction "this is just AI hype".

3. **Mechanism to impact:** How AI was used (code gen, refactoring) flows
   into what that produced architecturally — connects cause to effect.

## Build Order for Document Phases

Sections are not independent — write them in dependency order:

```
1. Metrics table (Transformation section)
       Must be written first. All other sections reference these numbers.
       Verify figures against git history before writing anything else.

2. Before State (The Challenge)
       Write second. Establishes baseline that makes metrics meaningful.
       Source: git show df5c3c4, catio_hardware.py before state.

3. After State (Architecture Impact)
       Write third. Needs the before state to exist for comparison.
       Source: architecture-overview.md, terminal-yaml-definitions.md.

4. How AI Enabled This
       Write fourth. Needs the what (transformation) established before the how.
       Source: author retrospective, commit history patterns.

5. Introduction paragraph
       Write last. Summarises everything — easier once all sections exist.
       Must stand alone for scan readers who stop after the intro.

6. Trajectory close (builder2ibek)
       Write last, or simultaneously with Introduction.
       One paragraph. Forward-looking. Advocacy tone.
```

## Anti-Patterns

### Anti-Pattern 1: Leading With Process

**What people do:** Start with "We used Claude Opus to help with development" or
"AI-assisted development involves using LLMs to..."
**Why it's wrong:** Management readers will frame the entire document as "AI
experiment" and discount the evidence. Lead with the achievement, not the method.
**Do this instead:** Lead with what was delivered in the opening paragraph. Introduce
the AI mechanism only after evidence is established.

### Anti-Pattern 2: Listing Tasks Instead of Showing Impact

**What people do:** "Claude was used to generate YAML parsers, write tests, create
the GUI, refactor modules..."
**Why it's wrong:** This is a list of tasks, not a case for AI-assisted development.
Management doesn't care about task lists.
**Do this instead:** Frame AI assistance in terms of what it enabled — speed,
scale, quality — with specific before/after comparisons.

### Anti-Pattern 3: Burying the Numbers

**What people do:** Scatter metrics through paragraphs: "...which required over
23,000 new lines across more than 50 files, completed in about two weeks..."
**Why it's wrong:** Metrics are the strongest material. Buried in prose they are
easy to miss and hard to reference.
**Do this instead:** Put all key metrics in a table in the Transformation section.
Let prose point to the table, not replace it.

### Anti-Pattern 4: Overly Technical for the Audience

**What people do:** Include YAML snippets, Python class hierarchies, ADS protocol
details to show technical depth.
**Why it's wrong:** The audience is management and stakeholders, not developers.
Technical depth signals effort, but loses the reader.
**Do this instead:** One architecture diagram (the before/after table) is enough.
Reference the technical docs (`architecture-overview.md`, `terminal-yaml-definitions.md`)
for readers who want depth.

### Anti-Pattern 5: Hedging the Advocacy

**What people do:** End with "AI assistance may have benefits in certain contexts
depending on the nature of the work."
**Why it's wrong:** The document's explicit purpose is advocacy. Hedging undercuts
this.
**Do this instead:** Make the case directly. "This body of work demonstrates that
AI assistance enabled a single developer to deliver what would otherwise have
required a larger team or significantly more time." Then cite the evidence.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Intro → Challenge | Forward reference only | Intro can foreshadow but not summarise |
| Challenge → Transformation | Numbers connect directly | Challenge establishes the baseline the numbers beat |
| Transformation → How AI Enabled | Cause-effect link | Keep this tight — readers accept the cause once they've seen the effect |
| How AI Enabled → Architecture Impact | "This is why X improved" | Connect method to outcome explicitly |
| Architecture Impact → Trajectory | "And it's getting better" | Trajectory section should feel like upward momentum, not a pivot |

### External References

| Reference | Integration Pattern | Notes |
|-----------|---------------------|-------|
| `architecture-overview.md` | Link at end of Architecture Impact | For readers wanting technical depth |
| `terminal-yaml-definitions.md` | Link at end of Transformation | Shows the YAML they only see in the table |
| `builder2ibek` project | Named reference in Trajectory | Don't link if it's outside this repo — mention by name |

## Scaling Considerations

This is a documentation page, not a system. "Scaling" here means audience reach:

| Audience | Adjustments |
|----------|-------------|
| Management reader (5 min) | Intro + metrics table + final paragraph only. All three must work alone. |
| Engaged stakeholder (10-15 min) | Full document as written. |
| Technical reader landing here | Introduction + Architecture Impact + links to technical docs. |

### Scaling Priority

1. **First: The intro paragraph must stand alone.** Some readers will read only
   this. It must deliver the core message without the rest of the document.

2. **Second: The metrics table must be self-explanatory.** Scanners will jump
   to it. Column headers and values must be unambiguous without reading surrounding text.

## Sources

- Project context: `.planning/PROJECT.md` — scope, audience, metrics, constraints
- Existing docs pattern: `docs/explanations/architecture-overview.md` — Sphinx/MyST format
- Sphinx/MyST format: `docs/explanations/` directory for formatting conventions
- Git history: `git log`, `git diff df5c3c4 HEAD --stat` — evidence figures verified
- Executive communication principles: derived from document purpose (advocacy for
  management audience) and standard persuasion structure (Context → Evidence → Implication)

---
*Architecture research for: Executive summary document — AI-assisted CATio development*
*Researched: 2026-03-02*
