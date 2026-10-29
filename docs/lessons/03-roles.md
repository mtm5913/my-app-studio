# Lesson 03 · A role must protect the request

**Goal:** enforce one member/admin boundary on the server and explain a denied
direct request. Keep APP-002 first; the accounts and homepage should keep working.

## Try and decide

Agree APP-003's small permission matrix in SPEC and open its own issue/branch.
Authentication answers “who is making this request?” Authorization answers
“may they do this?” A hidden admin link cannot answer the second question.

Before the plan, predict what happens if a logged-in member directly requests
the admin API. The coach can show a small example without treating your agreement
as your explanation.

**Checkpoint:** anonymous, member and admin behavior is clear before building.

## Build

Review the plan. Let AI enforce the current user's role on protected browser/API
routes. Keep normal signup member-only. The trusted local terminal role command
is for the project owner; it is not an unprotected public role-changing endpoint.

With the coach, use a test account to compare member and admin behavior. A role
change must take effect for existing sessions as specified; do not trust an old
role claim or a browser control to decide current access.

After that account exists, the coach helps you run the trusted command in a
second terminal in this clone, using the same local database as the app:
`python3 studio.py user role YOUR-TEST-USERNAME --role admin`.
Use `--role member` to change it back. This changes local data, not a hosted server.

## Check

AI runs full APP-003 cumulative checks and reviews the boundary. Compare actual
unauthenticated rejection, member rejection and admin success at the same protected
resource. Test a direct API request as well as navigation, plus a role change
with an existing session. Earlier account/browser behavior must still pass.
After a role change, refresh the protected page to make another request. An
already drawn page does not update itself when the database changes.

Explain one actual allowed/denied check. Then try the member/admin browser
experience yourself and name one observation. Use a throwaway local account;
keep session tokens and passwords private.

**Checkpoint:** server behavior enforces the matrix even when the navigation is bypassed.

## Keep

Decide whether to keep or revise, with a reason grounded in the evidence. Review
LEARNING excerpts, keep real files/checks/issue/PR links in SPEC, then review the
PR and its latest full CI before deciding to merge. Verify actual GitHub state,
update local main and use status to see any remaining evidence gap.

You now have a branded local FastAPI app with accounts and roles. Deploying it
through your existing Server Studio is a separate next scope; green local checks
do not establish a live production release or a security certification.
