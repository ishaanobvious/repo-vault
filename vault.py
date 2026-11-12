#!/usr/bin/env python3
"""Repo Vault: keep the review table up to date and flag repos that look like traps.

Usage:
  python3 vault.py add owner/repo --verdict yes|hype|no|untested [--kw WORD] [--reel URL] [--note TEXT]
  python3 vault.py check owner/repo
  python3 vault.py scan [--days 7] [--min-stars 500] [--limit 30]
  python3 vault.py render

It uses the GitHub CLI (`gh`) when it's installed and signed in, which gives a higher
rate limit. Otherwise it calls the public GitHub API. Standard library only.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "vault.csv"
README = ROOT / "README.md"
FIELDS = ["id", "repo", "what", "stars", "verdict", "keyword", "reel", "reviewed", "note"]
VERDICTS = {
    "yes": "✅ Clearly yes",
    "hype": "🤔 Clearly hype",
    "no": "⛔ Clearly not",
    "untested": "⚪ Untested",
}
BAIT = re.compile(
    r"\b(full[ -]?version|activated|activation|crack(ed)?|keygen|all features (enabled|unlocked)|"
    r"pre-?configured|unlocked|portable setup|standalone (desktop )?setup|full[ -]feature|"
    r"nothing held back|trainer tool|executor)\b",
    re.I,
)
PAID = re.compile(
    r"\b(adobe|acrobat|photoshop|premiere pro|illustrator|after effects|lightroom|cubase|ableton|"
    r"fl studio|kontakt|autodesk|autocad|inventor|archicad|solidworks|dxo|ninjatrader|metatrader|"
    r"aomei|easy-?worship|directory[ -]opus|display ?fusion|daemon[ -]?(tools|pro)|substance 3d|camtasia|"
    r"filmora|coreldraw|microsoft office|office 365|windows activator|clion|matlab|aida ?64)\b",
    re.I,
)
PS_ONELINER =re.compile(r"(irm|iwr|invoke-webrequest|invoke-restmethod)[^\n]{0,200}\|\s*iex", re.I)
FAKE_BADGE = re.compile(r"(downloads?|rating|score|stars)-[0-9.,]+[kKmM]?(%2F5|/5)?-", re.I)


# ---------- GitHub access ----------

def api(path: str):
    """GET a GitHub API path, returning parsed JSON (or None on 404)."""
    if shutil.which("gh"):
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        if "404" in r.stderr or "Not Found" in r.stderr:
            return None
    req = urllib.request.Request(
        "https://api.github.com/" + path.lstrip("/"),
        headers={"Accept": "application/vnd.github+json", "User-Agent": "repo-vault-script"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        sys.exit(f"GitHub API error {e.code} for {path}: {e.reason}")


def days_since(iso: str) -> int:
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - t).days


def short(n: int) -> str:
    if n >= 1000:
        s = f"{n / 1000:.1f}".rstrip("0").rstrip(".")
        return s + "K"
    return str(n)


# ---------- trap check ----------

def check(full_name: str) -> dict:
    repo = api(f"repos/{full_name}")
    if not repo:
        sys.exit(f"Repo not found: {full_name}")
    owner = api(f"users/{repo['owner']['login']}") or {}
    readme_obj = api(f"repos/{full_name}/readme")
    readme = ""
    if readme_obj and readme_obj.get("content"):
        readme = base64.b64decode(readme_obj["content"]).decode("utf-8", "replace")
    contents = api(f"repos/{full_name}/contents") or []
    names = {c.get("name", "").lower() for c in contents} if isinstance(contents, list) else set()

    stars, forks = repo["stargazers_count"], repo["forks_count"]
    repo_age, owner_age = days_since(repo["created_at"]), days_since(owner.get("created_at", repo["created_at"]))
    flags, notes = [], []

    if stars >= 300 and forks * 100 < stars:
        flags.append(f"Stars without forks: {stars:,} stars, {forks:,} forks")
    if owner_age <= 30:
        flags.append(f"Owner account is {owner_age} days old")
    if owner.get("public_repos", 99) <= 1 and stars >= 1000:
        notes.append("Owner has only this one public repo")
    text = f"{repo['name']} {repo.get('description') or ''}"
    if BAIT.search(text):
        flags.append(f"Paid-software bait in the name or description: \"{BAIT.search(text).group(0)}\"")
    brand = PAID.search(text)
    if brand and re.sub(r"\W", "", brand.group(0).lower())[:5] not in repo["owner"]["login"].lower():
        flags.append(f"Names paid software it doesn't own: \"{brand.group(0)}\"")
    if PS_ONELINER.search(readme):
        flags.append("README tells you to pipe a download into PowerShell (… | iex)")
    if re.search(r"password[^\n]{0,40}(zip|rar|archive|extract)|(zip|rar|archive)[^\n]{0,40}password", readme, re.I):
        flags.append("README mentions a password-protected archive")
    if repo_age <= 30 and FAKE_BADGE.search(readme):
        flags.append(f"Download or rating badges on a {repo_age}-day-old repo")
    code_like = {n for n in names if not n.startswith(".")} - {"readme.md", "index.html", "files", "docs", "license", "public"}
    if names and not code_like:
        flags.append("No source code, only a README, a web page and a files folder")
    if not repo.get("license"):
        notes.append("No license")
    if stars >= 1000 and repo.get("open_issues_count", 0) == 0 and repo_age <= 60:
        notes.append("No issues despite the stars")
    if repo_age <= 14 and stars >= 1000:
        notes.append(f"Fast riser: {stars:,} stars in {repo_age} days. Not bad by itself, but check the rest.")

    n = len(flags)
    summary = "No red flags found. Still read what it runs." if n == 0 else (
        "Slow down and check it carefully." if n <= 2 else "Looks like a trap. Don't install it.")
    return {
        "repo": repo, "flags": flags, "notes": notes, "summary": summary,
        "repo_age": repo_age, "owner_age": owner_age,
    }


def print_check(res: dict) -> None:
    r = res["repo"]
    print(f"\n{r['full_name']}  ·  {r['stargazers_count']:,}★  {r['forks_count']:,} forks  ·  "
          f"repo {res['repo_age']}d old, owner {res['owner_age']}d old")
    if r.get("description"):
        print(f"  {r['description'][:120]}")
    for f in res["flags"]:
        print(f"  ⛔ {f}")
    for n in res["notes"]:
        print(f"  ·  {n}")
    print(f"  → {res['summary']}")


# ---------- vault table ----------

def load() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def render(rows: list[dict]) -> None:
    lines = ["| # | Repo | What it does | ★ at review | Verdict | Keyword | Reel | Reviewed |",
             "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: int(x["id"]), reverse=True):
        if r["verdict"] == "no":
            repo = f"{cell(r['repo'])} *(not linked)*"
        else:
            repo = f"[{cell(r['repo'])}](https://github.com/{r['repo']})"
        what = cell(r["what"]) + (f" *{cell(r['note'])}*" if r.get("note") else "")
        reel = f"[watch]({r['reel']})" if r.get("reel") else ""
        kw = f"`{cell(r['keyword'])}`" if r.get("keyword") else ""
        lines.append(f"| {int(r['id']):03d} | {repo} | {what} | {short(int(r['stars']))} | "
                     f"{VERDICTS[r['verdict']]} | {kw} | {reel} | {r['reviewed']} |")
    if not rows:
        lines.append("| | *First reviews land this week.* | | | | | | |")
    table = "\n".join(lines)
    text = README.read_text(encoding="utf-8")
    new = re.sub(r"(<!-- vault:start -->)(.*?)(<!-- vault:end -->)",
                 lambda m: f"{m.group(1)}\n{table}\n{m.group(3)}", text, flags=re.S)
    README.write_text(new, encoding="utf-8")


def add(args) -> None:
    repo = api(f"repos/{args.repo}")
    if not repo:
        sys.exit(f"Repo not found: {args.repo}")
    rows = load()
    existing = next((r for r in rows if r["repo"].lower() == repo["full_name"].lower()), None)
    row = existing or {"id": str(max([int(r["id"]) for r in rows] or [0]) + 1)}
    row.update({
        "repo": repo["full_name"],
        "what": args.what or (existing or {}).get("what") or (repo.get("description") or "")[:110],
        "stars": str(repo["stargazers_count"]),
        "verdict": args.verdict,
        "keyword": (args.kw or (existing or {}).get("keyword") or "").upper(),
        "reel": args.reel or (existing or {}).get("reel", ""),
        "reviewed": args.date or (existing or {}).get("reviewed") or date.today().isoformat(),
        "note": args.note if args.note is not None else (existing or {}).get("note", ""),
    })
    if not existing:
        rows.append(row)
    save(rows)
    render(rows)
    print(f"{'Updated' if existing else 'Added'} #{int(row['id']):03d} {row['repo']} "
          f"({short(int(row['stars']))}★, {VERDICTS[row['verdict']]})")
    if args.verdict != "no":
        res = check(repo["full_name"])
        if res["flags"]:
            print("Heads up, the trap check found:")
            for f in res["flags"]:
                print(f"  ⛔ {f}")


def scan(args) -> None:
    since = (date.today() - timedelta(days=args.days)).isoformat()
    data = api(f"search/repositories?q=created:%3E{since}+stars:%3E{args.min_stars}"
               f"&sort=stars&order=desc&per_page={args.limit}")
    for item in (data or {}).get("items", []):
        stars, forks = item["stargazers_count"], item["forks_count"]
        quick = []
        if stars >= 300 and forks * 100 < stars:
            quick.append("stars>>forks")
        text = f"{item['name']} {item.get('description') or ''}"
        if BAIT.search(text) or PAID.search(text):
            quick.append("paid-software bait")
        tag = ("  ⛔ " + ", ".join(quick)) if quick else ""
        print(f"{stars:>7,}★ {forks:>6,}⑂  {item['full_name']:<42} {(item.get('description') or '')[:70]}{tag}")
    print("\nRun `vault.py check owner/repo` on anything before you film it.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add or update a reviewed repo")
    a.add_argument("repo")
    a.add_argument("--verdict", required=True, choices=VERDICTS)
    a.add_argument("--kw", help="comment keyword from the reel")
    a.add_argument("--reel", help="Instagram reel URL")
    a.add_argument("--what", help="what it does, in a few words (default: repo description)")
    a.add_argument("--note", help="short catch or caveat")
    a.add_argument("--date", help="review date, YYYY-MM-DD (default: today)")
    c = sub.add_parser("check", help="red-flag report for a repo")
    c.add_argument("repo", nargs="+")
    s = sub.add_parser("scan", help="new fast-rising repos, with quick flags")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--min-stars", type=int, default=500)
    s.add_argument("--limit", type=int, default=30)
    sub.add_parser("render", help="rebuild the README table from data/vault.csv")
    args = p.parse_args()

    if args.cmd == "add":
        add(args)
    elif args.cmd == "check":
        for r in args.repo:
            print_check(check(r))
    elif args.cmd == "scan":
        scan(args)
    else:
        render(load())
        print("README table rebuilt.")


if __name__ == "__main__":
    main()
