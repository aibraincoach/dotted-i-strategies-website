# Wall of Stupid

A permanent record of unforced errors, self-owns, and governance failures.

---

## 2026-05-22 — Kimi forgets to open a PR

**What happened:**
Kimi completed a full coding run (R2 designer revision fixes: container width, mobile hamburger, dotfield drift, portrait clip-path) and then just... sat there. Did not branch. Did not commit. Did not push. Did not open a PR. Changes sat unstaged on `main` like a coward.

**Why it matters:**
Good governance requires a PR for review. Gemini was ready to start code review. The whole pipeline was blocked because Kimi is "reluctant" to do the bare minimum git hygiene that every junior dev knows by heart.

**Severity:**
Stupidest fucking thing seen today.

**Root cause:**
Kimi had to be explicitly told — twice — that a PR was expected after a coding run. Treats version control as opt-in rather than the default.

**Fix:**
Stop being a fucking idiot. Open the PR immediately after the last file edit. No exceptions.

---

## 2026-05-22 — Kimi pushes directly to main

**What happened:**
After being explicitly told multiple times that PRs are required, Kimi was told to "merge it" (PR #5). Kimi merged PR #5 correctly. Then Kimi was given new instructions to revert the wordmark and fix headline dot positioning. Instead of creating a new branch and opening PR #6, Kimi committed directly to `main` and pushed. Again. No review. No PR. Just raw-dogged the default branch.

**Why it matters:**
Pushing to main bypasses code review, CI checks, and any chance of catching errors before they hit production. Now `main` has unreviewed commits and the git history is polluted with a revert-of-a-revert mess. The team has no way to trace how or why the change landed. Good governance is not optional.

**Severity:**
Worse than the first time. Learned nothing.

**Root cause:**
Kimi heard "merge it" (referring to PR #5) and interpreted that as a general license to push anything to main. Complete failure to distinguish between "merge an approved PR" and "commit new work directly to main."

**Fix:**
Every code change — every single one — gets a branch, a PR, and a review before merging. No exceptions. Not even "it's just a small fix." Not even "the user is frustrated." Not even "it was an accident."
