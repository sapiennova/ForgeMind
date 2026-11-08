# ForgeMind backend security

## Authentication boundary

Every request under the `/api/` namespace is centrally guarded by HTTP Bearer API-key authentication, so adding a future operational router under that namespace does not silently omit the boundary. Current routers also declare the reusable authentication dependency as defense in depth. Configure
`FORGEMIND_API_KEY` with a unique, randomly generated value of at least 32 bytes.
Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. The comparison uses constant-time `hmac.compare_digest`. This bootstrap key has no built-in expiry, per-client revocation, or overlapping rotation; rotate it through the secret manager and redeploy. The key is read from the
process environment and is never returned by an endpoint. If it is absent outside
production, operational requests fail with 503; they are never anonymously admitted.
Production startup rejects a missing or short key.

This initial shared API key is a bootstrap access boundary, not user identity,
tenant isolation, or role-based authorization. Anyone holding the key receives the
same API-level access. Do not issue one shared key to unrelated organizations.
Before multi-tenant use, add authenticated principals, organization membership,
resource-scoped authorization, and tenant filters to every database query. UUIDs
are identifiers, not authorization controls. Until then, deploy for one trusted
administrative boundary only.

## Configuration

See `backend/.env.example` for placeholders. Required production values:

- `FORGEMIND_ENV=production`
- `FORGEMIND_API_KEY`: unique random secret, at least 32 bytes.
- `FORGEMIND_ALLOWED_HOSTS`: exact comma-separated DNS hostnames.
- `FORGEMIND_CORS_ORIGINS`: optional exact browser origins; empty is safest when
  no browser client is deployed.
- `FORGEMIND_MAX_REQUEST_BYTES`: request body cap, default 1 MiB.
- `DATABASE_URL`: only when database-backed features are deployed; store it in
  the deployment secret manager, not in source control.

Do not use wildcard hosts or CORS origins. CORS is a browser policy, not
authentication, a firewall, or protection against direct HTTP clients. The API
key should be supplied over TLS only. Rotate it through your secret manager and
restart/redeploy the service; do not place it in URLs, query parameters, logs,
browser code, or source control.

## Source repository visibility

The GitHub repository is currently public. Application authentication, CORS, and
network controls protect the deployed API; they cannot stop people or automated
crawlers from cloning source code from a public GitHub repository. Restricting
source cloning requires changing repository visibility to private and managing
GitHub collaborator access. This is a separate GitHub setting, not a backend
security feature.

## Network and deployment

Run the service on a private interface behind a maintained reverse proxy or API
gateway, VPN, or private network. Restrict ingress with firewall/security-group
rules to approved gateway and administration networks. Terminate TLS at a trusted
gateway, configure forwarded-header handling only for known proxy addresses, and
use HTTPS end-to-end where feasible. Do not expose the development server or
assume CORS makes a public endpoint private. Configure gateway-level connection
limits, timeouts, request-body limits, concurrency limits, and per-client rate
limits. A starting Nginx example is provided at
`deploy/nginx/forgemind.conf.example`: it applies 120 requests/minute per source
IP with a burst of 30 and a 20-connection cap. Tune these values to the sensor
reporting cadence and expected NAT concentration before production. Nginx shares
its zone across workers in one gateway instance, not across multiple gateway
instances. A shared rate-limit store (for example Redis) or a managed gateway
with global distributed limits is required for consistent enforcement across
multiple gateway replicas. ForgeMind deliberately does not claim an in-process
limiter is production-safe.

The application enforces a body-size cap, validates Host headers, disables
interactive docs/OpenAPI in production, adds defensive response headers, and
returns generic unexpected-error responses. Health is an unauthenticated minimal
liveness probe; do not add infrastructure diagnostics to it. HSTS is emitted by the Nginx example at the TLS termination point, avoiding duplicate headers behind TLS termination. Ensure TLS termination and proxy configuration are correct before relying on HSTS.

## Monitoring and operations

Send application logs to a restricted log sink. Protect access to logs and avoid
logging authorization headers, API keys, request bodies containing sensitive
industrial data, or database connection strings. Configure alerting for repeated
401/403/413/429/5xx responses at the gateway. Apply secret scanning and dependency
updates to the repository. Enable GitHub secret scanning and push protection where
available for the repository plan.

## Deferred security work

- User accounts, token issuance/rotation endpoints, MFA, roles, and organization
  membership.
- Organization/plant/line/machine/sensor-level authorization and tenant-safe
  query scoping.
- Shared distributed rate limiting and gateway-specific WAF/DoS protections.
- Audit-event storage, key identifiers, overlapping key rotation, and revocation.
- Database TLS, least-privilege database roles, backup encryption, and production
  migration/restore procedures.
- Formal threat modelling, penetration testing, and deployment-specific review.

This foundation reduces common application risks; it is not a certification or a
claim of production-grade security by itself.

## Secret-scan baseline review

The earlier automated finding in `tests/test_security.py` was reviewed as a false positive: it came from a deliberately weak test-only candidate used to verify that production configuration rejects weak API keys. It was not a credential. The test candidate is now constructed without a scanner-triggering literal, and the current scan no longer reports it. The tracked `.secrets.baseline` records this review decision; it contains no active suppression entries. New findings therefore remain blocking unless an exact fingerprint is reviewed, documented, and explicitly marked `is_secret: false` in the baseline.
