# PRODUCT PROMO BRIEF

## PRODUCT

promo-video is an open-source agent skill. Run `/promo-video` in a product's repository and
it inspects the code, optionally watches a YouTube video for creative inspiration, writes a
product-specific creative brief, and renders a verified launch film with Remotion.

## TARGET USER

Developers and small teams who ship a product (web app, SaaS, mobile app, AI product,
developer tool) and want a launch film without a production team. Evidence: README.md
"What it does" and SKILL.md description.

## CORE PROBLEM

A good launch film needs creative direction, honest product knowledge and careful
production. Templates give you someone else's story; screen recordings are not films.

## VALUE PROPOSITION

Core message: *your repository already holds the story; this skill directs it.*
Three carrying ideas: **UNDERSTAND** (the product, from its own code) · **DIRECT** (a
creative brief from a framework or an inspiration video) · **VERIFY** (facts, timing,
sound and the rendered file are checked).

## HERO FEATURES

1. Product understanding from the repository — `engine/promo_engine/analyzer.py`
2. Inspiration analysis through the `watch` skill into a twelve-section prompt — `watcher.py`, `artifacts.py`
3. The creative transformation into a product-specific prompt — `adapter.py`
4. Fact enforcement: sourced claims, numbers need claim ids — `artifacts.py`, `timeline.py`
5. One timeline, three formats — `config.py`, `renderer/src/layout.ts`
6. No background music, proven by QA — `qa.py`

## PRODUCT MOMENTS

- `promo scan` summarising a repository (real output, this repository).
- The brief's FACTUAL CLAIMS section, each claim citing a file.
- The pipeline: inspiration → YOUTUBE INSPIRATIONAL PROMPT → PRODUCT-SPECIFIC PROMO PROMPT → timeline → film.
- `promo check timeline` refusing a number without a source (real error text).
- `promo build` ending in a QA pass.

## VISUAL ASSETS

No screenshots or logo exist in the repository (scan: 0 logos, 0 screenshots). The product's
real surfaces are its terminal output and its Markdown/JSON artifacts, rendered as terminal
and document scenes. Stills of the film itself (from `promo qa`) are real product output.
Brand: none defined; use the graphite preset with a single blue accent.

## DEMO OPPORTUNITIES

- Repository → scan → brief (input → process → result).
- Inspiration video → frames and cuts → rules → product-specific prompt.
- A timeline with an unsourced number → the compiler stops it.
- One timeline → 16:9, 9:16 and 1:1 renders.

## FACTUAL CLAIMS

- C1: `/promo-video` asks one question: whether you have a YouTube inspiration video — source: skills/promo-video/SKILL.md:58
- C2: `.env` files and secret-named files are never read — source: skills/promo-video/engine/promo_engine/analyzer.py:8
- C3: A claim that cites a file that does not exist fails the brief check — source: skills/promo-video/engine/promo_engine/artifacts.py:217
- C4: Numbers on screen or in narration need a claim id — source: skills/promo-video/engine/promo_engine/timeline.py:256
- C5: Inspiration videos are analysed through the `watch` skill from claude-video — source: skills/promo-video/engine/promo_engine/watcher.py:3
- C6: Seven-word runs copied from the inspiration transcript are rejected — source: skills/promo-video/engine/promo_engine/artifacts.py:79
- C7: The same timeline renders 16:9 (1920×1080), 9:16 and 1:1 — source: skills/promo-video/engine/promo_engine/config.py:34
- C8: QA requires the master to stay below −45 dBFS wherever no effect or voice is sounding — source: skills/promo-video/engine/promo_engine/qa.py:20
- C9: Voice takes are compared with the script and retried — source: skills/promo-video/engine/promo_engine/voiceover.py:14
- C10: The inspiration prompt needs 10–20 numbered rules — source: skills/promo-video/engine/promo_engine/artifacts.py:131
- C11: Thirteen scene primitives, from hook to lockup — source: skills/promo-video/engine/promo_engine/timeline.py:34
- C12: The adapter rescales the source's scene structure and pacing to the runtime — source: skills/promo-video/engine/promo_engine/adapter.py:8
- C13: QA exports stills of every scene for review — source: skills/promo-video/engine/promo_engine/qa.py:154
- C14: MIT licensed — source: LICENSE:1

## RESTRICTIONS

- No user counts, customers, testimonials, ratings or speed claims: none exist in the repo.
- Do not name or depict any real company's product or any third-party brand.
- Do not claim the films are made "without AI" or "automatically perfect"; the agent writes
  the brief and timeline, and QA plus the agent's review verify them.
- Do not claim Codex or other hosts were tested end to end.
- No background music.
