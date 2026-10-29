# Security notes · read at the point of use

The starter supplies reusable helpers so you can focus on connecting and checking
the account flow. A helper's tests do not prove that a route actually uses it.
Your coach should explain the relevant boundary and show its actual request test.

- **Password hashing:** store a slow password hash, not a plaintext password.
  [FastAPI's security tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
  introduces password hashing, token creation and current-user dependencies.
- **JWT validation:** the signature is not encryption. Validate the signature,
  expiry and required claims with a fixed permitted algorithm; do not let the
  token choose how it is verified.
  [PyJWT's API reference](https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode)
  explains the verification options and algorithm warning.
- **Browser sessions:** an HttpOnly cookie limits JavaScript access; Secure
  protects cookie transport over HTTPS. Cookie attributes do not replace expiry
  and server-side revocation.
  [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
  explains these separate protections.
- **CSRF:** browsers can send cookies automatically. State-changing requests need
  the prepared CSRF protection; SameSite is a defense layer, not a universal
  substitute. See
  [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
- **Roles:** evaluate current permissions on every protected request; a link's
  visibility or an old role value is insufficient. The lesson's permission
  matrix belongs in SPEC and must be exercised by actual request tests.

Local loopback development and production HTTPS have different configuration.
Keep local signing keys, SQLite data and test credentials ignored. Do not reuse
real passwords or publish raw tokens/browser state. These lessons cover a bounded
learning application; they do not provide every operation a public identity
service needs, such as recovery, verification, abuse response and ongoing maintenance.

The prepared throttles limit local signup/login attempts. A later public deployment
needs reviewed proxy/client-IP handling, ingress limits and a dedicated private
database directory. The default ignored runtime directory is prepared for local use.
