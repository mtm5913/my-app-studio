# Conversation evidence

AI-drafted task summary, not a transcript or grade. It may be public. Use actual
short words or labeled paraphrases; disclose help and leave missing responses
pending. The learner reviews, corrects or removes new excerpts before commit/push.
Accuracy approval is not proof of understanding. Label simulated trials explicitly.

**Available conversation context:** This coaching chat.

## APP-001

- Prediction: Learner hopes soft greens and friendly wording “will give them a sense of safety and that the brand cares about them.”
- Check interpretation: Learner said the 390px no-overflow check “would catch if it would fit on a phone screen.” AI clarified that this concerns avoiding sideways scrolling at that tested width.
- Browser observation: Learner disliked “a friendly place” and requested Olive be described as a friend instead. Learner also requested “Bite by bite, we can figure it out together” below the main button. AI revised the copy accordingly; learner confirmed the revised wording felt closer to the intended companion.
- Keep decision: Learner said, “I feel better about keeping this homepage. It matches more of the companion vibe I had in mind.”
- Review: Learner reviewed the summarized APP-001 excerpts and authorized commit, push and PR in this chat.
- Help/gaps: Learner chose Olive, the Companion character and soft greens to feel like a caring buddy when sharing personal information (AI paraphrase). AI proposed the promise and homepage scope; learner approved. Earlier neutral-page observation: ivory/forest green and generic “a real application” wording. AI implements design and checks; branding does not establish data privacy. Learner reviewed these excerpts before publication.
- Evidence links / next step: [Issue #1](https://github.com/mtm5913/my-app-studio/issues/1); Olive homepage implemented. Full APP-001 checks passed after copy revisions (98 foundation + 2 acceptance + 2 Chromium). Learner interpretation, requested copy revisions and keep reason recorded; accuracy review recorded; PR and CI pending.

## APP-002

- Prediction: Learner wanted a preview without actions before login, login when an action is requested, a return to that action after login, and home after standalone login (AI paraphrase).
- Check interpretation: Asked about replaying a copied session cookie after logout, learner said “whether or not a user can get in after loggin out?” AI clarified that this tested rejection of the old session cookie.
- Browser observation: After AI requested a signup/login/logout trial and revisiting Member space, learner reported “it takes me back to log in screen.” This records the reported revisit result; no additional browser details are inferred.
- Keep decision: Learner said “keep this account flow, because it did what I intended.”
- Review: Learner reviewed the new APP-002 summary and approved commit, push and PR in this chat.
- Help/gaps: AI proposed a public sample preview separate from the guarded dashboard and exact internal return destinations; learner approved. AI reused prepared password/session/CSRF helpers and updated starter navigation assertions to the approved behavior without removing authentication assertions. No tracking actions implemented. Learner reviewed the excerpts before publication.
- Evidence links / next step: [Issue #3](https://github.com/mtm5913/my-app-studio/issues/3); Full explicit APP-002 and normal checks passed (110 foundation/navigation, 14 cumulative acceptance, 2 Chromium). Learner check interpretation, revisit observation and keep reason recorded. Accuracy review recorded; PR and CI pending.

## APP-003

- Prediction: Asked what should happen if a logged-in member requests the admin API directly, learner said “it should be denied.”
- Check interpretation: After seeing a direct member request return the expected 403, learner said it would catch “something wrong with the authorization.” AI clarified the specific missing-server-check bug that hiding navigation alone would leave open.
- Browser observation: As a member, learner reported “Your account has member access. This page is available to admins.” After AI used the trusted local command to promote the throwaway account and requested a refresh without logout, learner reported seeing “the admin page.”
- Keep decision: Learner said “keep this permission flow because it only allows users with admin access.”
- Review: Learner reviewed the new APP-003 excerpts and authorized commit, push and PR in this chat.
- Help/gaps: AI proposed an admin overview limited to usernames and roles; learner approved. AI explained 403 and implemented server checks using prepared helpers, tests and layout review. AI performed the local test-account promotion. Automated checks also covered downgrade with an existing session; no learner observation of downgrade is claimed.
- Evidence links / next step: [Issue #5](https://github.com/mtm5913/my-app-studio/issues/5); full APP-003 and normal checks passed (111 foundation, 18 cumulative contracts, 2 Chromium journeys). Accuracy review recorded; commit/PR and CI remain pending.
