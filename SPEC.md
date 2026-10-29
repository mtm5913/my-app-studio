# App Studio decisions

The durable agreement between learner and AI. Update only agreed decisions and
actual evidence; pending is a valid state. Keep explanations/help in
[LEARNING.md](LEARNING.md), not a second copy here.

## Current stage

- **Current feature:** APP-002.
- **Status:** APP-001 merged in PR #2. APP-002 implementation and full local checks passed; learner interpretation, revisit observation and keep decision recorded. Summary reviewed and publication authorized; PR #4 open; full CI passed for the implementation commit, latest revision requires verification.
- **Next step:** Review [APP-002 PR #4](https://github.com/mtm5913/my-app-studio/pull/4) and latest Linux/Windows CI before a merge decision.
- **Implementation marker:** `studio.json` is now `implemented_through: 2` after passing the cumulative APP-002 contracts.

This repository owns application code. Server/proxy changes and production
deployment are outside these three local-development lessons. Prepared helpers
are reusable foundations, not evidence that unfinished routes are implemented.

## APP-001 · Branded homepage

**Scope:** make the neutral FastAPI homepage express one chosen identity with
a simple original SVG mark, coherent copy, navigation and shared style tokens.
Keep account actions honest about their unfinished state.

| Decision | Agreement |
|---|---|
| Visitor and concrete use situation | Someone managing their own blood sugar, viewing meals alongside readings to notice patterns. |
| Reused IS117 brand, or name / promise / primary archetype | New identity: Olive. Companion character. Promise: “A little support for noticing your everyday patterns.” |
| One visible choice and visitor benefit | Soft greens and friendly language: learner hopes visitors feel safe and cared for. No unimplemented privacy or medical claims. |
| Own issue / branch / PR | [Issue #1](https://github.com/mtm5913/my-app-studio/issues/1), branch `codex/app-001-olive`; [PR #2](https://github.com/mtm5913/my-app-studio/pull/2). |

**Keep when:** the agreed identity is visible and usable at desktop/narrow widths;
full foundation + APP-001 checks pass; AI review and the learner's actual check
interpretation/browser observation/keep reason are recorded; reviewed evidence
and verified GitHub state are linked below.

## APP-002 · Signup, login and logout

**Scope:** add browser forms and REST behavior for member signup, login, a private
dashboard and logout backed by SQLite. Reuse the prepared password/JWT/CSRF/session
helpers; keep data local. New accounts cannot choose their role.

| Decision | Agreement |
|---|---|
| Expected public/private behavior and account flow | Public /preview shows sample content only. /dashboard requires login and preserves next=/dashboard through login/signup. Standalone login returns /. Only / and /dashboard are allowed return destinations. Logout revokes the session server-side. |
| Valid and rejected cases to demonstrate | Valid member signup/login, malformed/duplicate/role-injected signup, wrong login, missing/cross-origin CSRF, anonymous/expired/revoked sessions, unsafe redirects and both login destinations. |
| Own issue / branch / PR | [Issue #3](https://github.com/mtm5913/my-app-studio/issues/3), codex/app-002-accounts; [PR #4](https://github.com/mtm5913/my-app-studio/pull/4). |

**Keep when:** the agreed forms/API work; duplicate/invalid signup and wrong
credentials are rejected; passwords are hashed; authentication uses validated,
expiring JWTs with protected cookies and CSRF; private requests require a live
session and logout revokes it. Full cumulative checks, AI review, actual learner
contributions and GitHub state are recorded. This is not a production-security certification.

## APP-003 · Server-enforced roles

**Scope:** enforce a small member/admin boundary in the API and browser. Assign
roles only through the trusted local terminal command; use current server-side
permissions, including for an existing session after a role change.

| Visitor | Homepage | Member area | Admin area/API |
|---|---|---|---|
| Anonymous | Allowed | Login required | Login required |
| Member | Allowed | Allowed | Forbidden |
| Admin | Allowed | Allowed | Allowed |

| Decision | Agreement |
|---|---|
| Intended admin-only result | Pending |
| Actual allowed/denied request evidence | Pending |
| Own issue / branch / PR | Pending |

**Keep when:** a direct request cannot bypass the role boundary, role changes
take effect as specified, new signup remains member-only, and full cumulative
checks plus AI review pass. Link the learner's actual interpretation/observation,
reviewed record and verified GitHub result. Hidden navigation alone is insufficient.

## Evidence

Link actual files/checks and the student's own issues/PRs. No fabricated URLs,
customer research or claims that a timestamp proves learning.

| Feature | Files / own issue / PR | Actual checks and learner observations | Kept / GitHub state |
|---|---|---|---|
| APP-001 | `app/brand.json`, `app/templates/home.html`, `app/templates/base.html`, `app/static/logo.svg`, `app/static/site.css`; [issue #1](https://github.com/mtm5913/my-app-studio/issues/1) | Full explicit APP-001 check passed, then normal full check passed after marker update: 98 foundation + 2 acceptance + 2 Chromium tests. AI reviewed desktop/narrow rendering, keyboard skip link and account boundary. Learner prediction and phone-width check interpretation recorded. Learner requested friend-focused copy and “Bite by bite, we can figure it out together,” then chose to keep the revised companion feel. | Keep decision recorded; summary reviewed; [PR #2](https://github.com/mtm5913/my-app-studio/pull/2) open. [Initial CI run](https://github.com/mtm5913/my-app-studio/actions/runs/40962891203): Linux passed at observation; Windows pending. Verify latest revision before merge |
| APP-002 | `app/features/accounts.py`, account/preview/dashboard templates, shared navigation/styles, `tests/test_account_navigation.py`; [issue #3](https://github.com/mtm5913/my-app-studio/issues/3) | Full explicit APP-002 check passed: 110 foundation/navigation tests, 14 cumulative contracts, 2 Chromium journeys. Normal full check after marker update also passed. AI reviewed account page desktop/390px layout, private boundary, input handling and safe returns. Starter redirect assertions intentionally changed for approved home/return behavior; auth/CSRF/revocation assertions retained. | Learner interpreted old-session rejection, reported returning to login on revisiting Member space after logout, and chose to keep the intended flow. Summary reviewed; [PR #4](https://github.com/mtm5913/my-app-studio/pull/4) open. [Full CI](https://github.com/mtm5913/my-app-studio/actions/runs/40965878512) passed check/windows for 2025fa3; verify latest revision before merge |
| APP-003 | Pending | Unfinished; explicit contracts not yet passed | Pending |

The instructor's reference branches show possible implementations. They do not
establish this repository's completion or the learner's own reasoning.
