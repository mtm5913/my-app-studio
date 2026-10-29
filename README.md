# IS373 App Studio

**Build a small web application with an AI coach—and understand why it works.**
Start with a working, neutral FastAPI page. Give it a brand, add accounts, then
enforce member/admin permissions. Each lesson ends with a visible result, actual
checks and a short GitHub record. Your decisions are still pending in this template.

This follows the [Server Studio](https://github.com/kaw393939/373_hosting).
That repository owns your server and proxy; this one owns your application.
Start locally here. Deployment into your existing server is a later agreed step.

## Start here · on your laptop

Work only to the first checkpoint for now. The later sections are references
for the coach to introduce when you need them.

1. Sign into GitHub, then on [this template](https://github.com/kaw393939/is373-app-studio), choose
   **Use this template → Create a new repository**. Create a public copy named
   `my-app-studio` in your own account; leave **Include all branches** off.
   Wait until your copy shows its README and files.
2. Use your usual class terminal and GitHub SSH setup. Replace `YOUR-USERNAME`,
   then run one command at a time:

   ```sh
   git clone git@github.com:YOUR-USERNAME/my-app-studio.git
   cd my-app-studio
   pwd
   git remote -v
   ```

   An empty clone can mean GitHub is still making the copy. Wait for its files
   to appear, then run `git pull --ff-only origin main` inside the clone. Ask your
   coach for help; do not invent missing project files.

3. Open this cloned folder as a **local project** in ChatGPT desktop/Codex or an
   AI agent that can read/edit local files and run terminal commands. Browser
   control is useful for review; browser access alone is insufficient. VS Code
   is optional. Start one chat:

   > Read README.md, AGENTS.md, SPEC.md and LEARNING.md. Confirm my folder and SSH remote, help me run setup, then guide me through APP-001 one small step at a time. Wait for my decisions, predictions and browser observations; do not invent my answers or complete all lessons at once.

4. Let the connected coach check Python **3.12+**, run `python3 studio.py setup`
   and help with actual errors. It prepares the environment, quality tools and
   Chromium. You do not need Node, local Docker, an IDE extension or another agent CLI.
   On Windows, if your class Python command is `python`, the coach confirms its
   version and uses it in place of `python3` below; no second Python install is needed.

5. In your original terminal, still in this clone, run:

   ```sh
   python3 studio.py run
   ```

   Open the address printed by the server, normally `http://127.0.0.1:8000`.
   Leave this terminal running; the agent uses its separate project terminal.

**First checkpoint:** you can see the neutral page and tell the coach one thing
you notice. Accounts and roles are deliberately unfinished; this is a starting
point, not a failed installation.

Saved Python changes restart the development app. Saved template, CSS and
JavaScript changes refresh the browser automatically. Unsaved edits do not
appear. A refresh can clear an unsent form. Press **Ctrl+C** in the running
terminal to stop it. For a plain preview, stop first and use
`python3 studio.py run --plain`. Refresh after template/CSS edits; after Python
edits, stop and restart the app too.
If the port is occupied, let the coach identify your earlier server or use
`python3 studio.py run --port 8001` and its printed address. Do not stop unrelated programs.

These commands run Python locally. GitHub Pages cannot run this FastAPI app.
Keep credentials, local SQLite files and signing keys out of Git and the chat.
Use throwaway local test accounts, not a password you use elsewhere.

## Three small lessons

Follow **Try → Decide → Build → Check → Keep** in the same chat. Finish one
lesson before starting the next; the coach reveals the next small action.

| Lesson | What you make | What you learn to explain |
|---|---|---|
| [APP-001 · Homepage](docs/lessons/01-homepage.md) | A branded FastAPI homepage and shared styles | How your choices serve a visitor, and what a check proves |
| [APP-002 · Accounts](docs/lessons/02-accounts.md) | Signup, login, a private dashboard and logout | How REST requests, hashed passwords and JWT sessions fit together |
| [APP-003 · Roles](docs/lessons/03-roles.md) | Member/admin access enforced on the server | Why a hidden button is insufficient and how a denied request proves a boundary |

Use your IS117 brand if it fits. Otherwise a name, visitor need, promise and one
brand archetype are enough; you are not repeating the whole branding assignment.
An archetype describes the brand's recurring character, not a customer stereotype.

For each lesson, agree a short scope, open **one issue in your own repository**,
work on its feature branch and review its PR. The agent builds, tests and reviews
first. You interpret one actual check, try the browser and decide whether to
keep or revise. You may adopt an AI suggestion; a short reason is enough.
“Yes” can approve a proposal, but it is not a prediction or browser observation.

The coach keeps agreed decisions and evidence links in [SPEC.md](SPEC.md), and
a short AI-drafted summary of your contributions and help in
[LEARNING.md](LEARNING.md). The summary is not a transcript or grade and may be
public: review, correct or remove excerpts **before commit/push**. Missing
answers stay pending. Timestamps and closed issues show recorded activity;
they do not establish authorship or understanding.

**Returning later:** reopen this same clone/chat. Ask the coach to read SPEC and
LEARNING and resume the newest unfinished stage. Its status checks the current
revision; older issues/PRs preserve the earlier completed work. Reuse a running server, or run
`python3 studio.py run` again. You normally do not clone or install again.

## Prepared checks and progress

`python3 studio.py check` runs Black, Pylint, pytest and real Chromium journeys
for the foundation and stages marked implemented. On a fresh template it checks
the foundation only; a green baseline does not mean accounts already work.

The coach runs `python3 studio.py check --lesson APP-001` for the current lesson's
cumulative acceptance checks. Unfinished lessons should fail these checks.
After the agreed implementation passes, the coach updates
`studio.json`'s `implemented_through` to that stage so CI keeps testing it, then
reruns the normal full check because the declaration changed.
Never raise that marker in place of implementing the feature, remove a failing
contract or weaken a check to get a pass. `check --fast` omits real-browser work;
it is useful while fixing a problem, but is not the full completion check.

Positive/negative describe **cases**, such as a correct password and a wrong
one. Unit/integration/E2E describe **levels**: one function, joined app/database
parts, or a complete browser journey. Passing assertions establish their tested
behavior, not a guarantee against every defect or a security certification.

The coach uses `python3 studio.py issue --lesson APP-001 --open` to open the
prepared GitHub form; without `--open` it prints the URL. After you create the
issue, it records the actual URL with `--url`; `--pr` records the actual PR.
No extra GitHub CLI is required. Template copies do not inherit instructor issues.
CI prepares clean environments. Wait for both `check` and `windows` in the PR;
after merging, wait for its main-branch checks before checking progress. Pending
CI is a wait, not a reason to clone again or rebuild the feature.
`python3 studio.py status --lesson APP-001` names the next recorded checkpoint;
it neither grades nor performs a merge or issue closure. It checks whether a
record is present, not whether its reasoning is correct. The coach must leave
missing explanations pending rather than filling them with an approval like “yes.”
On a shared class network, GitHub's API limit can leave status unverified even
when the signed-in browser works. Ask the coach to inspect the real issue, PR
and CI through an authenticated connector/browser; do not paste tokens or treat
that access limit as an application failure.

## Worked examples · when useful

The instructor's cumulative [homepage](https://github.com/kaw393939/is373-app-studio/tree/reference/app-001),
[accounts](https://github.com/kaw393939/is373-app-studio/tree/reference/app-002) and
[roles](https://github.com/kaw393939/is373-app-studio/tree/reference/app-003)
branches show **one possible solution**, not your chosen brand or your learning
record. Ask your coach to compare one relevant part when you need an example.
Browse them upstream; do not check them out over your work or copy their completed
evidence. Your template copy uses `main`, which keeps the student starting point.

[Security notes and primary sources](docs/security.md) explain the relevant
protections when the accounts and roles lessons reach them. No production
deployment, password recovery, email verification, payment system or extra
application feature is required in these three lessons.

[Instructor orientation and evaluation records](docs/instructor.md) are optional
background; students start with this README.
