# Lesson 02 · Make the account boundary real

**Goal:** add signup, login, a private dashboard and logout, then explain one
successful and one rejected request. Keep APP-001 first; use the same clone/chat.

## Try and decide

Agree APP-002's small scope and open its own issue/feature branch. New accounts
are members; signup cannot choose admin. Use throwaway local accounts and keep
passwords and session tokens out of Git and conversation records.

Before the plan, predict what a private request should receive before and after
login. The coach explains the relevant part when needed: FastAPI serves both
HTML and REST responses, SQLite stores users/sessions, a password hash avoids
storing the password, and a JWT signature is not encryption.

**Checkpoint:** SPEC names the intended account flow and rejected cases.

## Build

Review a short plan. Let AI connect the prepared helpers to forms and API routes:
signup, login, dashboard and logout. Reuse the prepared cookie/CSRF/session
protections; do not design cryptography or store JWTs in localStorage.

The session must expire and logout must revoke it on the server. Clearing a
browser cookie alone does not invalidate a copied token. Your local development
settings are not permission to expose the app publicly without HTTPS/configuration review.

The local `/docs` page maps implemented HTML and REST routes. FastAPI also
provides `/openapi.json`; `GET /api/me` should change from 401 to 200 after login.

## Check

AI runs APP-002's full cumulative checks and reviews actual behavior. Useful
cases include valid signup/login, duplicate or malformed signup, wrong credentials,
an unauthenticated private request, missing CSRF and a revoked/expired session.
The prepared tools distinguish unit helpers, joined app/database requests and
a real Chromium account journey.

Explain one actual result the coach shows. Then use your own browser to sign up,
log in, visit the private area and log out. Describe what you actually see when
you revisit the private area. Do not publish the account password or cookie.

**Checkpoint:** successful and rejected behavior is real evidence, not a hidden button.

## Keep

Decide whether to keep or revise and why. Review the short LEARNING summary,
link actual checks/files and merge the reviewed PR only after its full CI passes.
Verify the issue's completed scope, update local main and inspect progress.

Next, APP-003 asks what a logged-in member is allowed to do. A complete account
flow is not a claim of password recovery, email verification or production readiness.
