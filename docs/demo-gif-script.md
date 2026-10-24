# Demo GIF — script

**Goal:** in about 20 seconds, show what makes UniDocVerse different: a hard question about a real 104-page government report, answered with exact figures and the source cited — all on this computer.

**Setup:** demo organisation only (fictional tax forms + the public CDTFA 2023-24 Annual Report). 1280×800, light mode, no personal data.

| # | Time | Screen | What the viewer learns |
|---|---|---|---|
| 1 | 0–3 s | **Documents**: W-2s, 1099s, K-1s and the CDTFA Annual Report, each with its detected type | It reads and classifies real paperwork |
| 2 | 3–9 s | **Research agent**: the question is typed — *"How much sales and use tax revenue did California collect in fiscal year 2023-24, how did it compare with 2022-23, and how much went to the General Fund?"* | You ask in plain English, even three-part questions |
| 3 | 9–12 s | Thinking indicator — about 150 s on a cold start, sped up 50× and labelled on screen | It searches the documents |
| 4 | 12–20 s | **Answer**: $79.4 billion, down 0.6% from 2022-23, $34.5 billion to the General Fund — with **CDTFA Annual Report 2023-24.pdf** as the cited source | Exact figures, every one traceable to its source |

**Caption under the GIF in the README:** *Ask in plain English; every figure is cited to the file it came from — runs entirely on your machine.*

**Re-record:** `DEMO_TOKEN_FILE=… node docs/record_demo.js out/`, then build the GIF with ffmpeg (sped-up thinking segment labelled) (needs the app running on localhost:4200 / :7979 and a demo-organisation token).
