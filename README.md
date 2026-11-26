# News Image — 26 November 2026

[![news-image-20261126](https://make.fun/badge/news-image-20261126.svg)](https://make.fun/bounty/news-image-20261126)
[![rank](https://make.fun/badge/news-image-20261126/xoman222-max/news-image-20261126/rank.svg)](https://make.fun/bounty/news-image-20261126)
[![reward](https://make.fun/badge/news-image-20261126/xoman222-max/news-image-20261126/reward.svg)](https://make.fun/bounty/news-image-20261126)

Sum up 26 November's world news in one image — a [make.fun](https://make.fun/bounty/news-image-20261126) bounty entry.

## The image

A one-page newspaper front page for Thursday 26 November 2026: 35 stories
across 7 regions, every one of which happened or was first reported on that
day. 14 featured stories with a drawn scene each, a UTC timeline, a world map
with numbered pins, an "ALSO ON THURSDAY 26 NOVEMBER" list, and a DATE CHECK
box naming the tempting near-miss stories that were left out on purpose
(Hormuz tankers: 25 Nov; COP31 collapse: 22 Nov; Taiwan shares: 25 Nov
close; Nasdaq -4%: 25 Nov; 49ers-Vikings: 22 Nov).

## How it is made

`main.py` draws the whole page from scratch in pure Python 3.13 standard
library (no PIL, no network): a 5x7 bitmap font, a small vector canvas,
stylised continent polygons, 14 flat vector scenes, and a calibrated
newsprint grain. The output is deterministic — two runs write identical
bytes.

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png (1024x1024)
```

`entry.png` in this repo is the image that run produced (296,901 bytes).

## Bounty

- Competition: [news-image-20261126](https://make.fun/bounty/news-image-20261126)
- Prize: $100 shared by the top 50 entries ($20 for 1st place)
- Deadline: 28 November 2026, 08:00 Taipei
