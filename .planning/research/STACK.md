# Stack Research

**Domain:** Technical documentation — AI-assisted development executive summary (Sphinx/MyST markdown)
**Researched:** 2026-03-02
**Confidence:** MEDIUM

---

## Context

This is not a software technology stack in the traditional sense. The "stack" for this deliverable is a
documentation format, structure, and presentation approach. The output is a single Sphinx/MyST page in
`docs/explanations/` aimed at management and stakeholders making the case for AI-assisted development.

The recommended approach below is based on:
- What already exists in this codebase (existing explanation pages, conf.py, SKILLS.md)
- Established patterns from research organizations and developer experience reports (MEDIUM confidence,
  training knowledge only — web search unavailable)
- The specific constraints in PROJECT.md (Sphinx/MyST, advocacy tone, executive audience)

**Note:** WebSearch and WebFetch were unavailable during this research session. Findings about external
patterns are from training data (knowledge cutoff August 2025) and flagged accordingly.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| MyST Markdown | in pyproject.toml: myst-parser | Page authoring format | Already used by all explanation pages in this project — zero setup needed |
| Sphinx | in pyproject.toml | Documentation engine | Already configured and deployed — page just needs adding to toctree |
| pydata-sphinx-theme | >=0.12 | Visual presentation | Already active — provides professional look with responsive tables |
| sphinxcontrib-mermaid | in pyproject.toml | Architecture diagrams | Already configured (mermaid_output_format = "raw") — use for before/after diagrams |
| sphinx-design | in pyproject.toml | Grid cards, badges | Already enabled — use for callout boxes, metric highlights, summary cards |

All five are already installed, configured, and in active use. No new dependencies are required.

### Structural Components (Content "Stack")

| Component | Purpose | Why |
|-----------|---------|-----|
| Quantified metrics section | Concrete before/after numbers | Stakeholders respond to numbers, not prose — "113 commits, 23k lines, 2 weeks" is the evidence |
| Before/after comparison | Architectural change narrative | Shows magnitude of change without technical depth |
| AI role breakdown | Where AI helped, where human judgment was required | Prevents overstating or understating — credibility anchor |
| Trajectory reference | Pointer to builder2ibek as maturation example | Shows this is an ongoing capability, not a one-off experiment |
| Limitations acknowledgement | What predates structured agent workflows | Honesty increases stakeholder trust |

### Development Tools (No New Setup Required)

| Tool | Purpose | Notes |
|------|---------|-------|
| sphinx-autobuild | Live preview while writing | `tox -e docs-autobuild` — already configured |
| tox -e docs | Full build validation | Use before committing to catch broken links or warnings |
| myst-parser colon_fence | MyST admonition syntax (`:::`) | Already enabled in conf.py via myst_enable_extensions |

---

## Content Format Recommendations

### Proven Executive Summary Structure (MEDIUM confidence — training knowledge)

The GitHub blog post cited in CLAUDE_NOTES.md and the broader AI developer experience research
ecosystem (GitLab DevSecOps surveys, GitHub Octoverse, DORA State of DevOps) consistently surface
the same elements that land with non-technical stakeholders:

1. **Lead with outcome, not method.** Open with what was delivered (architectural transformation in
   two weeks by one developer), not with how Claude works.

2. **Concrete metrics, not percentages.** "113 commits over two weeks" is more credible than
   "40% productivity gain." The project has real numbers — use them.

3. **Before/after comparison with named artefacts.** Not "code improved" but "catio_hardware.py was
   ~1200 lines per terminal family; now 29 terminal types are defined in 14,276 lines of YAML
   generated from vendor XML."

4. **Acknowledge the tool honestly.** "Claude Opus via GitHub Copilot subscription ($39/month)" is
   transparent and grounds the ROI claim.

5. **Trajectory, not just snapshot.** The builder2ibek reference is important — it shows that the
   approach has matured since this work was done, addressing the "this was lucky" objection.

### MyST Format Specifics (HIGH confidence — verified in codebase)

The existing explanation pages establish the house style. Match it exactly:

```markdown
# Page Title (sentence case, concise)

Brief introduction paragraph — one or two sentences, no heading.

## Section Heading

Content...

### Subsection (sparingly)

Content...
```

- Use `|table|` format for before/after comparisons — already used throughout this project's docs
- Use ` ```mermaid ` blocks for architecture diagrams — already configured
- Use `:::` admonition syntax for key callouts — enabled via colon_fence
- No front matter (no YAML `---` block) — other explanation pages have none
- Link to sibling docs with relative paths: `[Architecture Overview](architecture-overview.md)`

**DO NOT use:** HTML, raw RST, custom CSS classes, or external images. The page must build cleanly
with `--fail-on-warning`.

### Admonitions for Emphasis (HIGH confidence — verified via SKILLS.md)

```markdown
:::{note}
This work predates GSD workflows and structured agent skills, which are covered in the
[builder2ibek](link) project.
:::
```

Use sparingly — one `note` for the "predates workflows" caveat, possibly one `tip` for the
advocacy conclusion. Avoid `warning` (wrong tone for advocacy).

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| MyST Markdown in docs/explanations/ | Separate PDF report | If audience does not access the Sphinx docs site — but DLS stakeholders likely do |
| Mermaid for architecture diagrams | ASCII art diagrams | ASCII is better for hierarchy trees; Mermaid is better for layer/flow diagrams (use Mermaid for before/after architecture) |
| Tables for metrics | Prose descriptions | Use tables — scannable at a glance for busy stakeholders |
| Inline code snippets (sparingly) | Extensive code blocks | Executive audience: zero or one brief code example max |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Percentage productivity claims without a study | Unverifiable, invites skepticism | Raw counts: commits, files, lines, days |
| Jargon: "LLM", "token", "context window" | Opaque to management audience | "AI assistant (Claude Opus)" |
| Step-by-step prompting examples | This is an executive summary, not a tutorial | One short quote from CLAUDE_NOTES.md workflow if illustrative |
| Lengthy code examples | Loses executive audience | Architecture diagrams instead |
| Footnotes or endnotes | Breaks narrative flow in Sphinx | Use linked sections instead |
| Separate standalone file (PDF, slide deck) | Fragile, gets stale | Living doc in Sphinx updates with project |

---

## Stack Patterns by Variant

**If the audience is primarily technical management:**
- Include the Mermaid before/after architecture diagram
- Include the commit/file/line metrics table
- One paragraph on the refactoring workflow (Opus for analysis, Sonnet for implementation)

**If the audience is non-technical executive:**
- Lean harder on the time/team-size comparison
- Lead with the "one developer, two weeks, normally requires larger team" framing
- The Mermaid diagrams may be skipped or replaced with the ASCII tree from architecture-overview.md

**The PROJECT.md targets both.** Write for technical management (can understand architecture diagrams),
with the opening paragraph accessible to non-technical readers.

---

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| myst-parser | in dev deps | colon_fence enabled — `:::` admonitions work |
| sphinxcontrib-mermaid | in dev deps | mermaid_output_format = "raw" — no mmdc needed |
| sphinx-design | in dev deps | Grid cards, badges available |
| pydata-sphinx-theme | >=0.12 | Tables render with responsive styles |

All versions are pinned in `pyproject.toml` dependency-groups.dev — no compatibility work needed.

---

## Key Metrics Already Available (from PROJECT.md)

The page does not need research to generate metrics — they are documented in PROJECT.md:

| Metric | Value | Source |
|--------|-------|--------|
| Time to deliver | ~2 weeks | PROJECT.md |
| Total commits | 113 (100 Giles, 11 copilot-swe-agent, 2 Gregory Gay) | PROJECT.md |
| New source code | ~23k lines | PROJECT.md |
| Source files | 16 to 56 (before to after) | PROJECT.md |
| Terminal types defined | 29 in YAML | PROJECT.md |
| YAML definition size | 14,276 lines | PROJECT.md |
| Previous approach | ~1200 lines Python per terminal family in catio_hardware.py | PROJECT.md context |
| Tool used | Claude Opus via GitHub Copilot ($39/month subscription) | CLAUDE_NOTES.md |
| AI model versions | Claude Sonnet 4.5 (primary), Claude Opus 4.5 (analysis/refactor) | CLAUDE_NOTES.md |

These are the hard evidence. The document must present them prominently — they are what makes the
advocacy case.

---

## Sources

- `/scratch/hgv27681/work/fastcs-catio/.planning/PROJECT.md` — project requirements and known metrics (HIGH confidence)
- `/scratch/hgv27681/work/fastcs-catio/docs/conf.py` — Sphinx configuration, verified extensions (HIGH confidence)
- `/scratch/hgv27681/work/fastcs-catio/docs/explanations/*.md` — existing explanation page format (HIGH confidence)
- `/scratch/hgv27681/work/fastcs-catio/CLAUDE_NOTES.md` — first-person account of AI-assisted workflow (HIGH confidence)
- `/scratch/hgv27681/work/fastcs-catio/SKILLS.md` — MyST/Mermaid patterns already validated in project (HIGH confidence)
- Training knowledge: stakeholder communication patterns for AI productivity — unverified by web search (MEDIUM confidence)

---

*Stack research for: AI-assisted development executive summary documentation (Sphinx/MyST)*
*Researched: 2026-03-02*
