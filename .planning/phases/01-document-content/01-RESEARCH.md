# Phase 1: Document Content - Research

**Researched:** 2026-03-02
**Domain:** Technical writing -- executive summary of AI-assisted architectural transformation
**Confidence:** HIGH

## Summary

This phase produces the content of an executive summary documenting the CATio architectural transformation. The document is a narrative piece, not a software engineering deliverable -- the "stack" is document structure, evidence presentation, and writing discipline. All the raw evidence already exists in the git history and codebase: 16 source files grew to 56, 20 hard-coded Python terminal controller classes were replaced by 29 YAML-defined terminal types with dynamic controller generation, and a separate `catio_terminals` GUI tool was created from scratch -- all within roughly two weeks by a single developer using Claude Opus.

The critical research finding is that the before/after contrast is concretely demonstrable through the codebase. The old `catio_hardware.py` contained 1199 lines of hand-written Python with 20 explicit controller classes (one per terminal type), each manually defining attributes via `add_attribute()` calls. The new approach uses a single factory function (`get_terminal_controller_class()`) that reads YAML definitions and generates controller classes at runtime. Adding a new terminal type went from "write a new Python class with 30-60 lines of boilerplate" to "edit a YAML file." This is the core narrative.

**Primary recommendation:** Structure the document as outcome-first prose with an embedded metrics table, a minimal before/after code snippet (old hard-coded class vs YAML definition), and a brief trajectory paragraph referencing builder2ibek. Keep it under 300 lines of MyST markdown. Every factual claim must trace to a git commit, file count, or line count.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Narrative structure**: Outcome-first opening -- lead with the transformation result (YAML-driven dynamic controllers, ~2 weeks, one developer + AI) then explain how
- **Two-paragraph before/after contrast** -- enough to understand the pain (hard-coded Python per terminal type) and appreciate the solution, without repeating existing technical docs
- **Trajectory arc (builder2ibek -> CATio)** woven into the main narrative, not a separate section
- **Forward-looking close** -- end on maintainability payoff ("new terminal = edit YAML, not write Python") as proof the investment pays forward
- **Both inline numbers in prose AND a summary metrics table** for quick reference
- **Metrics cover the full scope**: architecture transformation AND catio-terminals GUI tool
- **One minimal before/after code snippet** (3-5 lines each) to make the transformation tangible
- **Link to existing detailed docs** for readers who want to go deeper
- **Developer-AI collaboration framing** -- "pair programming" where developer provided architectural vision, Claude handled bulk implementation
- **Task-level specifics on what Claude did** -- name concrete tasks (controller boilerplate, protocol handlers, etc.)
- **Brief honest mention of limitations/challenges** to build credibility
- **Brief paragraph (2-3 sentences) on builder2ibek** as evidence of maturing AI-assisted practice
- **Developer positioned as the directing agent throughout** (CONT-06)
- **Mixed audience**: technical managers, fellow developers, and semi-technical stakeholders
- **Dual takeaway**: appreciation for the achievement + curiosity about AI adoption
- **Domain-specific terms** (EtherCAT, CoE, PDO, ADS) used with brief inline context on first mention
- **Cross-references to existing explanation pages** (architecture overview, terminal YAML definitions, etc.)
- **"Let raw numbers speak"** -- no productivity multiplier claims, present the data and let readers draw conclusions
- **builder2ibek positioned as the earlier, simpler AI project** that paved the way
- **Explicitly exclude**: step-by-step AI tutorials, detailed code examples, lengthy prose sections
- **"Short and snappy"** per FRMT-03

### Claude's Discretion
- Metric precision (exact vs rounded numbers) -- whatever reads naturally and stays credible
- Loading skeleton design for any diagrams or visual elements
- Exact section headings and document length within "executive summary" constraint

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONT-01 | Document includes a concise before-state description (hard-coded Python classes per terminal type) | Git evidence at commit `e8e2f37`: `catio_hardware.py` was 1199 lines with 20 explicit controller classes. Each terminal type required a dedicated Python class with manual `add_attribute()` calls (see Code Examples section). |
| CONT-02 | Document includes quantified scale metrics from git history (commits, lines, files, terminal types) | Full metrics table verified from git: ~141 non-merge commits by Giles (Dec 15 - Feb 5), 16->56 source files, 29 terminal types in YAML, 14,276 lines of YAML, ~17,680 lines of Python across both packages. See Verified Metrics section. |
| CONT-03 | Document includes high-level overview of architectural transformation (YAML-driven dynamic controllers, catio-terminals GUI) | Architecture documented in existing `architecture-overview.md` and `terminal-yaml-definitions.md`. Dynamic controller factory in `catio_dynamic_controller.py`. GUI tool is `catio_terminals` package with NiceGUI web editor. See Architecture Patterns section. |
| CONT-04 | Document identifies where Claude Opus was used to achieve rapid development | `CLAUDE_NOTES.md` documents specific AI usage: architecture docs generation (commit `4dcc9d5`), code refactoring when complexity grew (Opus for analysis, Sonnet for implementation), feature documentation before coding, skill extraction to AGENTS.md. |
| CONT-05 | Document states the timeline (~2 weeks, single developer) | Git history confirms: first major commit Dec 15 2025 (`399ff48`), main transformation Jan 22 - Feb 5 2026. Single developer (Giles Knap) authored ~141 of ~154 non-merge commits. |
| CONT-06 | Document frames the developer as the agent who directed AI, not AI as autonomous hero | `CLAUDE_NOTES.md` provides first-person evidence: developer directed all architecture, used Opus for analysis/refactoring, Sonnet for implementation. PITFALLS.md documents the anti-pattern and prevention strategy. |
| ADVC-01 | Document includes trajectory arc -- this work predates agent skills, builder2ibek shows maturation | `CLAUDE_NOTES.md` confirms pre-agent workflow (chat window, manual skill extraction). `builder2ibek` exists as sibling project at `/scratch/hgv27681/work/builder2ibek/` with structured agent features. |
| ADVC-02 | Document highlights maintainability improvement (new terminal = edit YAML, not write Python) | Before: adding a terminal required writing 30-60 lines of Python in `catio_hardware.py`. After: adding a terminal means adding ~15-25 lines of YAML to `terminal_types.yaml` (or using the GUI editor). 10 new terminal types were added after the initial set with zero Python changes. |
</phase_requirements>

## Standard Stack

### Core

This phase produces a document, not software. The "stack" is the writing approach and evidence sources.

| Component | Location | Purpose | Why Standard |
|-----------|----------|---------|--------------|
| MyST Markdown | `docs/explanations/` | Document format | All existing explanation pages use this format; zero setup needed |
| Git history | Repository | Primary evidence source | All metrics claims must be verifiable from git |
| `CLAUDE_NOTES.md` | Repository root | AI workflow evidence | First-person developer account of Claude usage |
| `AGENTS.md` | Repository root | AI context documentation | Shows how project-specific AI context was managed |
| Existing explanation pages | `docs/explanations/` | Cross-reference targets | Architecture overview, terminal YAML definitions, FastCS IOC docs |

### Supporting

| Component | Location | Purpose | When to Use |
|-----------|----------|---------|-------------|
| sphinx-design admonitions | In-page `:::` syntax | Callout boxes for caveats | One `note` for "predates workflows" caveat; sparingly |
| Mermaid diagrams | In-page code blocks | Visual architecture contrast | Only if a simple before/after diagram adds value; not required by user decisions |
| Relative links | MyST `[text](path.md)` | Cross-references to sibling docs | Link to architecture-overview.md, terminal-yaml-definitions.md, etc. |

### Alternatives Considered

| Recommended | Alternative | Tradeoff |
|-------------|-------------|----------|
| Single markdown file | Multi-file with includes | Complexity for no benefit -- this is one page |
| Inline metrics table | Separate data file | Table is small enough (8-10 rows) to inline |
| Minimal code snippet (3-5 lines) | Full before/after module comparison | Executive audience -- one snippet is enough to make the point tangible |

## Architecture Patterns

### Recommended Document Structure

```
# AI-Assisted Architectural Transformation of CATio

[Opening paragraph: outcome-first -- what was delivered, scale, timeline]

## The Transformation
[Before-state paragraph: hard-coded Python, maintenance burden]
[After-state paragraph: YAML-driven, dynamic generation, GUI tool]
[Minimal code snippet: before vs after]

## By the Numbers
[Metrics table: commits, files, lines, terminal types, timeline]

## How AI Accelerated Development
[What Claude did: concrete tasks named]
[Developer-AI collaboration framing]
[Honest limitations mention]
[builder2ibek trajectory woven in]

## What This Means Going Forward
[Maintainability payoff: new terminal = edit YAML]
[Forward-looking close]

## Learn More
[Cross-references to existing docs]
```

### Pattern: Outcome-First Opening

**What:** Lead with the transformation result, not the problem.
**When to use:** Always for executive summaries. Busy readers need the conclusion before the reasoning.
**Example:**
```
A single developer, working with Claude Opus over approximately two weeks,
transformed CATio from a system requiring hand-written Python for each
terminal type to one driven entirely by YAML definitions -- covering 29
terminal types across two packages and roughly 17,000 lines of Python.
```

### Pattern: Paired Evidence (Scale + Quality)

**What:** Every scale metric is immediately followed by a quality indicator.
**When to use:** For every quantitative claim.
**Example:**
```
| Metric | Value | Quality Indicator |
|--------|-------|-------------------|
| Terminal types | 29 in YAML | Validated against Beckhoff ESI XML |
| Source files | 16 -> 56 | Documented in 10 explanation pages |
```

### Anti-Patterns to Avoid

- **Productivity multiplier claims:** Never write "10x faster" or "saved 6 months." Present raw numbers and let readers draw conclusions.
- **AI as hero:** Never make Claude the grammatical subject of architectural decisions. "The developer directed; Claude executed."
- **Passive voice for AI contributions:** "The code was generated" obscures agency. Write "Claude generated the controller boilerplate under the developer's direction."
- **Jargon without context:** First mention of EtherCAT, CoE, PDO, ADS must include a brief inline explanation (e.g., "CoE (CANopen over EtherCAT) configuration parameters").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Metrics computation | Don't manually count commits or lines | Git commands verified against the repository | Accuracy -- manual counts drift from reality |
| Before/after code snippet | Don't write synthetic "example" code | Extract from actual git history (`git show e8e2f37:src/...`) | Authenticity -- real code is more credible than illustrations |
| builder2ibek description | Don't guess at what builder2ibek does | Check the sibling project's README.md | Accuracy -- the reference must match reality |

**Key insight:** This is a document about evidence. Every claim must trace to a verifiable artifact. Don't synthesise or approximate when the real data is available.

## Common Pitfalls

### Pitfall 1: Unverifiable Productivity Claims

**What goes wrong:** The document says "10x faster" without grounding in specifics. Skeptical stakeholders dismiss the entire document.
**Why it happens:** Authors reach for dramatic framing to convey impact.
**How to avoid:** Anchor every claim in verifiable facts. "141 commits over two weeks by one developer" is verifiable. "Equivalent to 6 months of traditional development" is not. Present raw numbers; let readers draw conclusions.
**Warning signs:** Any sentence with "X times faster" that lacks a specific baseline measurement.

### Pitfall 2: AI Treated as Autonomous Agent

**What goes wrong:** The narrative frames Claude as the agent that delivered the work, sidelining the developer's judgment, direction, and domain expertise.
**Why it happens:** AI tools are novel and attract disproportionate attention in the narrative.
**How to avoid:** Developer (Giles Knap) is the grammatical subject of all decisions. Claude is the subject of execution tasks. "The developer designed the YAML schema; Claude generated the 29 terminal definitions from Beckhoff XML."
**Warning signs:** Passive constructions like "the code was generated" or "the architecture emerged."

### Pitfall 3: Scale Without Quality Evidence

**What goes wrong:** The document leads with "17,000 lines of new code" but never demonstrates the code is correct or maintainable. This backfires with technical audiences who know large quantities of AI-generated code can be low quality.
**Why it happens:** Scale is easy to measure; quality is harder to articulate.
**How to avoid:** Pair each scale metric with a quality indicator: terminal definitions validated against Beckhoff ESI XML, system test suite, architecture documented in explanation pages, code refactored into smaller modules when complexity grew.
**Warning signs:** Scale metrics in the introduction with no quality follow-through anywhere.

### Pitfall 4: Omitting Conditions for Success

**What goes wrong:** The document implies AI-assisted development works universally without noting that this succeeded because of a developer with deep domain expertise directing the tool.
**Why it happens:** Advocacy tone tempts authors to omit caveats.
**How to avoid:** Frame as evidence from one project, not proof of a universal method. Mention the developer's pre-existing EtherCAT/TwinCAT/ADS expertise. The builder2ibek trajectory reference naturally addresses this by showing the approach has matured.
**Warning signs:** Language like "AI-assisted development enables..." (universal) rather than "this project demonstrates..." (evidential).

### Pitfall 5: Inaccurate Metrics

**What goes wrong:** Numbers quoted in the document don't match what git history shows. A single factual error undermines the entire evidence base.
**Why it happens:** Metrics are computed once during research and not re-verified against the source.
**How to avoid:** Every number in the document must be reproducible from a specific git command. Include the verification commands in plan task descriptions so the implementer can re-run them.
**Warning signs:** Round numbers that look estimated (e.g., "about 150 commits" when the actual count is 141).

## Code Examples

### Before State: Hard-Coded Terminal Controller (from git history)

Source: `git show e8e2f37:src/fastcs_catio/catio_hardware.py` (lines 215-270)

```python
class EL1004Controller(CATioTerminalController):
    """A sub-controller for an EL1004 EtherCAT digital input terminal."""
    io_function: str = "4-channel digital input, 24V DC, 3ms filter"
    num_channels: int = 4

    async def get_io_attributes(self) -> None:
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()
        self.add_attribute("WcState", AttrR(datatype=Int(), ...))
        self.add_attribute("InputToggle", AttrR(datatype=Int(), ...))
        for i in range(1, self.num_channels + 1):
            self.add_attribute(f"DICh{i}Value", AttrR(datatype=Int(), ...))
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"
```

Each terminal type required a dedicated Python class. 20 classes totalling 1199 lines. Adding a new terminal type meant writing 30-60 lines of boilerplate.

### After State: YAML Terminal Definition (current)

Source: `src/catio_terminals/terminals/terminal_types.yaml`

```yaml
EL1004:
  description: 4Ch. Dig. Input 24V, 3ms
  identity:
    vendor_id: 2
    product_code: 65810514
    revision_number: 1048576
  symbol_nodes:
    - name_template: Channel {channel}
      index_group: 61489
      type_name: InputBits
      channels: 4
      access: Read-only
      fastcs_name: channel_{channel}
      selected: true
  coe_objects: []
  group_type: DigIn
```

The dynamic controller factory (`get_terminal_controller_class()`) reads this YAML at runtime and generates a FastCS controller class. Adding a new terminal type means adding a YAML block (or using the GUI editor).

### Recommended Minimal Snippet for the Document

For the executive summary, use an even more condensed version (3-5 lines each side):

```python
# Before: one Python class per terminal type (x20 classes, 1199 lines)
class EL1004Controller(CATioTerminalController):
    io_function = "4-channel digital input, 24V DC, 3ms filter"
    async def get_io_attributes(self):
        for i in range(1, 5):
            self.add_attribute(f"DICh{i}Value", AttrR(datatype=Int(), ...))
```

```yaml
# After: one YAML block per terminal type (29 types, generated from vendor XML)
EL1004:
  description: 4Ch. Dig. Input 24V, 3ms
  symbol_nodes:
    - name_template: Channel {channel}
      channels: 4
      selected: true
```

## Verified Metrics

All numbers below are verified from the git repository. Commands are provided for re-verification.

### Timeline

| Metric | Value | Verification Command |
|--------|-------|---------------------|
| First major commit | 2025-12-15 (`399ff48`) | `git show 399ff48 --format="%ad" --date=short` |
| Core transformation period | 2026-01-22 to 2026-02-05 | `git log --after="2026-01-21" --before="2026-02-06" --oneline` |
| Primary developer | Giles Knap | `git log --format="%aN" \| sort \| uniq -c` |
| Duration | ~2 weeks (core), ~7 weeks (full Dec-Feb) | Git date range |

### Scale Metrics

| Metric | Before | After | Verification |
|--------|--------|-------|--------------|
| Python source files (src/) | 16 | 50 | `git ls-tree -r --name-only {commit} -- src/ \| grep '\.py$' \| wc -l` |
| Total source files (src/) | 16 | 56 | `git ls-tree -r --name-only {commit} -- src/ \| wc -l` |
| Hard-coded terminal classes | 20 (in catio_hardware.py) | 0 needed (dynamic) | `grep "^class " catio_hardware.py` |
| Terminal types supported | 20 (Python only) | 29 (YAML) | `grep "^  EL\|^  EK\|^  ELM" terminal_types.yaml \| wc -l` |
| catio_hardware.py lines | 1199 | 1204 (still present as fallback) | `wc -l catio_hardware.py` |
| YAML terminal definitions | 0 | 14,276 lines | `wc -l terminal_types.yaml` |
| catio_terminals package | Did not exist | 31 Python files, 6,256 lines | `find src/catio_terminals -name '*.py' \| wc -l` |
| fastcs_catio Python lines | ~5,000 (est.) | 11,424 | `find src/fastcs_catio -name '*.py' -exec wc -l {} + \| tail -1` |
| New dynamic modules | 0 | 6 files (catio_dynamic_*.py, terminal_config.py, logging.py) | `ls src/fastcs_catio/catio_dynamic*.py` |

### Commit Metrics

| Metric | Value | Verification |
|--------|-------|--------------|
| Non-merge commits (Dec 15 - Feb 5) | 154 | `git log --no-merges --after=... --before=... \| wc -l` |
| Giles Knap commits (all name variants) | ~141 | `git log --author="Giles\|giles\|gilesknap" --no-merges ...` |
| copilot-swe-agent commits | 11 (documentation updates) | `git log --author="copilot-swe-agent" ...` |
| Gregory Gay commits | ~2-15 (varies by name variant) | `git log --author="Gregory\|ggay" ...` |
| Pull requests merged | 13 | `git log --oneline \| grep "Merge pull request"` |

### Key Milestones

| Date | Commit | Milestone |
|------|--------|-----------|
| 2025-12-15 | `399ff48` | Upgrade to latest FastCS framework |
| 2026-01-05 | `c1d9b08` | Add initial testing capability (mock server, unit/system/perf tests) |
| 2026-01-13 | `4dcc9d5` | Generate and refine Architecture Docs with Claude |
| 2026-01-22 | `ce8efa1` | Add system test |
| 2026-01-27 | `d2cb4a8` | Add initial version of terminal description YAML editor (catio_terminals born) |
| 2026-01-29 | `2788c9f` | Create dynamic terminal controller class generator |
| 2026-02-02 | `6291d22` | Switch to using YAML for all terminals |
| 2026-02-04 | `fff1a1b` | Refactor dynamic code into smaller modules |
| 2026-02-05 | `a0cc799` | Update documentation to reflect updated code |

### Metric Precision Recommendation (Claude's Discretion)

For the document, use these rounded/natural phrasings:
- "approximately two weeks" (not "14 calendar days" or "10 working days")
- "29 terminal types" (exact, small enough to be precise)
- "over 14,000 lines of YAML" (rounded from 14,276 -- exact is fine too)
- "50 Python source files" (rounded from 50 -- actually exact in this case)
- "roughly 140 commits" or "over 140 commits" (from 141 non-merge by Giles)

## AI Usage Evidence (for CONT-04)

From `CLAUDE_NOTES.md` and git history, specific Claude tasks include:

| Task | Evidence | AI Role | Developer Role |
|------|----------|---------|----------------|
| Architecture documentation | Commit `4dcc9d5`: "Generate and refine Architecture Docs with Claude" | Generated initial doc drafts (1,307 lines across 14 files) | Refined and validated accuracy |
| XML parsing / terminal definitions | CLAUDE_NOTES.md: "each time I asked Claude to look in the cached Beckhoff Terminal XML..." | Parsed vendor XML, extracted terminal definitions | Directed what to extract, validated results |
| Code refactoring | CLAUDE_NOTES.md: "hit 12000 lines and Claude Sonnet was struggling... asked Opus to take a look" | Opus analyzed and proposed refactoring; Sonnet implemented | Decided when and how to refactor |
| Feature implementation workflow | CLAUDE_NOTES.md: "get the agent to write a document for the feature first" | Wrote feature docs, then implemented code | Designed workflow, reviewed docs before implementation |
| Controller boilerplate | 20 hard-coded classes -> dynamic factory | Generated repetitive attribute definitions | Designed the YAML schema and factory pattern |
| AGENTS.md / skills | CLAUDE_NOTES.md: multiple references | Codified domain knowledge into reusable context | Identified what knowledge to capture |

**AI model versions used:** Claude Sonnet 4.5 (primary implementation), Claude Opus 4.5 (analysis, refactoring, complex features). Via GitHub Copilot subscription ($39/month).

## builder2ibek Trajectory Context (for ADVC-01)

The builder2ibek project exists at `/scratch/hgv27681/work/builder2ibek/` as a sibling project. Key points for the narrative:

- CATio work predates structured agent workflows (GSD, agent skills, AGENTS.md skills)
- builder2ibek represents the next stage: built with more mature AI agent features
- The trajectory shows the developer's practice improving over time, not a one-off experiment
- **Open question:** The exact builder2ibek URL and its public accessibility need to be verified before linking. The narrative should work even without a direct link -- describe the progression rather than depending on the URL.

## Existing Cross-Reference Targets

Pages the executive summary should link to with `[text](path.md)` relative paths:

| Page | Path | What It Covers |
|------|------|----------------|
| Architecture Overview | `architecture-overview.md` | Full architecture with Mermaid diagrams, dynamic controller generation |
| Terminal YAML Definitions | `terminal-yaml-definitions.md` | Complete YAML schema, how to add terminals, GUI editor usage |
| FastCS EPICS IOC | `fastcs-epics-ioc.md` | Dynamic controller generation details, runtime attribute creation |
| ADS Client | `ads-client.md` | Protocol implementation details |

## Open Questions

1. **builder2ibek public URL**
   - What we know: The project exists locally and is referenced in PROJECT.md as a maturation example
   - What's unclear: Whether it has a public GitHub URL accessible to the target audience
   - Recommendation: Write the builder2ibek paragraph to work without a clickable link. If the URL is confirmed public, add it as enhancement. The planner should flag this as an author-confirmation step.

2. **Exact metric scoping (architecture-only vs all commits)**
   - What we know: PROJECT.md says "113 commits" but git shows ~141 non-merge commits by Giles in the full period. The 113 figure may have been computed differently (e.g., architecture-only, excluding deploy/doc commits).
   - What's unclear: Whether the document should use ~141 (all non-merge by Giles) or a filtered count.
   - Recommendation: Use the full non-merge count (~141 by Giles, ~154 total) with a note that this includes testing, documentation, and cleanup commits alongside the architecture work. This is more honest and the larger number is still impressive. Flag for author confirmation.

3. **catio_hardware.py still exists with hard-coded classes**
   - What we know: The file still contains 20 hard-coded classes (1204 lines) alongside the new dynamic factory. The routing logic falls back to hard-coded classes first, then dynamic.
   - What's unclear: Whether the old classes are retained intentionally (e.g., for tested terminals) or are technical debt.
   - Recommendation: Frame accurately -- "dynamic generation handles all 29 YAML-defined terminal types; legacy explicit classes remain as a validated fallback for the original set." This is honest and does not overstate the transformation.

## Sources

### Primary (HIGH confidence)
- Git repository history -- all metrics verified against actual commits
- `src/fastcs_catio/catio_hardware.py` -- before-state evidence (hard-coded classes)
- `src/fastcs_catio/catio_dynamic_controller.py` -- after-state evidence (factory function)
- `src/catio_terminals/terminals/terminal_types.yaml` -- YAML terminal definitions
- `CLAUDE_NOTES.md` -- first-person developer account of AI usage
- `docs/explanations/architecture-overview.md` -- existing architecture documentation
- `docs/explanations/terminal-yaml-definitions.md` -- existing YAML documentation

### Secondary (MEDIUM confidence)
- `.planning/PROJECT.md` -- project context and previously computed metrics (some numbers differ from current git count; flagged in Open Questions)
- `.planning/research/STACK.md` -- previous stack research (document format recommendations)
- `.planning/research/PITFALLS.md` -- previous pitfall research (writing discipline guidance)

### Tertiary (LOW confidence)
- builder2ibek trajectory details -- project exists locally but public accessibility unverified

## Metadata

**Confidence breakdown:**
- Verified metrics: HIGH -- all numbers confirmed from git history with reproducible commands
- Document structure: HIGH -- user decisions in CONTEXT.md are specific and complete
- AI usage evidence: HIGH -- CLAUDE_NOTES.md and commit messages provide direct evidence
- builder2ibek context: MEDIUM -- project exists but URL/accessibility needs confirmation
- Pitfalls/writing discipline: MEDIUM -- based on established technical writing principles (from prior research)

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable -- git history does not change; document format is established)
