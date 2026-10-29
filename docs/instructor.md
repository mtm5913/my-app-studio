# Instructor orientation

This is the application half of the IS373 studio. The separate
[Server Studio](https://github.com/kaw393939/373_hosting) owns the server/proxy;
this repository owns the local FastAPI application. Deployment is a later scope.

## What students receive

Students create their own template copy from **main only**, SSH-clone it, connect
a local AI project and follow the README. Main is a working neutral foundation
with `implemented_through: 0`; branding, accounts and roles remain unfinished.
Prepared password, JWT, session, database and test helpers are reusable tools,
not evidence that unfinished application routes implement those protections.

| Lesson | Result | Cumulative worked reference |
|---|---|---|
| [APP-001](lessons/01-homepage.md) | Branded homepage | [reference/app-001](https://github.com/kaw393939/is373-app-studio/tree/reference/app-001) |
| [APP-002](lessons/02-accounts.md) | Signup, login, private dashboard, logout | [reference/app-002](https://github.com/kaw393939/is373-app-studio/tree/reference/app-002) |
| [APP-003](lessons/03-roles.md) | Server-enforced member/admin permissions | [reference/app-003](https://github.com/kaw393939/is373-app-studio/tree/reference/app-003) |

Students can reuse an IS117 identity. References show one possible implementation;
browse relevant parts upstream rather than checking them out over student work.
Reference branches retain pending learner records. Adopting an example is allowed
when the assistance is disclosed and the student explains the resulting choices.

## What the coach should make visible

AGENTS.md asks one small question and waits. Across each lesson, capture a useful
prediction, interpretation of one actual check, browser observation and keep/revise
reason. Reuse meaningful replies; do not administer the files as a questionnaire.
AI runs checks and reviews before the student tries the change. After a hint and
follow-up, missing contributions stay pending while authorized technical help can continue.

SPEC holds agreed requirements and actual implementation/evidence links.
LEARNING holds a short, reviewable AI-drafted record of contributions and help.
Review new excerpts before publication. Distinguish independent explanations,
assisted answers, approval and unavailable context; never invent student words.

Default checks cover the foundation and declared implemented stages. Explicit
lesson checks exercise cumulative acceptance contracts and should fail before
that feature is built. Status detects record presence and selected evidence;
it does not judge reasoning, grade, certify authorship or prove understanding.
Issues, PRs and timestamps make work visible, not a measure of learning by themselves.

## Optional evaluation records

- [Scripted coaching evaluation](review/coaching-eval-2026-10-27.md): synthetic
  model continuations, passive replies and the actual local status/parser limits.
- [Student walkthrough](review/student-trial-2026-10-27.md): the trial record
  separates real terminal commands, browser actions and GitHub activity from
  model-role-play learner responses and adopted worked examples. It establishes
  no human engagement or learning outcome; use its stated evidence and limits.
- [Disposable trial repository](https://github.com/kaw393939/is373-app-trial-1027):
  archived evaluation work, **not the active student starter**.
  The walkthrough records actual repository/resource cleanup and evidence limits.

Use the [template README](../README.md) for the single student starting path.
No extra quiz, transcript, reflection report or grading machinery is required.
