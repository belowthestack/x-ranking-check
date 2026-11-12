"""
Score an X draft against the published ranking weights.

Weights read from xai-org/x-algorithm, home-mixer/params/param.rs,
pinned at commit f06f45adc055 (pushed 2026-11-11T03:52:56Z).

WHAT THIS DOES NOT DO: predict reach. X's own comment above the weight
table says the weights multiply the PREDICTED PROBABILITY of an action,
not raw counts, and explicitly calls out reading the ratios as count
equivalences as a misinterpretation. So this tool does not compute a
reach score. It reports which weighted actions the draft gives a reader
no reason to take, and what that forfeits.
"""
import argparse
import json
import os
import pathlib
import sys

PINNED = "f06f45adc055"

# (action, weight, what the post must do to give a reader a reason to take it)
EARNABLE = [
    ("Share via copy link", 20.0,
     "Contains something a reader would copy and send to a specific person: a "
     "number, a finding, a warning, a tool, a result. Not a feature announcement."),
    ("Reply", 5.0,
     "Asks something answerable, takes a position someone could push back on, or "
     "leaves an obvious gap a reader would want to fill. A statement nobody can "
     "respond to earns nothing here."),
    ("Quote post", 5.0,
     "Makes a claim a reader would want to put their own take on top of."),
    ("Share via DM", 5.0,
     "Useful to one specific person a reader knows, enough to send it privately."),
    ("Follow author", 4.0,
     "Suggests the author will keep producing things like this: shows expertise, "
     "an ongoing project, or a thread worth staying for."),
    ("Share", 2.118,
     "Worth passing on in any form."),
    ("Repost", 1.0,
     "A reader would put this in front of their own audience unchanged."),
    ("Like", 0.708,
     "Worth a tap. Nearly worthless in ranking, listed for completeness."),
]

# Negative weights. These are what a post RISKS, not what it earns.
RISKS = [
    ("Report", -234.0, "Reads as spam, a scam, or rule-breaking."),
    ("Mute author", -58.8, "Reads as repetitive noise someone would want out of their feed."),
    ("Not interested", -53.07, "Reads as off-topic or irrelevant filler."),
    ("Block author", -31.2, "Reads as hostile, baiting, or aggressive self-promotion."),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "earned": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "earned": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["action", "earned", "reason"],
                "additionalProperties": False,
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "triggered": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["action", "triggered", "reason"],
                "additionalProperties": False,
            },
        },
        "biggest_miss": {"type": "string"},
    },
    "required": ["earned", "risks", "biggest_miss"],
    "additionalProperties": False,
}

SYSTEM = """You judge draft social posts against a fixed rubric. You are strict.

Default to NOT earned. A post earns an action only if a real reader, scrolling
fast, who does not know or follow the author, would plausibly take that action.
Being well written is not enough. Being about a good product is not enough.

Never speculate about reach, impressions or virality. Judge only whether the
text gives a reader a reason to take each listed action.

Keep every reason under 20 words and concrete. Say what is missing, not what is
nice."""


def load_env():
    """Read keys from the environment, falling back to a .env file."""
    for p in (pathlib.Path.cwd() / ".env",):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def build_prompt(draft):
    earnable = "\n".join("- {} (weight {}): {}".format(n, w, c) for n, w, c in EARNABLE)
    risks = "\n".join("- {} (weight {}): {}".format(n, w, c) for n, w, c in RISKS)
    return (
        "DRAFT POST:\n---\n{}\n---\n\n"
        "For each action below, decide whether this draft gives a reader a reason "
        "to take it.\n\nACTIONS THE POST CAN EARN:\n{}\n\n"
        "RISKS THE POST CAN TRIGGER:\n{}\n\n"
        "Return a judgement for every action and every risk listed, using the exact "
        "names above. Then name the single biggest miss in one sentence."
    ).format(draft, earnable, risks)


def score(draft, client):
    resp = client.messages.create(
        model="claude-opus-5-5",
        max_tokens=4000,
        system=SYSTEM,
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[{"role": "user", "content": build_prompt(draft)}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def report(draft, data):
    weights = {n: w for n, w, _ in EARNABLE}
    total = sum(weights.values())
    got = sum(weights.get(e["action"], 0) for e in data["earned"] if e["earned"])
    lost = total - got

    print("\n" + "=" * 68)
    print(draft.strip()[:300])
    print("=" * 68)
    print("\n  EARNS {:.1f} of {:.1f} available weight.  FORFEITS {:.1f}.\n".format(
        got, total, lost))
    for e in sorted(data["earned"], key=lambda x: -weights.get(x["action"], 0)):
        mark = "OK  " if e["earned"] else "MISS"
        print("  [{}] {:>6.3f}  {}".format(mark, weights.get(e["action"], 0), e["action"]))
        if not e["earned"]:
            print("           {}".format(e["reason"]))
    fired = [r for r in data["risks"] if r["triggered"]]
    if fired:
        print("\n  RISKS TRIGGERED:")
        for r in fired:
            print("    {}: {}".format(r["action"], r["reason"]))
    print("\n  Biggest miss: {}\n".format(data["biggest_miss"]))
    print("  Weights pinned at xai-org/x-algorithm@{}".format(PINNED))
    print("  These weights multiply predicted probabilities, not raw counts.")
    print("  This is unclaimed upside, not a reach prediction.\n")


def main():
    ap = argparse.ArgumentParser(
        description="Score an X draft against the published ranking weights.")
    ap.add_argument("draft", nargs="?", help="the draft text; omit to read stdin")
    ap.add_argument("--file", help="score each non-empty line of a file")
    ap.add_argument("--json", action="store_true", help="emit raw JSON")
    args = ap.parse_args()

    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not (key or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No API key found. Set ANTHROPIC_API_KEY in the environment or a .env file")

    try:
        import anthropic
    except ImportError:
        sys.exit("pip install anthropic")

    client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()

    if args.file:
        lines = pathlib.Path(args.file).read_text(encoding="utf-8").splitlines()
        drafts = [line for line in lines if line.strip()]
    elif args.draft:
        drafts = [args.draft]
    else:
        drafts = [sys.stdin.read()]

    out = []
    for d in drafts:
        data = score(d, client)
        if args.json:
            out.append(dict(draft=d, **data))
        else:
            report(d, data)
    if args.json:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
