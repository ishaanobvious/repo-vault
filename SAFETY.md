# The 60-second repo check

Run this before you install anything from GitHub, especially if a reel, a post or an AI agent told you about it.

Stars can be bought. In 2026, researchers found thousands of fake repos posing as AI tools and MCP servers, and many of them had hundreds or thousands of stars. Checking the star count alone tells you very little.

## The checks

| # | Check | Where to look | Red flag |
|---|---|---|---|
| 1 | **Stars vs forks** | Top right of the repo page | 1,000+ stars and almost no forks. Real projects get forked by people who use them. |
| 2 | **How old is the owner's account** | Click the owner's name | The account is days or weeks old, has 1 repo, and the repo blew up overnight. |
| 3 | **What it promises** | Repo name and description | Paid software that's "full version", "all features unlocked", "activated" or "pre-configured". That's a cracked-software lure. |
| 4 | **How it installs** | README, "Install" section | "Paste this PowerShell command" (`irm ... \| iex`), a password-protected zip, or a download link that leaves GitHub. |
| 5 | **Fake proof** | README badges | "93K downloads" or "4.9/5 rating" badges on a repo that's a few days old. Anyone can make a badge say anything. |
| 6 | **Is there real code** | The file list | Only a README, an `index.html` and a "files" folder, with no source you can actually read. |
| 7 | **License** | Right sidebar | No license at all. That's not proof of anything bad, but you can't legally use the code, and it often means low effort. |
| 8 | **Issues and activity** | Issues tab, commit history | Thousands of stars and no issues. Real users report bugs. |

## How to read the result

- **0 red flags:** no warning signs. You still need to read what it runs before you give it access to your files or accounts.
- **1–2 red flags:** slow down. Look for the same project on the maker's X or website, and check that the links match.
- **3 or more:** treat it as a trap. Don't download it, and don't hand it to your AI agent.

## Let a script do it

`vault.py check owner/repo` in this repo runs checks 1–5, 7 and 8 automatically:

```bash
python3 vault.py check owner/repo
```

It isn't a malware scanner. It points out warning signs. A clean result doesn't mean a repo is safe.

---

From [@ishaan.clearlyy](https://www.instagram.com/ishaan.clearlyy/): I install the AI repos blowing up on GitHub, so you know what works, what's hype and what's a trap.
