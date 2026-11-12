# x-ranking-check

The posts that traveled furthest were the ones people saved. Bookmarks tracked
reach more than twice as strongly as reposts and five times as strongly as
replies, while likes tracked it slightly negatively. X's published ranking code
has no value for bookmarks anywhere in it.

That came out of trying to do something else. X put the code behind its algorithm
on GitHub, so I pulled the engagement weights out of it, built a tool that grades
a draft post against them, and tested that tool against 42 real posts from six
founders under 50k followers.

The tool does not work. Here is everything, including the failure.

```
python findings.py
```

```
  42 posts.  6 accounts.  All under 50k followers.
  Each post measured against its OWN account's median views.

  WHICH ENGAGEMENT ACTUALLY TRACKS REACH

    bookmarks  +0.558  ######################
    reposts    +0.265  ##########
    replies    +0.099  ###
    likes      -0.060  ##

  THE ADVICE: "DON'T POST LINKS"

    with a link      n=30   median 1.00x
    without a link   n=12   median 0.98x
    (see the caveat below: this comparison is weaker than it looks)

  THE SCORER I BUILT FROM THE WEIGHTS

    correlation with actual reach:  -0.047
```

## Three things that came out of it

**Bookmarks track reach better than anything else, and there is no bookmark
weight anywhere in the file.** +0.558 against +0.265 for reposts, +0.099 for
replies and -0.060 for likes. Search `param.rs` for "bookmark" and you get
nothing. Whatever bookmarks are doing, they are not doing it through the
published weight table.

**The link penalty did not show up, but this sample cannot settle it.** 30 of the
42 posts contain a link, which means each account's median is mostly made of link
posts, so comparing link posts against that median is close to comparing them
against themselves. Comparing each account's link posts against its own non-link
posts is the honest test, and only 5 accounts have both kinds. The results are
7.27x, 8.72x, 0.43x, 0.89x and 1.75x. No penalty, and no pattern. Treat this as
"nothing showed up in 42 posts," not as evidence that links are free. There is no
link penalty term in the published weights, but a post with a link plausibly earns
fewer replies and reposts because readers leave, and those actions are what the
weights pay for.

**A text scorer built from the weights is worthless.** Spearman correlation
between earned weight and actual reach is -0.047, which is noise. Posts that beat
their account's median and posts that died scored the same. The weights are real;
reading a post's text is not enough to predict which actions people will take.

## Use it on your own posts

`findings.py` works on any CSV with these columns: account handle, post text,
views, likes, replies, reposts, bookmarks. No API key, no install beyond Python.

```
python findings.py my-posts.csv
```

It ranks your engagement types by how well each one tracks reach, measured
against each account's own median rather than raw counts, and splits your link
posts against your non-link posts per account. If your numbers disagree with
mine, that is the useful outcome. 42 posts from 6 accounts is a small sample and
I would rather see it broken than repeated.

## Method

Every post is measured as a ratio against **its own account's median views**,
never raw numbers. A post with 50,000 views on a 500,000-follower account is
below average for that account. Comparing raw view counts across accounts of
different sizes measures follower count, not post quality.

Spearman rank correlation throughout, because the distributions are heavily
skewed and rank is what matters.

## What the scorer does, and what it does not

`score.py` reads a draft and reports, action by action, whether the post gives a
reader a reason to take that action, then sums the **forfeited weight**.

It does not predict reach. X wrote a comment directly above the weight table
saying the weights multiply the *predicted probability* of an action, not raw
engagement counts, and they explicitly name reading the ratios as count
equivalences ("one report cancels 468 likes") as a misinterpretation. Any tool
claiming to score a post's virality from its text is lying. This one catches
forfeits, which is a smaller claim, and the validation above shows even that does
not survive contact with real data.

## Where the weights come from

`xai-org/x-algorithm`, file `home-mixer/params/param.rs`, pinned at commit
`f06f45adc055` (pushed 2026-11-11T03:52:56Z).

https://github.com/xai-org/x-algorithm/blob/f06f45adc055/home-mixer/params/param.rs#L416-L443

| Action | Weight |
|---|---|
| Share via copy link | 20.0 |
| Reply, between mutual follows | 15.0 boost |
| Reply | 5.0 |
| Quote | 5.0 |
| Share via DM | 5.0 |
| Follow author | 4.0 |
| Share | 2.118 |
| Repost | 1.0 |
| Like | 0.708 |
| Block author | -31.2 |
| Not interested | -53.07 |
| Mute author | -58.8 |
| Report | -234.0 |

Two caveats worth repeating anywhere these numbers get quoted. These are
`param!` declarations with remote config keys, so they are defaults that
production can override; they are the best public evidence available, not
confirmed live values. And the file moves: it was pushed to on Nov 7, Nov 10 and
Nov 11. Re-pin before citing it.

Also worth knowing, from that same comment: engagement only counts on posts the
algorithm actually served, so coordinating a pile-on from a group chat does
nothing for reach. And the report weight looks enormous because reports are over
a thousand times rarer than likes. Without a large multiplier the model could not
react to them at all.

## The data

`indie-founder-x-posts-2026-11-11.csv`, 42 posts from 6 accounts, collected
2026-11-11. Columns: handle, post URL, post text, views, likes, replies, reposts,
bookmarks. Every post ID was verified authentic by decoding its snowflake
timestamp (`(id >> 22) + 1288834974657` gives the post's creation time in
milliseconds) and checking it against the claimed date. Zero mismatches.

Engagement counts are as reported at collection time and have not been
independently re-checked post by post.

## Usage

```
pip install anthropic
export ANTHROPIC_API_KEY=...

python score.py "your draft post here"
python validate.py indie-founder-x-posts-2026-11-11.csv
python findings.py
```

`findings.py` makes no API calls and needs no key.

## Why this exists

I am trying to grow a study app on X and wanted to know whether the advice
everyone sells is grounded in anything. The weights are public. Most of the
advice is not derived from them.

MIT.
