# timeline.json

The film, as data. You write it from `creative-prompt.md`; `promo compile` validates it
and turns it into `render-config.json`, `storyboard.md` and `narration.txt`.

```json
{
  "version": 1,
  "product": "Tallyboard",
  "source": "framework",
  "seed": 3,
  "style": { "preset": "graphite", "accent": "#1F8A70" },
  "narration": { "enabled": true },
  "scenes": [
    {
      "id": "hook",
      "kind": "hook",
      "duration": 8,
      "purpose": "visual mystery before the name",
      "source": "framework §4 beat 1",
      "props": { "line": "Where did this month go?", "fragments": ["taxi", "lunch", "hosting"] },
      "narration": { "text": "Every month ends the same way.", "offset": 5.2 }
    }
  ]
}
```

## Top level

| Field | Meaning |
|---|---|
| `version` | always `1` |
| `product` | name shown in reports |
| `source` | `framework` (Path B) or `inspiration` (Path A) |
| `seed` | integer; every scattered or orbiting element is placed from it. Same seed, same film. |
| `style.preset` | `graphite` (near-black, default) · `midnight` (deep blue-black) · `paper` (light) |
| `style.accent` / `ground` / `ink` | optional `#rrggbb` overrides; use the product's own accent |
| `narration.enabled` | `true` by default. `false` requires `narration.reason`. |

## Scene fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | lowercase slug, unique |
| `kind` | yes | one of the primitives below |
| `duration` | yes | seconds, 1.5–30 |
| `purpose` | yes | the scene's job in the story (goes into the storyboard) |
| `props` | yes | per kind, below. Media paths are relative to `promo/assets/`. |
| `transition` | no | `{ "type": "fade" \| "light" \| "push" \| "zoom" \| "wipe" \| "cut", "duration": 0.5 }`: how this scene *enters*. Default `fade` 0.5 s. |
| `narration` | no | a string, or `{ "text", "offset" }` (seconds after scene start, default 0.4) |
| `claims` | when showing facts | claim ids from `product-brief.md`. **Any digit on screen or in narration needs one.** |
| `source` | recommended | the inspiration rule (`R4`) or framework beat this scene realises |
| `sfx` | no | extra cues: `[{ "fx": "click", "at": 2.4, "vol": 0.8 }]`, `at` relative to the scene |
| `autoSfx` | no | `false` turns off the scene's automatic sound design |

Narration is checked against time: at about 2.7 words per second, a line must fit in the
rest of its scene. The whole film must fit the configured duration range (60–100 s by default).

## Primitives

Thirteen primitives. Each is a directed scene, not a slide. All adapt to 16:9, 9:16 and 1:1.

### `hook`
Point of light; `fragments` orbit it faster and faster; everything freezes; `line` lands.
`line` (≤70) · `fragments` (0–16 short real words from the product's world) · `eyebrow` · `accent` (words to colour) · `freezeAt` (s, default 55% of the scene)

### `wordzoom`
Typographic hook: a small line types in (optionally replaced by `then`); two cursors
select `word`; the camera flies through one of its letters into the accent ground, where
`name` lands.
`line` (≤60) · `then` (≤60) · `word` (must appear in the final text) · `through` (letter index to fly through; default the first round letter) · `name` · `tags` (two cursor labels, default `you`, `agent`)

### `title`
The name lands in silence; tracking closes; a band of light crosses it.
`name` (≤32) · `tagline` (≤70) · `logo` (asset)

### `statement`
One large line, when the words are the subject.
`text` (≤90) · `accent` (words) · `eyebrow` · `small` (≤110, e.g. honest small print) · `size` `xl|l|m`

### `pillars`
Two to four ideas or stages; at the end one stays lit.
`items` (2–4, strings or `{title, detail}`) · `focus` (index) · `title`

### `screen`
Real product media in a device, with a camera move and callouts.
`media` (image or video) · `device` `browser|phone|desktop|none` · `camera` `push|pull|pan|rise|hold` ·
`focus` `{x, y}` (0–1, where the push goes) · `callouts` (0–4 `{x, y, label, at?}`) · `cursor` `{x, y, at}` ·
`title` · `caption` · `url` (shown in the browser bar)

### `flow`
Input → process → result. A pulse travels the connectors; each step lights on arrival.
`steps` (2–5 `{label, detail?, lines?, media?, kind?}`) · `title`

### `terminal`
Real commands typed at a human pace; real output arriving line by line.
`lines` (1–14: `{type: "cmd"|"out"|"ok"|"dim", text, hold?}`) · `title` · `prompt` (default `$`) · `caption`.
The engine rejects a terminal whose typing does not fit its duration.

### `document`
A real artifact the product produces, assembling section by section.
`title` · `sections` (1–4 `{heading, lines[]}`) · `source` · `caption`

### `montage`
Many real surfaces at once, in depth.
`items` (3–8 `{media?, label?}`) · `layout` `orbit|stack|grid|row` (row: one shared height, for mixed aspect ratios) · `title`

### `compare`
Two paths: the usual way (muted) and this product's way (lit). Facts only.
`left`, `right` (`{title, items: 1–5}`) · `title` · `verdict`

### `metric`
One sourced number, counted up. **Requires a claim id.**
`value` · `label` · `prefix` · `suffix` · `small` (the source, in small print)

### `lockup`
The light returns and contracts into the name; closing line; fade.
`name` · `line` · `logo` · `cta` (e.g. an install command or URL) · `small`

## Sound effects

`click` `pop` `pop2` `whoosh` `chime` `type` `tick` `tick2` `drag` `sparkle` `riser` `rise`
`thud` `kick` `dive` `ascent` `braam`. All are short. There is no music file to reference.

Automatic cues (turn off per scene with `autoSfx: false`): risers into light transitions,
whooshes on push/zoom/wipe, an impact on the hook's freeze, keystrokes while a command
types, ticks as output arrives, pops as steps and callouts land, a chime when a result
resolves, a resolve under the lockup.
