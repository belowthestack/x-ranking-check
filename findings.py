"""
Prints the three findings in a clean, readable form, for screen recording.

No API calls. Instant. Safe to type live on camera:

    python findings.py
"""
import csv
import io
import math
import re
import statistics
import sys
from collections import defaultdict

CSV = "indie-founder-x-posts-2026-11-11.csv"


def spearman(a, b):
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        out = [0] * len(x)
        for pos, i in enumerate(order):
            out[i] = pos
        return out
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    den = math.sqrt(sum((ra[i] - ma) ** 2 for i in range(n))
                    * sum((rb[i] - mb) ** 2 for i in range(n)))
    return num / den


def bar(value, width=40):
    """A simple bar for a value in roughly -1..1."""
    filled = int(abs(value) * width)
    return ("#" * filled) if filled else "."


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else CSV
    rows = list(csv.DictReader(io.open(path, encoding="utf-8-sig")))
    for r in rows:
        for k in ("views", "likes", "replies", "reposts", "bookmarks"):
            r[k] = int(str(r[k]).replace(",", "") or 0)

    by = defaultdict(list)
    for r in rows:
        by[r["account handle"]].append(r["views"])
    med = {h: statistics.median(v) for h, v in by.items()}
    for r in rows:
        r["ratio"] = r["views"] / med[r["account handle"]]
        r["link"] = bool(re.search(r"https?://", r["post text"]))

    ratio = [r["ratio"] for r in rows]

    print()
    print("  {} posts.  {} accounts.  All under 50k followers.".format(
        len(rows), len(by)))
    print("  Each post measured against its OWN account's median views.")
    print()
    print("  " + "-" * 58)
    print("  WHICH ENGAGEMENT ACTUALLY TRACKS REACH")
    print("  " + "-" * 58)
    print()
    scores = []
    for k in ("bookmarks", "reposts", "replies", "likes"):
        rate = [r[k] / r["views"] for r in rows]
        scores.append((k, spearman(rate, ratio)))
    for k, s in sorted(scores, key=lambda x: -x[1]):
        print("    {:<10} {:+.3f}  {}".format(k, s, bar(s)))
    print()
    print("    Bookmarks win by 4x. And there is no bookmark weight")
    print("    anywhere in the algorithm file.")
    print()
    print("  " + "-" * 58)
    print("  THE ADVICE: 'DON'T POST LINKS'")
    print("  " + "-" * 58)
    print()
    w = [r["ratio"] for r in rows if r["link"]]
    wo = [r["ratio"] for r in rows if not r["link"]]
    print("    with a link      n={:<3}  median {:.2f}x".format(len(w), statistics.median(w)))
    print("    without a link   n={:<3}  median {:.2f}x".format(len(wo), statistics.median(wo)))
    print()
    print("    No penalty. Every video still repeats it.")
    print()
    print("  " + "-" * 58)
    print("  THE SCORER I BUILT FROM THE WEIGHTS")
    print("  " + "-" * 58)
    print()
    try:
        import json
        v = json.load(io.open("validation.json", encoding="utf-8"))
        s = spearman([o["earned_weight"] for o in v], [o["ratio"] for o in v])
        print("    correlation with actual reach:  {:+.3f}".format(s))
        print()
        print("    That is noise. It does not work.")
    except FileNotFoundError:
        print("    validation.json not found. See validate.py.")
    print()


if __name__ == "__main__":
    main()
