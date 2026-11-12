"""
Validate the scorer against real posts with known outcomes.

Labels each post by how it did against ITS OWN account's median views, not by
raw numbers, because a post with 50k views from a 500k account is below average
for them. Then scores every post blind and checks whether the scorer's forfeited
weight separates the winners from the duds.

    python validate.py indie-founder-x-posts-2026-11-11.csv
"""
import csv
import io
import json
import os
import pathlib
import statistics
import sys
from collections import defaultdict

from score import EARNABLE, load_env, score

WEIGHTS = {n: w for n, w, _ in EARNABLE}
TOTAL = sum(WEIGHTS.values())

WIN = 2.0   # >= 2x the account's own median views
DUD = 0.7   # <= 0.7x


def label(ratio):
    if ratio >= WIN:
        return "WIN"
    if ratio <= DUD:
        return "DUD"
    return "MID"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "indie-founder-x-posts-2026-11-11.csv"
    rows = list(csv.DictReader(io.open(path, encoding="utf-8-sig")))

    by_account = defaultdict(list)
    for r in rows:
        r["views_n"] = int(str(r["views"]).replace(",", ""))
        by_account[r["account handle"]].append(r["views_n"])
    medians = {h: statistics.median(v) for h, v in by_account.items()}

    for r in rows:
        r["ratio"] = r["views_n"] / medians[r["account handle"]]
        r["label"] = label(r["ratio"])

    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY")
    import anthropic
    client = anthropic.Anthropic(api_key=key)

    out = []
    for i, r in enumerate(rows, 1):
        try:
            data = score(r["post text"], client)
        except Exception as exc:  # keep going; one bad row should not kill the set
            print("row {} failed: {}".format(i, exc), file=sys.stderr)
            continue
        got = sum(WEIGHTS.get(e["action"], 0) for e in data["earned"] if e["earned"])
        out.append({
            "handle": r["account handle"],
            "url": r["post URL"],
            "views": r["views_n"],
            "ratio": round(r["ratio"], 2),
            "label": r["label"],
            "earned_weight": round(got, 2),
            "forfeited": round(TOTAL - got, 2),
            "earned": [e["action"] for e in data["earned"] if e["earned"]],
            "biggest_miss": data["biggest_miss"],
            "text": r["post text"],
        })
        print("{:>3}/{}  {:<16} {:>5}x {:<4} earned {:>5.1f}".format(
            i, len(rows), r["account handle"], round(r["ratio"], 1), r["label"], got),
            file=sys.stderr)

    pathlib.Path("validation.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    groups = defaultdict(list)
    for o in out:
        groups[o["label"]].append(o["earned_weight"])
    for lab in ("WIN", "MID", "DUD"):
        vals = groups.get(lab, [])
        if vals:
            print("{:<4} n={:<3} mean earned weight {:>6.2f}   median {:>6.2f}".format(
                lab, len(vals), statistics.mean(vals), statistics.median(vals)))
    if groups.get("WIN") and groups.get("DUD"):
        gap = statistics.mean(groups["WIN"]) - statistics.mean(groups["DUD"])
        print("\nWIN minus DUD: {:+.2f} weight".format(gap))
        print("If that gap is near zero or negative, the scorer does not work.")
    print("\nwrote validation.json")


if __name__ == "__main__":
    main()
