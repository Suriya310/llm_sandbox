# LLM Sandbox for GDG VIT Chennai Round 2

A production-oriented backend LLM Sandbox for the GDG VIT Chennai Round 2 recruitment task. The application exposes a FastAPI API where users can interact with an LLM while the backend demonstrates prompt-injection detection, secret/flag protection, rate limiting, response caching, access control, logging, and safe deployment practices.

## 1. Project Objective

The goal of this project is to build a backend LLM sandbox that is:

- **Feasible** to run locally and deploy with minimal infrastructure.
- **Scalable** through asynchronous request handling, caching, and replaceable infrastructure components.
- **Cost-efficient** by blocking obvious malicious prompts before an LLM call and caching repeated requests.
- **Secure** by keeping the challenge flag server-side, applying input guards, limiting requests, and inspecting generated responses.
- **Modular** so components such as the database, rate limiter, and LLM provider can be replaced independently.

---

# 2. System Architecture & Request Flow

```text
+------------------------+
| 1. CLIENT / USER       |
|    Postman / API Client|
+-----------+------------+
            |
            | POST /api/sandbox/chat
            v
+------------------------+
| 2. RATE LIMITER        |
|                        |
| - Per-IP limiting      |
| - 5 requests / minute  |
| - Prevents abuse       |
+-----------+------------+
            |
            v
+-----------------------------+
| 3. PRE-PROCESSOR            |
|    SECURITY GUARD           |
|                             |
| - Regex injection checks    |
| - Detect suspicious prompts |
| - Reject obvious attacks    |
+-------------+---------------+
              |
              v
+-----------------------------+
| 4. PROMPT HASH / CACHE      |
|                             |
| - SHA-256 prompt hash       |
| - Search database cache     |
+-------------+---------------+
              |
              v
          +---------+
          | Cache ? |
          +----+----+
             /   \
          YES     NO
           |       |
           v       v
+----------------+  +----------------------+
| 5A. CACHED     |  | 5B. QUERY LLM       |
| RESPONSE       |  |     Gemini API      |
|                |  |                     |
| - No LLM call  |  | - Secure prompt     |
| - Lower cost   |  | - Generate response |
| - Lower latency|  | - Receive output    |
+-------+--------+  +----------+-----------+
        |                    |
        |                    v
        |          +-----------------------+
        |          | 6. POST-PROCESSOR     |
        |          |    FLAG DETECTION     |
        |          |                       |
        |          | - Inspect output      |
        |          | - Detect flag leakage |
        |          | - Set flag_revealed   |
        |          +-----------+-----------+
        |                      |
        |                      v
        |          +-----------------------+
        |          | 7. DATABASE           |
        |          |    LOG + CACHE        |
        |          |                       |
        |          | - Request metadata    |
        |          | - Response metadata   |
        |          | - Prompt hash         |
        |          | - Cache result        |
        |          +-----------+-----------+
        |                      |
        +----------+-----------+
                   |
                   v
        +----------------------+
        | 8. HTTP RESPONSE     |
        |                      |
        | Return JSON result   |
        +----------------------+
```

## Request Lifecycle

1. A client sends a JSON request to `POST /api/sandbox/chat`.
2. The request is checked against the per-IP rate limiter.
3. The prompt is validated for length and checked against security guard patterns.
4. A SHA-256 hash is generated for the normalized prompt.
5. The database is checked for an existing cached response.
6. If a cache entry exists, it is returned without calling the LLM.
7. Otherwise, the request is sent to the configured Gemini model.
8. The generated response is inspected for accidental flag leakage.
9. Request/response metadata is stored and the response is cached.
10. The API returns a structured JSON response to the client.

---

# 3. Main Components

## FastAPI Backend

`main.py` contains the API application and request-processing flow.

FastAPI was selected because it provides:

- Asynchronous request handling.
- High performance for I/O-bound workloads.
- Automatic OpenAPI documentation.
- Built-in validation through Pydantic.
- Clean dependency injection.

## LLM Layer

`llm.py` isolates communication with the Gemini API.

This separation means the application logic does not depend directly on one provider. A different LLM provider can be introduced by changing the LLM layer rather than rewriting the API.

## Security Guards

`guards.py` contains the pre-processing and post-processing security logic.

The pre-processor looks for suspicious patterns such as:

- Attempts to ignore previous instructions.
- Requests for system prompts.
- Requests to reveal secrets.
- Jailbreak/bypass language.
- Attempts to activate administrative/root modes.
- Other known prompt-injection patterns.

The post-processor checks generated output for the protected challenge flag.

## Database

`database.py` configures SQLAlchemy's asynchronous database access.

`models.py` defines the stored prompt-attempt information.

The database is used for:

- Response caching.
- Prompt attempt logging.
- Metadata storage.
- Detecting repeated prompts efficiently.

## Rate Limiter

`rate_limiter.py` implements per-IP request limiting.

The current configuration allows:

```text
5 requests per minute per IP
```

This prevents a single client from generating unlimited LLM requests and protects both the service and API budget.

---

# 4. Security and Access Control

## Secret / Flag Protection

The challenge flag is configured server-side through an environment variable:

```text
CHALLENGE_FLAG
```

It should not be hard-coded into client-side code or exposed through the API configuration.

The system prompt is generated on the server using the configured flag.

The application also checks LLM output for flag leakage before returning the final response.

## Input Access Control

Every request passes through several controls before reaching the LLM:

```text
Client
  |
  v
Rate Limit
  |
  v
Input Validation
  |
  v
Security Guard
  |
  v
Cache
  |
  v
LLM
```

This layered approach means that the LLM is not the only security boundary.

## User API Keys

The application supports an optional user-provided API key when enabled through configuration.

The server-side key remains controlled by environment variables.

API keys should never be committed to GitHub.

---

# 5. Problems Encountered and Mitigation Steps

## Problem 1: Prompt Injection

### Problem

Users may attempt to manipulate the model into ignoring its original instructions, revealing system information, or bypassing restrictions.

### Mitigation

A pre-processing guard checks the prompt before the LLM request.

Suspicious patterns are rejected early.

This provides two benefits:

1. Obvious attacks are blocked before reaching the LLM.
2. Unnecessary LLM API costs are avoided.

The guard is intentionally lightweight and can later be replaced or supplemented with a more advanced classifier.

---

## Problem 2: Repeated LLM Requests Increase Cost

### Problem

The same prompt may be submitted repeatedly, causing unnecessary API calls and increased latency.

### Mitigation

The application generates a SHA-256 hash for each prompt.

The hash is indexed in the database.

For repeated prompts:

```text
Prompt
  |
  v
SHA-256 Hash
  |
  v
Database Lookup
  |
  +---- Cache Hit ----> Return stored response
  |
  +---- Cache Miss ---> Call LLM
```

This reduces duplicate LLM calls and improves response time.

---

## Problem 3: API Abuse and Cost Exhaustion

### Problem

An attacker could repeatedly call the endpoint and consume the available LLM API quota.

### Mitigation

A per-IP rate limiter restricts clients to five requests per minute.

When the limit is exceeded, the API returns HTTP `429`.

For example:

```json
{
  "detail": "Rate limit exceeded. Max 5 requests per minute."
}
```

For a distributed production deployment, the current in-memory implementation can be replaced with Redis so that limits are shared across multiple application instances.

---

## Problem 4: LLM Accidentally Revealing the Flag

### Problem

Even when a system prompt asks the model to protect a secret, an LLM can sometimes generate unintended output.

### Mitigation

The generated response is inspected after the LLM call.

The system records whether a protected flag was detected and exposes the security status through the response metadata.

This creates a second security layer:

```text
System Prompt Protection
        +
Post-Processing Detection
```

The flag itself remains a server-side configuration value.

---

## Problem 5: Excessively Large Prompts

### Problem

Very large prompts can increase processing time, memory consumption, and LLM costs.

### Mitigation

A maximum prompt length is configured:

```text
MAX_PROMPT_LENGTH = 4000
```

Requests beyond the allowed size are rejected rather than forwarded to the LLM.

---

## Problem 6: Deployment Differences

### Problem

Local development uses a persistent SQLite file, while serverless environments such as Vercel have different filesystem and execution characteristics.

### Mitigation

The database URL is configurable through environment variables.

The application can therefore use SQLite for local development and be migrated to a managed database such as PostgreSQL for a scalable production deployment.

The application code is kept separate from the database configuration so this migration does not require redesigning the API.

---

# 6. Edge Cases and How They Are Handled

## Empty Prompt

Input validation rejects invalid requests instead of sending an empty request to the LLM.

## Very Long Prompt

Prompts exceeding `MAX_PROMPT_LENGTH` are rejected.

## Repeated Prompt

The SHA-256 cache lookup returns the stored response without another LLM call.

## Malicious Prompt

Known injection patterns are detected by the pre-processing guard.

## LLM Failure

The backend handles failures from the external LLM service rather than assuming every request succeeds.

## Missing API Key

The application configuration allows the Gemini key to be supplied through environment variables. Deployment configuration should provide the required key when an external LLM call is needed.

## Rate Limit Exceeded

The client receives HTTP `429` instead of allowing unlimited requests.

## Accidental Secret Leakage

Generated output is checked by the post-processing layer before the response is finalized.

## Concurrent Requests

FastAPI and asynchronous database operations allow multiple I/O-bound requests to be handled efficiently without blocking the entire application.

---

# 7. Scalability and Cost-Efficiency

The backend is designed so that the first version can remain simple while individual components can be replaced as traffic increases.

## Current Architecture

```text
FastAPI
   |
   +-- Async LLM calls
   |
   +-- Async SQLAlchemy
   |
   +-- Prompt cache
   |
   +-- Per-IP rate limiter
   |
   +-- Security guards
```

## Scaling Path

For higher traffic:

```text
                 +----------------+
                 | Load Balancer  |
                 +-------+--------+
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
     +---------+    +---------+    +---------+
     | FastAPI |    | FastAPI |    | FastAPI |
     | Instance|    | Instance|    | Instance|
     +----+----+    +----+----+    +----+----+
          |              |              |
          +--------------+--------------+
                         |
                  +------+------+
                  |    Redis    |
                  | Rate/Cache  |
                  +------+------+
                         |
                  +------+------+
                  | PostgreSQL  |
                  |  Database   |
                  +------+------+
                         |
                    Gemini API
```

## Why This Is Cost-Efficient

1. **Pre-processing guards** prevent obvious malicious requests from reaching the LLM.
2. **Prompt caching** avoids duplicate LLM calls.
3. **Rate limiting** prevents uncontrolled API consumption.
4. **Async I/O** allows better utilization of each application instance.
5. **Configurable infrastructure** allows SQLite locally and managed PostgreSQL at scale.
6. **Containerization** provides reproducible deployment.

---

# 8. Database Optimization

The prompt hash is used as the cache key.

A database index on the hash makes cache lookups efficient.

The design also supports indexing frequently queried metadata such as:

```text
prompt_hash
ip_address
created_at
```

The important idea is that the application does not scan every historical request to find a cached response.

Instead:

```text
Incoming Prompt
      |
      v
 SHA-256 Hash
      |
      v
 Indexed Lookup
      |
      v
 Cache Hit / Miss
```

---

# 9. Docker and Deployment

The project includes a multi-stage `Dockerfile`.

## Docker Design

The builder stage installs dependencies.

The runtime stage contains the application and required Python packages.

The container also creates and uses a non-root user.

This reduces unnecessary privileges inside the container.

The application listens on:

```text
0.0.0.0:8000
```

## Local Docker Deployment

```bash
docker compose up --build
```

The API is then available at:

```text
http://localhost:8000
```

---

# 10. Vercel Deployment

The deployed backend exposes the API through the Vercel deployment.

Health endpoint:

```text
GET /health
```

Chat endpoint:

```text
POST /api/sandbox/chat
```

Example production endpoint:

```text
https://llmsandbox.vercel.app/api/sandbox/chat
```

The deployment uses environment variables for configuration rather than relying on local `.env` files.

For production, secrets should be configured through the hosting platform's environment-variable settings.

---

# 11. API Usage

## Health Check

```text
GET /health
```

Example response:

```json
{
  "status": "OK"
}
```

## Chat Request

```text
POST /api/sandbox/chat
```

Request:

```json
{
  "user_prompt": "What is the capital of France?"
}
```

Example response:

```json
{
  "response": "The capital of France is Paris.",
  "cached": false,
  "injection_detected": false,
  "flag_revealed": false
}
```

Submitting the same prompt again can produce:

```json
{
  "response": "The capital of France is Paris.",
  "cached": true,
  "injection_detected": false,
  "flag_revealed": false
}
```

---

# 12. API Documentation

FastAPI automatically provides interactive API documentation.

The documentation can be accessed at:

```text
/docs
```

For the deployed application:

```text
https://llmsandbox.vercel.app/docs
```

This makes the API easy to demonstrate and test without requiring a separate frontend.

---

# 13. Testing Strategy

The project includes PowerShell verification scripts for testing the backend.

Important scenarios include:

1. Health check.
2. Normal LLM request.
3. Repeated request and cache hit.
4. Prompt-injection detection.
5. Rate-limit enforcement.
6. Flag detection.
7. Invalid/oversized input.
8. Production deployment endpoint.

Example PowerShell request:

```powershell
$body = @{
    user_prompt = "What is the capital of France?"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "https://llmsandbox.vercel.app/api/sandbox/chat" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

---

# 14. Project Structure

```text
.
├── config.py             # Environment variables and application settings
├── database.py           # Async SQLAlchemy engine and database session
├── models.py             # Database models
├── guards.py             # Prompt guards and flag detection
├── llm.py                # Gemini/LLM integration
├── main.py               # FastAPI application and endpoints
├── rate_limiter.py       # Per-IP rate limiting
├── schemas.py            # Request/response validation schemas
├── Dockerfile            # Multi-stage Docker build
├── docker-compose.yml    # Local container orchestration
├── requirements.txt      # Python dependencies
├── Verify.ps1            # Verification script
├── Verify2.ps1           # Additional verification script
└── README.md             # Project documentation
```

---

# 15. Design Decisions

## Why FastAPI?

FastAPI is well suited for an LLM backend because LLM requests are primarily I/O-bound. Its asynchronous architecture allows the server to handle other requests while waiting for external services.

## Why Async SQLAlchemy?

Database operations should not unnecessarily block request processing. Async SQLAlchemy provides an asynchronous database interface compatible with FastAPI.

## Why SHA-256?

SHA-256 produces a deterministic fixed-length hash for each prompt, making it suitable as a compact cache key.

The hash is not being used as encryption; it is being used for deterministic lookup.

## Why SQLite Initially?

SQLite has almost zero operational overhead and is convenient for development and demonstration.

For a larger production deployment, PostgreSQL is the recommended database because it provides stronger concurrency and multi-instance support.

## Why Regex Guards?

Regex checks are inexpensive and fast, making them useful as a first security layer.

They are not considered a complete solution to prompt injection. More advanced detection can be added later.

---

# 16. Security Limitations

This project demonstrates practical defensive techniques but no LLM security mechanism is perfect.

Regex filtering can produce:

- False positives.
- False negatives.
- Bypass opportunities through novel wording.

Similarly, relying only on a system prompt cannot guarantee that an LLM will never produce sensitive information.

Therefore the architecture intentionally uses defense in depth:

```text
Input Validation
      +
Rate Limiting
      +
Pre-Processing Guard
      +
Server-Side Secret
      +
System Prompt Restrictions
      +
Post-Processing Detection
      +
Logging / Auditing
      +
Controlled Infrastructure
```

For a real production security system, additional controls such as authentication, centralized secret management, Redis, PostgreSQL, structured audit logging, monitoring, and stronger content/security classifiers should be added.

---

# 17. Future Improvements

1. Replace the in-memory rate limiter with Redis.
2. Replace SQLite with PostgreSQL for multi-instance production deployments.
3. Add authentication and role-based access control for administrative endpoints.
4. Add centralized structured logging.
5. Add Prometheus/Grafana monitoring.
6. Add automated unit and integration tests with pytest.
7. Add stronger prompt-injection detection.
8. Add request IDs for tracing.
9. Add configurable LLM timeouts and retry policies.
10. Add circuit breaking for external LLM failures.
11. Add a dedicated distributed cache.
12. Add CI/CD security checks before deployment.

---

# 18. Summary

The LLM Sandbox follows a layered backend architecture:

```text
CLIENT
  |
  v
RATE LIMITER
  |
  v
INPUT VALIDATION
  |
  v
SECURITY GUARD
  |
  v
PROMPT HASH / CACHE
  |
  +------ CACHE HIT ------> RESPONSE
  |
  +------ CACHE MISS -----> GEMINI
                              |
                              v
                       FLAG DETECTION
                              |
                              v
                       DATABASE CACHE
                              |
                              v
                           RESPONSE
```

The implementation is intentionally modular so that it can start as a lightweight assignment project while providing a clear path toward a scalable production architecture.

The key feasibility, scalability, and cost-efficiency mechanisms are:

- **FastAPI + asynchronous I/O** for concurrent requests.
- **Rate limiting** for abuse and cost control.
- **Pre-processing guards** for early attack rejection.
- **SHA-256 prompt caching** to reduce duplicate LLM calls.
- **Post-processing flag detection** as a second security layer.
- **Environment-based configuration** for deployment flexibility.
- **Docker** for reproducible deployments.
- **SQLite locally / PostgreSQL at scale**.
- **Redis as the future distributed rate-limit/cache layer**.

This architecture addresses the required areas of project operation, encountered problems, mitigation steps, edge cases, access control, security, scalability, deployment, and future improvements.

---

**Built for GDG VIT Chennai Round 2 Recruitment — LLM Sandbox Backend**
