# App Store App-Preview cut recipe

App Store / Play Store **App Previews** have hard rules the 33s/60fps master breaks:

| Rule | Requirement |
|------|-------------|
| Length | **15–30 seconds** (trim ~3s from 33s) |
| Frame rate | **30 fps** (down from 60) |
| Dimensions | **exact device size** — iPhone 6.5": `886×1920` (portrait) or `1920×886` (landscape). Not 1080×1920. |
| Format | .mov / .mp4 / .m4v, H.264 |
| Poster | first frame becomes the thumbnail |

**Render the exact size natively** (compositions `PromoStorePortrait` 886×1920 /
`PromoStoreLandscape` 1920×886) — never letterbox or stretch a 1080-wide file.

## Trim to ≤30s without chopping speech
Don't uniformly fast-forward. Apply a **gentle global speed-up (~6%)** plus a **harder
speed-up (~2.5×) only in the silent gaps between VO lines**, so no spoken word is rushed.
Cut points must land in silence (use the VO start times + measured line durations from the
`build_audio.py` run). Then output 30fps.

Single-pass ffmpeg (segment remap in one `filter_complex`, no drift). Adjust the `SEG` list
to your VO gaps:

```python
import subprocess
SRC = "out/promo-store-886x1920.mp4"
DST = "out/promo-store-886x1920-appstore.mp4"
# (start, end, speed) — cuts fall only in silence between spoken lines
SEG = [(0.00,11.45,1.06),(11.45,12.15,2.50),(12.15,23.07,1.06),
       (23.07,25.15,2.50),(25.15,28.28,1.06),(28.28,28.85,2.50),(28.85,33.05,1.06)]
def atempo(sp):
    if abs(sp-1.06)<1e-6: return "atempo=1.06"
    if abs(sp-2.50)<1e-6: return "atempo=1.581139,atempo=1.581139"   # 2.5x, pitch-kept
    return f"atempo={sp}"
parts, vl, al = [], [], []
for i,(s,e,sp) in enumerate(SEG):
    parts.append(f"[0:v]trim=start={s}:end={e},setpts=(PTS-STARTPTS)/{sp}[v{i}]")
    parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,{atempo(sp)}[a{i}]")
    vl.append(f"[v{i}]"); al.append(f"[a{i}]")
fc = ";".join(parts) + ";" + "".join(v+a for v,a in zip(vl,al)) + \
     f"concat=n={len(SEG)}:v=1:a=1[vc][a];[vc]fps=30[v]"
subprocess.run(["ffmpeg","-y","-i",SRC,"-filter_complex",fc,"-map","[v]","-map","[a]",
  "-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-r","30",
  "-c:a","aac","-b:a","256k","-movflags","+faststart",DST], check=True)
```

Verify: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate
-of csv=p=0 DST` → `886,1920,30/1`, and duration ≤ 30s.

The App Preview uploads in App Store Connect's **Previews and Screenshots** media area
(same place as screenshots) — *not* the Build section, and unrelated to App Clips.
