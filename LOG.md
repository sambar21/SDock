# Project Log

One place for bugs, design choices, and trade-offs. Add an entry the moment something happens, not later from memory. Newest entries go at the top of each section.

## How to write an entry
- **Date**, a short **title**, and the **phase** it happened in.
- Say what happened or what was decided in plain words.
- Say why. For decisions, list the options you considered and what each one costs.
- Say what you'd revisit and what would make you change your mind.

---

## Design decisions

### D-001: One input format (PLY) to start
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Support PLY only.
- **Why:** It is common for scans, simple to parse, and easy to generate test files for.
- **Alternatives:** OBJ, GLB, E57, LAS.
- **Trade-off:** Fewer formats means a smaller test surface and less parsing code, but users with other formats are turned away.
- **Revisit if:** The core flow is done and time remains. The validator and loader are the only parts that would need to grow.

### D-002: Process in a background worker, not in the request
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Upload returns `202` right away. A worker does the heavy work.
- **Why:** Decimating a large scan can take many seconds. Holding the request open risks timeouts and blocks the API.
- **Alternatives:** Do it inline in the request.
- **Trade-off:** Adds Redis, a worker process, and a status field the client has to poll. Worth it, because inline processing would fail on big files.
- **Revisit if:** Polling feels slow. Server-sent events could replace it.

### D-003: Local storage behind an interface
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Store files on local disk, behind a small storage interface.
- **Why:** Keeps setup simple while leaving a clean seam to swap in S3 or MinIO later.
- **Alternatives:** Use S3-compatible storage from day one.
- **Trade-off:** Local disk doesn't scale across multiple servers. Fine for this scope.
- **Revisit if:** The service needs to run on more than one machine.

### D-004: FastAPI for the API
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Use FastAPI.
- **Why:** It generates OpenAPI docs from the code, so the docs can't drift from the routes.
- **Alternatives:** Django REST Framework, Flask, Node with Express.
- **Trade-off:** Fewer built-ins than Django (no admin, no ORM bundled), so more is wired by hand.

### D-005: RQ over Celery
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Use RQ for the job queue.
- **Why:** Much smaller and easier to reason about. One queue and one worker is all this needs.
- **Trade-off:** Fewer features: weaker retry and scheduling options, Redis only.
- **Revisit if:** Jobs need complex retries or scheduling.

### D-006: Roles checked in one shared dependency
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** A single permission dependency used by every route.
- **Why:** One place to read, one place to test, no chance of a route forgetting its check.
- **Trade-off:** Slightly more abstract than inline checks, but much harder to get wrong.

### D-007: Two-stage validation
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Cheap checks (type, empty, size) at upload. Expensive checks (parsing, NaN, zero vertices) in the worker.
- **Why:** Reject obvious junk instantly without queueing work, while keeping slow parsing off the request path.
- **Trade-off:** Some bad files are only caught after upload returns, so the client sees `failed` status instead of an immediate error.

### D-008: 90 percent is a target, measured not assumed
- **Date:** 2026-10-06
- **Phase:** Planning
- **Decision:** Record `reduction_pct` per scan and report the real average over a set of test scans.
- **Why:** The reduction depends heavily on the input. Dense scans shrink a lot, small ones may not.
- **Revisit if:** Results land far from 90. Adjust the decimation target or state the real number.

### D-009: SQLite as the default database outside Docker
- **Date:** 2026-10-06
- **Phase:** 1 (Skeleton)
- **Decision:** `DATABASE_URL` defaults to a local SQLite file. Docker Compose sets it to Postgres.
- **Why:** Tests and local runs work with no services running. Compose still exercises the real Postgres path.
- **Trade-off:** SQLite and Postgres differ in small ways (types, locking, constraints). A bug could pass on one and fail on the other.
- **Revisit if:** A Postgres-only bug shows up. Then run the test suite against Postgres in CI.

### D-010: Pinned dependency versions, split runtime and dev files
- **Date:** 2026-10-06
- **Phase:** 1 (Skeleton)
- **Decision:** `requirements.txt` for runtime (pinned), `requirements-dev.txt` for test tools.
- **Why:** The Docker image stays small, and builds are repeatable.
- **Trade-off:** Pins need manual bumping.

### D-011: Open3D is not the first choice for processing
- **Date:** 2026-10-06
- **Phase:** 1 (Skeleton)
- **Decision:** Plan to use trimesh with fast-simplification, plus numpy voxel downsampling for point clouds. Open3D is dropped unless it installs cleanly.
- **Why:** The dev machine runs Python 3.13, and Open3D wheels have lagged behind new Python versions. Not yet verified, so this stays provisional until phase 4.
- **Trade-off:** Fewer ready-made point cloud tools, so voxel downsampling is written by hand.

### D-012: Tables created at startup, Alembic deferred (superseded by D-037)
- **Date:** 2026-10-06
- **Phase:** 2 (Auth and orgs)
- **Decision:** `Base.metadata.create_all` runs at app start. Alembic is not set up yet.
- **Why:** The schema is still moving. Writing migrations now would mean rewriting them as it changes.
- **Trade-off:** `create_all` never alters existing tables, so a changed model needs a database reset until migrations exist.
- **Update:** Done in phase 6 (D-037).

### D-013: Non-members get 404, low-role members get 403
- **Date:** 2026-10-06
- **Phase:** 2
- **Decision:** If you are not in an org, every org route says "not found". If you are in it but lack the role, you get "forbidden".
- **Why:** A 403 for outsiders would confirm that an org id exists.
- **Trade-off:** Slightly harder to debug a wrong org id, since it looks the same as no access.

### D-014: Roles compared by rank
- **Date:** 2026-10-06
- **Phase:** 2
- **Decision:** viewer=1, editor=2, owner=3. A route asks for a minimum role.
- **Why:** One comparison, and no per-route role lists to keep in sync.
- **Trade-off:** Roles must stay a strict ladder. A role like "uploader but not deleter" would not fit and would need a real permission model.

### D-015: Argon2 for passwords, PyJWT for tokens
- **Date:** 2026-10-06
- **Phase:** 2
- **Decision:** `pwdlib` with its recommended Argon2 hasher, and HS256 tokens with a 60 minute lifetime.
- **Why:** Argon2 is the current default recommendation, and `passlib` is no longer maintained.
- **Trade-off:** No refresh tokens and no token revocation. A stolen token works until it expires. Fine for this scope.

### D-016: Email normalized to lowercase, and a login error that doesn't say which part was wrong
- **Date:** 2026-10-06
- **Phase:** 2
- **Decision:** Emails are lowercased on register and login. Wrong password and unknown email return the identical `401`.
- **Why:** Avoids duplicate accounts that differ by case, and avoids revealing which emails are registered.
- **Trade-off:** Register still returns `409 email_taken`, which does reveal that an email exists. Closing that fully needs email verification, which is out of scope.

### D-017: Last owner is protected
- **Date:** 2026-10-06
- **Phase:** 2
- **Decision:** The only owner of an org can't be removed or demoted (`409 last_owner`).
- **Why:** Otherwise an org could end up with nobody able to manage members.
- **Trade-off:** An org can't be abandoned. Deleting an org would be a separate feature.

### D-018: Generated test scans instead of real ones
- **Date:** 2026-10-06
- **Phase:** 3 (Upload and validation)
- **Decision:** `tools/scangen.py` makes binary PLY files: noisy-sphere point clouds, wavy-grid meshes, and one broken file per failure case (truncated, NaN, zero vertices, not a PLY).
- **Why:** No real scans are available, and generated ones give exact control over size and defects.
- **Trade-off:** Synthetic geometry is cleaner than real scans. A noisy sphere decimates differently from a messy room, so the size reduction measured on these files may not match real-world results. State that plainly when reporting numbers.
- **Revisit if:** Real scans become available. Rerun the size measurements on them.

### D-019: Two layers of size limit
- **Date:** 2026-10-06
- **Phase:** 3
- **Decision:** Middleware rejects requests whose declared `Content-Length` is over the limit plus 1 MB. The save step counts bytes and aborts past the limit.
- **Why:** The framework reads the whole multipart body to a temp file before the route runs. The streaming count alone would not stop a huge upload from being received first.
- **Trade-off:** The 1 MB slack means the middleware is approximate, so the exact check still lives in the save step. Chunked uploads with no `Content-Length` skip the middleware and are only caught after they have been received.
- **Revisit if:** Large uploads become common. A reverse proxy such as nginx should enforce the limit before the app sees the body.

### D-020: Upload checks type by extension and first bytes only
- **Date:** 2026-10-06
- **Phase:** 3
- **Decision:** `.ply` extension plus a `ply` magic header. Nothing else is parsed during the request.
- **Why:** Matches D-007. A deeper parse belongs in the worker.
- **Trade-off:** A file with a valid header and garbage body is accepted, then fails in the worker.

### D-021: Storage layout is `org_id/scan_id/original.ply`
- **Date:** 2026-10-06
- **Phase:** 3
- **Decision:** One folder per scan. The preview will sit beside the original.
- **Why:** Deleting a scan is one folder removal. Keys use only generated ids, so user filenames never touch the disk path. The storage layer also refuses any key that resolves outside its root.
- **Trade-off:** The original filename is only kept in the database.

### D-022: Upload route is sync, not async
- **Date:** 2026-10-06
- **Phase:** 3
- **Decision:** `def`, not `async def`, so FastAPI runs it in a thread pool.
- **Why:** Writing a big file to disk is blocking work and would stall the event loop if it ran in an async handler.
- **Trade-off:** Uses a thread per concurrent upload.

### D-023: trimesh confirmed for processing, Open3D never tried
- **Date:** 2026-10-06
- **Phase:** 4 (Worker and processing)
- **Decision:** Use trimesh with fast-simplification for mesh decimation. Point clouds are thinned by random sampling in numpy.
- **Why:** It installed and ran on Python 3.13 with no trouble. This settles D-011. Open3D was not tried, so there is no evidence either way on whether it would have worked.
- **Trade-off:** Random sampling can leave uneven density, where voxel downsampling would spread points evenly. Mesh decimation drops vertex colours. Neither matters for the synthetic scans, but both could show up on real ones.
- **Revisit if:** Real scans look patchy in the viewer. Voxel downsampling is the first thing to try.

### D-024: Keep 10 percent, with a floor
- **Date:** 2026-10-06
- **Phase:** 4
- **Decision:** Keep 10 percent of triangles or points, but never fewer than 500 triangles or 2,000 points.
- **Why:** The 10 percent ratio is what drives the size reduction. The floor stops small scans from turning into blobs.
- **Trade-off:** Scans under the floor are not shrunk at all, and their preview can come out roughly the same size as the original or slightly larger. The reduction is stored as measured, so it can be near zero or negative.

### D-025: No Draco compression
- **Date:** 2026-10-06
- **Phase:** 4
- **Decision:** Export plain GLB.
- **Why:** trimesh cannot write Draco, and Three.js needs an extra decoder to read it. The 10 percent geometry cut already gets close to the target.
- **Trade-off:** Previews are larger than they could be. Draco could shrink them further.
- **Revisit if:** Previews need to be much smaller than 10 percent of the original.

### D-026: Undo the upload if the queue is down
- **Date:** 2026-10-06
- **Phase:** 4
- **Decision:** If the job can't be queued, delete the scan and its file and return `503 queue_unavailable`.
- **Why:** The scan would otherwise sit in `uploaded` forever with nothing to move it on.
- **Alternatives:** Keep the scan and retry later (needs a sweeper job), or mark it `failed` (the user did nothing wrong).
- **Trade-off:** The user has to upload again. It is simple, and nothing is ever left half-done.

### D-027: Fake queue in tests, plus a separate check on the real queue code
- **Date:** 2026-10-06
- **Phase:** 4
- **Decision:** Most tests swap the queue for a list and run the worker function by hand. Two tests use fakeredis to check the real enqueue code and a real RQ worker.
- **Why:** RQ's worker does not run on Windows, and the tests should not need a Redis server.
- **Trade-off:** Real Redis is never exercised. The fakeredis tests cover job format and the function path, not network behaviour.

### D-028: Worker only handles scans in `uploaded`
- **Date:** 2026-10-06
- **Phase:** 4
- **Decision:** A job for a scan in any other status does nothing.
- **Why:** Duplicate jobs, retries and jobs for deleted scans are all harmless.
- **Trade-off:** A worker that crashes mid-job leaves the scan stuck in `validating` or `processing`, and nothing rescues it.
- **Update:** Done in phase 6 (D-038).

### D-029: Original file is kept after processing
- **Date:** 2026-10-06
- **Phase:** 4
- **Decision:** `original.ply` stays next to `preview.glb`.
- **Why:** The original is the source of truth. Deleting it would make re-processing impossible.
- **Trade-off:** Storage use is the original plus the preview.

### Measured size reduction (synthetic scans)
Run with `python -m tools.measure samples` on 2026-10-06:

| File | Original | Preview | Smaller |
|---|---|---|---|
| cloud_large | 7,500,180 | 800,920 | 89.3% |
| cloud_small | 300,179 | 32,916 | 89.0% |
| mesh_large | 9,474,205 | 903,616 | 90.5% |
| mesh_small | 133,881 | 13,716 | 89.8% |

The average is **89.6%**. That is about 90 percent, not at least 90. Four scans is a small sample, and these are synthetic, so treat the figure as indicative. The README should quote the measured number as it stands.

### D-030: The viewer is served by the API, with no build step
- **Date:** 2026-10-06
- **Phase:** 5 (Viewer)
- **Decision:** Plain HTML and ES modules in `viewer/`, mounted by FastAPI at `/viewer/`. No Vite, no bundler, no npm project.
- **Why:** Same origin as the API, so there is no CORS to configure and one container to run. Nothing to build means nothing to break.
- **Trade-off:** No hot reload, no TypeScript, no bundling. Fine for one page.
- **Revisit if:** The UI grows past a few hundred lines.

### D-031: Three.js is copied into the repo, not loaded from a CDN
- **Date:** 2026-10-06
- **Phase:** 5
- **Decision:** Three.js 0.186.1 (`three.module.js`, `three.core.js`, GLTFLoader, OrbitControls and two helpers it imports) lives in `viewer/vendor/`, wired up with an import map.
- **Why:** Works offline, behind a firewall, and in tests. The version cannot change under the page.
- **Trade-off:** About 2.3 MB in the repo, and upgrades are manual. GLTFLoader also imports SkeletonUtils, which I missed at first and added after checking the imports.

### D-032: The preview is fetched with the token, then handed to the loader
- **Date:** 2026-10-06
- **Phase:** 5
- **Decision:** The page downloads the GLB with `fetch` and an `Authorization` header, then parses the bytes with `GLTFLoader.parseAsync`.
- **Why:** A model loaded by URL cannot send a bearer header, and putting the token in the URL would leak it into logs and history.
- **Trade-off:** The whole file is held in memory before parsing, with no progress bar. Fine for previews around 1 MB.

### D-033: Token kept in sessionStorage
- **Date:** 2026-10-06
- **Phase:** 5
- **Decision:** Store the JWT in `sessionStorage`, so it goes when the tab closes.
- **Why:** Simplest approach with the bearer-token API from D-015.
- **Trade-off:** Any script injected into the page could read it. An httpOnly cookie would be safer but needs CSRF handling and API changes. The page writes all user-supplied text (scan and org names) with `textContent`, never `innerHTML`, to keep injection off the table.
- **Revisit if:** The service handles anything beyond a demo.

### D-034: Added `GET /api/v1/orgs` (my organizations)
- **Date:** 2026-10-06
- **Phase:** 5
- **Decision:** A new route returns the caller's orgs with their role.
- **Why:** The plan had no way for a page to learn which org to show. Without it, the viewer would need an org id typed in by hand.
- **Trade-off:** A small API addition beyond the original plan. It is covered by a test.

### D-035: Polling every 2 seconds, only while something is unfinished
- **Date:** 2026-10-06
- **Phase:** 5
- **Decision:** The page refreshes the scan list every 2 seconds while any scan is `uploaded`, `validating` or `processing`, and stops once all are `ready` or `failed`.
- **Why:** Matches the plan. Idle pages cost nothing.
- **Trade-off:** Up to 2 seconds of lag, and one list request per tick. Server-sent events would avoid both but add moving parts.

### D-036: Browser check script instead of a browser test in the suite
- **Date:** 2026-10-06
- **Phase:** 5
- **Decision:** `tools/browser_check.py` drives the real page in Edge through Playwright. It is not part of `pytest`.
- **Why:** It needs Edge and Playwright, and renders with software WebGL. That is too heavy and too machine-specific for the normal test run.
- **Trade-off:** It runs by hand, so it can go stale. The pure helpers are covered by `node --test viewer/scan-state.test.mjs`, which is fast.

### D-037: Alembic replaces create_all (resolves D-012)
- **Date:** 2026-10-06
- **Phase:** 6 (Hardening)
- **Decision:** One initial migration, `0001`, generated from the models and then read through. The API no longer creates tables. The Docker image runs `alembic upgrade head` before starting the server. A test keeps migrations and models from drifting apart.
- **Why:** `create_all` never alters existing tables, and it left the worker with no tables (B-008).
- **Trade-off:** Local dev now needs `alembic upgrade head` once. Every model change needs a new migration, and the drift test fails until you add one. The downgrade also drops the Postgres enum types, which autogenerate leaves behind.
- **Verified later:** The migration ran against real Postgres 17 inside Docker during phase 7.

### D-038: Stuck scans are failed by a sweeper inside the API
- **Date:** 2026-10-06
- **Phase:** 6
- **Decision:** Every 60 seconds the API fails any scan that has been `uploaded`, `validating` or `processing` for more than 15 minutes, with a message asking the user to upload again.
- **Why:** Closes the gap in D-028. A crashed worker or a lost job no longer leaves a scan spinning forever.
- **Alternatives:** A separate scheduler process, or a cron job.
- **Trade-off:** If several API instances run, each sweeps. That is harmless, because the update is idempotent, but it is wasted work. The 15 minutes sits above the 10 minute job timeout, so a slow but live job is not cut off. Failed scans are not retried automatically.
- **Related behaviour:** If the sweeper fails a scan and the old job runs later, the worker skips it, because it only handles scans in `uploaded` (D-028). A test covers this.

### D-039: Refuse to start with a weak secret outside dev
- **Date:** 2026-10-06
- **Phase:** 6
- **Decision:** A new `ENVIRONMENT` setting defaults to `dev`. In any other environment the app will not start if `SECRET_KEY` is the dev default or shorter than 32 characters.
- **Why:** Closes the open risk in B-003. A forgotten secret would let anyone forge tokens.
- **Trade-off:** The safe path is opt-in, because the default is `dev`. Someone who forgets `ENVIRONMENT` gets dev behaviour. The Compose file sets `ENVIRONMENT=dev` on purpose, since it is a local stack.

### D-040: Bearer scheme and error models in the docs
- **Date:** 2026-10-06
- **Phase:** 6
- **Decision:** Auth uses FastAPI's `HTTPBearer` (with `auto_error` off), so `/docs` shows an Authorize button. Each router declares its error responses with a shared `ErrorBody` model. `/` redirects to the viewer. The API version is now 1.0.0.
- **Why:** Before this, the token was a bare header parameter on every route, so you could not try the API from the docs page.
- **Trade-off:** The listed error codes are per router, not per route, so a route can list a code it never returns (for example, `409` on reading an org).

### D-041: The permission matrix builds a fresh org for every case
- **Date:** 2026-10-06
- **Phase:** 6
- **Decision:** 9 endpoints × 5 callers (anonymous, outsider, viewer, editor, owner) as 45 separate tests, each with its own world.
- **Why:** Destructive cases (delete a scan, remove a member) cannot poison the next one, and a failure names its exact endpoint and caller.
- **Trade-off:** Slow. Registering users hashes passwords with Argon2, so the full suite takes about 20 seconds, up from about 3.
- **Revisit if:** The suite gets too slow. Use a cheaper hasher in tests, or share users across cases.

### D-042: Host port is configurable
- **Date:** 2026-10-06
- **Phase:** 7 (Write-up and verification)
- **Decision:** Compose publishes `${API_PORT:-8000}:8000`.
- **Why:** The first `docker compose up` failed because another project's container (`taskflow-api-1`) already held port 8000 (B-015). Stopping someone else's container was not an option.
- **Trade-off:** One more variable to know about. The default is unchanged.

### D-043: The demo GIF is recorded from the real page
- **Date:** 2026-10-06
- **Phase:** 7
- **Decision:** `python -m tools.browser_check --gif` saves frames while it runs and writes `docs/demo.gif`, about 450 KB at 900 px wide.
- **Why:** A hand-made screen recording would go stale and could not be remade. This one is rebuilt with one command.
- **Trade-off:** Processing is so fast with these small scans that the "processing" state is rarely caught in a frame. The GIF shows queued and finished states, then the models turning. Palette is cut to 96 colours to keep the file small.

### D-044: Stack check script runs against the real Docker stack
- **Date:** 2026-10-06
- **Phase:** 7
- **Decision:** `tools/stack_check.py` talks plain HTTP to a running stack. It uploads every sample, waits on the real worker, and checks each preview is a real GLB of the size the API reports.
- **Why:** Everything before this ran with a fake queue and SQLite. This is the only check of real Postgres, Redis and RQ together.
- **Trade-off:** It needs a running stack, so it is a manual check and not part of `pytest`.

### D-045: A separate "Vercel mode", not a rewrite
- **Date:** 2026-10-06
- **Phase:** 8 (Vercel packaging)
- **Decision:** When Vercel's own `VERCEL` variable is present, the app defaults to database storage, inline processing, a 4 MB upload cap, no background sweeper, and `ENVIRONMENT=production`. Every default can still be overridden. Docker behaviour is unchanged.
- **Why:** Research on Vercel's docs found four mismatches with this design: request bodies are capped at 4.5 MB, there is no disk that lasts, there is no long-running worker, and there is no Redis. Vercel Queues has a Python SDK, but it is in beta. Blob client uploads (the way past the 4.5 MB cap) are documented for the JavaScript SDK, and I found no documented Python equivalent. Both would have been code I could not test without a Vercel account.
- **Alternatives:** Build on Vercel Queues and Blob (untestable here, beta, and a larger rewrite). Host on a platform that runs Docker (no changes needed, but not what was asked).
- **Trade-off:** Vercel mode is limited to small scans (4 MB), but every line of it is tested locally. The big-scan path stays on Docker.
- **Revisit if:** Large scans are needed on Vercel. Browser-to-Blob uploads plus Vercel Queues would be the route.

### D-046: Storage interface now deals in bytes and streams, not file paths
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** Dropped `path()` from the storage interface and added `write()`. The worker reads with `open()` and writes the preview with `write()`. The preview route streams from `open()`.
- **Why:** Database storage has no file path to hand out. This also makes an S3 backend a drop-in later.
- **Trade-off:** The worker now holds the whole preview in memory before writing it, where before it exported straight to disk. Previews are small, so this is fine.
- **Check:** All 113 existing tests passed unchanged after the refactor, and the real Docker stack passed again afterwards.

### D-047: Files stored as database rows in Vercel mode
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** A `stored_files` table (key, bytes) holds originals and previews. Added as migration `0002`.
- **Why:** The only storage that needs no extra service, no beta SDK and no account, and it can be tested here with SQLite.
- **Trade-off:** Both the original and the preview are kept, so each scan costs roughly its own size plus a tenth. On a small free database that is room for a modest number of scans. Whole files pass through memory. Deleting a scan frees its rows.
- **Revisit if:** The database fills up. Switch to Blob storage, or drop the original after processing.

### D-048: Inline processing in Vercel mode
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** In Vercel mode the upload request processes the scan before returning. The `202` response already shows `ready` or `failed`.
- **Why:** There is no worker to hand the job to. At a 4 MB cap, processing takes well under a second, and the function allows 60 seconds.
- **Trade-off:** Uploads take a little longer. If the function is killed mid-job, the scan stays `processing` until the sweeper fails it. The page still polls, so nothing breaks.
- **Also:** The response is refreshed from the database after processing, so it shows the real status in every mode. Without that, the object held by the request would be stale.

### D-049: Sweeper runs as a Vercel Cron call
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** `GET /api/v1/internal/sweep` is called daily by Vercel Cron. It needs `Authorization: Bearer <CRON_SECRET>`, compared in constant time. With no `CRON_SECRET` set it answers `404` as if it did not exist. It is hidden from the public docs.
- **Why:** The in-process sweeper depends on a long-lived process, which serverless does not have.
- **Trade-off:** Daily is the most a free Vercel plan allows (this is from my reading of the docs, not from a test), so a stuck scan can wait up to a day. The 15 minute threshold only decides what counts as stuck once the sweep runs.

### D-050: Database URL cleanup and no connection pool on Vercel
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** `postgres://` and `postgresql://` URLs get the driver name added, since hosts hand out URLs without it. On Vercel the engine uses `NullPool`.
- **Why:** Many function instances each holding their own pool can exhaust the database's connections. The host's pooled URL does the pooling.
- **Trade-off:** Every request opens a fresh connection, which adds latency. Not measured.

### D-051: The viewer folder is mounted with a literal relative path
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** `StaticFiles(directory="viewer")` replaces a path built from `__file__`.
- **Why:** Vercel's docs say it finds static folders by reading the mount call, so a computed path might not be recognised.
- **Trade-off:** The app must now start from the project folder. Docker's `WORKDIR` and every script here already do.
- **Not verified:** I have not seen Vercel pick it up.

### D-052: What the Vercel bundle leaves out
- **Date:** 2026-10-06
- **Phase:** 8
- **Decision:** `.vercelignore` drops tests, tools, samples, screenshots, docs, migrations, Docker files and the plan and log. Migrations are run by hand from a laptop, not at deploy time.
- **Why:** Smaller bundle, and nothing public that is not needed. Running migrations on every deploy is risky if two deploys overlap.
- **Trade-off:** A step to remember. A test checks that the ignore list never removes `app`, `viewer`, `requirements.txt` or `vercel.json`.

### D-053: Open demo mode, switched on by `AUTH_DISABLED=true`
- **Date:** 2026-10-06
- **Phase:** 9 (Demo mode)
- **Decision:** One setting turns sign-in off. Everyone who opens the page acts as one shared user inside one shared workspace. It is off by default, so the safe behaviour stays the default everywhere, including on Vercel.
- **Why:** The first Vercel deploy crashed because no `SECRET_KEY` was set (B-020). For a public demo, accounts are not relevant. With sign-in off no tokens are issued, so no secret is needed either.
- **Alternatives:** Default to open on Vercel (rejected, because a forgotten setting would silently leave a deployment wide open). Pre-fill a throwaway secret (rejected, because it is the weakness the startup check exists to catch).
- **Trade-off:** In this mode anyone with the link can upload and delete anyone else's scans, and the roles feature is bypassed. Uploads are still capped at 4 MB on Vercel, but there is no rate limiting, so someone could fill a small free database. The page says so in a notice. Real sign-in is untouched and still tested.

### D-054: The shared user and workspace are created on first use
- **Date:** 2026-10-06
- **Phase:** 9
- **Decision:** The first request creates a user (`demo@open.local`) and a workspace it owns. Later requests reuse them. No seeding step is needed.
- **Why:** Fresh databases just work, with no extra command after `alembic upgrade head`.
- **Details:** The user's password hash is `!`, which is not a valid hash, so it can never match. The address also uses the reserved `.local` domain, which the login and register forms refuse, so nobody can sign in as it or register it. If two first visits collide, the unique email makes one insert fail, and that request rolls back and uses the other one. A test forces that collision.
- **Trade-off:** A visitor's very first request does a few extra writes.

### D-055: The page asks the server whether sign-in is needed
- **Date:** 2026-10-06
- **Phase:** 9
- **Decision:** New public route `GET /api/v1/config` returns `{auth_required, max_upload_mb}`. The page uses it to skip the sign-in screen, hide sign-out and "create organization", show the demo notice, and print the upload size limit.
- **Why:** The same page serves both modes, with no separate build. If the call fails, the page assumes sign-in is required, which is the safe guess.
- **Trade-off:** One extra request on page load. It also publicly states whether sign-in is on, but that is visible anyway from how the page behaves.

### D-056: A bad stored password hash never crashes login
- **Date:** 2026-10-06
- **Phase:** 9
- **Decision:** `verify_password` returns `False` for anything that is not a real hash, instead of raising.
- **Why:** The shared user's `!` hash would otherwise have caused a 500 if anyone ever reached the login check for it, for example after turning sign-in back on.
- **Trade-off:** A genuinely corrupted hash in the database now fails quietly as a wrong password, which hides a data problem. That is a small price for never leaking a stack trace at the login form.

---

## Verification (phase 7)

All run on 2026-10-06.

| Check | Result |
|---|---|
| `pytest` | 113 passed |
| `node --test viewer/scan-state.test.mjs` | 6 passed |
| `tools.browser_check` (Edge, real page) | Passed, including the viewer role |
| Docker stack: build, Postgres migration, API health, RQ worker | Came up healthy on port 8010 |
| `tools.stack_check` on the stack | Passed. 7 of 8 samples accepted, 8th rejected at upload. 4 good scans ready as valid GLBs, 3 broken ones failed with reasons |
| Size reduction through the stack | Identical to local: 89.3, 89.0, 90.5 and 89.8 percent |
| Redis stopped, then upload | `503 queue_unavailable`, no scan left, worker resumed on its own after Redis returned |
| Fresh copy of the project, README steps only | Install, `alembic upgrade head`, 113 tests passed |

Not covered: real scans, load, many users, a real worker crash mid-job (the sweeper is unit-tested only), and Windows-native RQ.

## Verification (phase 8, Vercel mode)

| Check | Result |
|---|---|
| `pytest` | 142 passed (113 before, plus 29 for Vercel mode) |
| Storage backends | The same 5 contract tests pass on disk and on the database |
| Real server with Vercel's variables set, SQLite, `alembic upgrade head` | Small scans were `ready` when the upload returned. The two large samples got `413 file_too_large`. Broken files failed with reasons. Cron endpoint: 404 without the secret, `{"failed":0}` with it. Viewer served |
| Browser check after the storage refactor | Passed |
| Docker stack after the refactor, on real Postgres | Passed. Migration `0002` applied, all 7 accepted samples processed, reductions unchanged at 89.6% |

Not covered: an actual Vercel deployment. Entry-point detection, static-file promotion, cold starts, the bundle size, and real Neon behaviour are all unconfirmed.

## Verification (phase 9, demo mode)

| Check | Result |
|---|---|
| `pytest` | 154 passed (142 before, plus 12 for demo mode) |
| `node --test viewer/scan-state.test.mjs` | 6 passed |
| `tools.browser_check --open` (Edge) | Passed. No sign-in form, demo notice shown, shared workspace selected, a scan uploaded, processed and drew, and a reload kept working |
| `tools.browser_check` (normal mode) | Still passes |
| Vercel's variables, `AUTH_DISABLED=true`, no `SECRET_KEY`, no `CRON_SECRET`, SQLite | Started. Config reported 4 MB. Small scans were `ready` on upload. The large one got `413`. Broken file failed with a reason. Preview was a valid GLB. Viewer served |

Not covered: the demo mode on Vercel itself with a real Neon database.

## Trade-offs summary
| Choice | Gain | Cost |
|---|---|---|
| PLY only | Small, testable scope | Narrow format support |
| Background worker | No timeouts, API stays responsive | Redis, worker, polling |
| Local storage | Simple setup | Single machine only |
| RQ over Celery | Simplicity | Fewer features |
| Two-stage validation | Fast rejects, light request path | Some errors arrive late |
| Plain Three.js viewer | Fast to build | Minimal UI |
| SQLite default | Zero-setup tests | Possible Postgres drift |
| Alembic migrations | Real schema history, drift test | A migration for every model change |
| 404 for outsiders | Doesn't leak org ids | Harder debugging |
| Role ranks | One simple check | No fine-grained permissions |
| Stateless JWT | Simple, no session store | No revocation, no refresh |
| Generated test scans | Exact control, no data needed | Results may differ on real scans |
| Two-layer size limit | Early reject plus exact count | Chunked uploads slip past the first layer |
| Header-only upload check | Fast uploads | Bad bodies fail later in the worker |
| 10% keep ratio with floor | Reduction near 90% | Tiny scans barely shrink |
| Random point sampling | Simple, repeatable | Uneven density possible |
| Plain GLB, no Draco | No decoder in the viewer | Larger previews |
| Undo upload on queue failure | Nothing left half-done | User must retry |
| Keep the original file | Can re-process | More storage (in Vercel mode, in the database) |
| Stuck-scan sweeper | Nothing spins forever | Failed scans are not retried |
| No frontend build step | Nothing to break | No bundling or TypeScript |
| Three.js vendored | Offline, pinned | 2.3 MB in repo, manual upgrades |
| Fetch then parse the GLB | Token stays out of URLs | No progress bar |
| sessionStorage token | Simple | Readable by injected scripts |
| Poll every 2s | Simple | Small lag, repeated requests |
| Vercel mode (DB storage, inline, 4 MB) | Fully testable, no beta services | Small scans only on Vercel |
| Open demo mode (opt-in) | No accounts, no secrets, works for a demo | Anyone can upload and delete |
| Page asks the server for config | One page serves both modes | One extra request on load |
| Manual browser and stack checks | Real browser and real services covered | They can go stale |
| trimesh over Open3D | Installs on Python 3.13 (to verify) | More hand-written point cloud code |

---

## Bugs

Use this template for each one.

### B-000: Title (template, delete me)
- **Date found:**
- **Phase:**
- **What happened:** What you saw, with the exact error text.
- **Expected:** What should have happened.
- **Steps to reproduce:**
- **Root cause:** Only once it's actually verified.
- **Fix:** What changed and where.
- **Test added:** Which test now guards against it.
- **Status:** open / fixed

### B-001: Docker Compose could not start (environment)
- **Date found:** 2026-10-06
- **Phase:** 1 (Skeleton)
- **What happened:** `docker compose up -d --build` failed with `unable to get image 'postgres:17': error during connect ... dockerDesktopLinuxEngine: The system cannot find the file specified.`
- **Expected:** Containers start and `/api/v1/health` answers.
- **Steps to reproduce:** Run `docker compose up` while Docker Desktop is closed.
- **Root cause:** Docker Desktop was not running. Not a code bug.
- **Fix:** Start Docker Desktop, then rerun.
- **Test added:** `tools/stack_check.py` now exercises the running stack.
- **Status:** fixed. Docker Desktop was started and the stack ran end to end (see Verification below).

### B-003: Weak JWT key warning in tests
- **Date found:** 2026-10-06
- **Phase:** 2
- **What happened:** pytest printed `InsecureKeyLengthWarning: The HMAC key is 18 bytes long, which is below the minimum recommended length of 32 bytes`.
- **Root cause:** The development default `secret_key` was too short.
- **Fix:** Lengthened the dev default. Real deployments must set `SECRET_KEY` themselves.
- **Test added:** None. The warning disappearing from the test run is the check.
- **Status:** fixed
- **Open risk:** Closed by D-039. Outside dev mode the app refuses to start with the default key.

### B-004: Shell script failed to parse when creating many files at once
- **Date found:** 2026-10-06
- **Phase:** 2
- **What happened:** A single large bash script with many heredocs failed with `unexpected EOF while looking for matching '`, and nothing was written.
- **Root cause:** Not pinned down. Likely quoting trouble in the one large script.
- **Fix:** Wrote the files one at a time with the file tool instead.
- **Status:** fixed (workaround)

### B-005: The first size test only exercised the middleware
- **Date found:** 2026-10-06
- **Phase:** 3
- **What happened:** The oversized-file test sent a 3 MB file against a 1 MB limit. The middleware rejected it by `Content-Length`, so the byte-counting check in the save step never ran in any test.
- **Root cause:** The test file was too far over the limit to reach the second layer.
- **Fix:** Added a test with a 1.5 MB file, which is under the middleware cutoff (limit plus 1 MB) but over the real limit.
- **Test added:** `test_file_just_over_the_limit_is_caught_while_saving`.
- **Status:** fixed

### B-006: Possible flaky ordering in the list test
- **Date found:** 2026-10-06
- **Phase:** 3
- **What happened:** Nothing failed. The newest-first test depends on scans created in quick succession getting different `created_at` values.
- **Root cause:** If the clock resolution is coarse, two scans could tie and the order would be undefined.
- **Fix:** Added `id` as a second sort key, so ties can no longer reorder.
- **Status:** fixed

### B-007: Worker bound the real database at import time
- **Date found:** 2026-10-06
- **Phase:** 4
- **What happened:** The first run of the real-worker test failed with `no such table: scans`. It had quietly opened the real `dev.db` file instead of a test database.
- **Root cause:** `process_scan` took `session_factory=SessionLocal` as a default argument, which Python evaluates once at import. Tests could not replace it.
- **Fix:** The default is now `None`, and the real session factory is looked up when the job runs.
- **Test added:** `test_a_real_worker_can_run_the_queued_job` now uses an in-memory database. The suite no longer creates `dev.db`.
- **Status:** fixed

### B-008: Worker never creates tables
- **Date found:** 2026-10-06
- **Phase:** 4
- **What happened:** B-007 showed that the worker process does not set up the database. Only the API does, at startup.
- **Root cause:** `create_all` lives in the API's startup hook (D-012).
- **Fix:** Alembic migrations (D-037). The API container runs them before it starts, and the worker waits for the API to report healthy.
- **Status:** fixed (the Compose path itself is still unverified)

### B-009: RQ workers do not run on Windows
- **Date found:** 2026-10-06
- **Phase:** 4
- **What happened:** RQ's standard worker relies on `fork`, which Windows lacks. The worker can only run for real inside Docker (Linux).
- **Fix:** None needed for deployment. Local tests call the worker function directly (D-027).
- **Status:** open (known limitation). The worker does run correctly inside Docker; local Windows runs still call the function directly.

### B-010: Browser check reported a blank canvas that was not blank
- **Date found:** 2026-10-06
- **Phase:** 5
- **What happened:** The first browser run reported both models as blank. The screenshots showed them rendering correctly.
- **Root cause:** The check copied the WebGL canvas into a 2D canvas. After a WebGL frame is shown, its buffer is cleared unless `preserveDrawingBuffer` is on, so the copy was empty.
- **Fix:** The check now takes a screenshot of the stage and counts colours with Pillow. I did not turn on `preserveDrawingBuffer`, since that would slow the page just to satisfy a test.
- **Status:** fixed

### B-011: Browser check could not find the organization option
- **Date found:** 2026-10-06
- **Phase:** 5
- **What happened:** The check timed out waiting for an `<option>` to be visible.
- **Root cause:** Playwright never treats `<option>` elements as visible. The page was fine.
- **Fix:** Wait for the element to be attached instead.
- **Status:** fixed

### B-012: Favicon request caused a console 404
- **Date found:** 2026-10-06
- **Phase:** 5
- **What happened:** The browser requested `/favicon.ico`, which does not exist, and logged a 404.
- **Fix:** Added an empty inline icon to the page.
- **Status:** fixed

### B-013: Viewer upload and delete controls are not covered by an automated browser test
- **Date found:** 2026-10-06
- **Phase:** 5
- **What happened:** The browser check never signs in as a viewer on an org with scans. Hiding of upload and delete controls for viewers is checked by reading the code only. The server enforces the roles regardless, and the API tests cover that.
- **Fix:** The browser check now makes a real viewer, signs in as them, and confirms the upload form and delete button are hidden and the model still loads.
- **Status:** fixed

### B-014: My first mutation check used a dangerous path
- **Date found:** 2026-10-06
- **Phase:** 6
- **What happened:** While checking that tests can fail, my command made a backup file at the filesystem root and tried to delete it. Claude Code's safety check refused, and nothing ran.
- **Root cause:** A sloppy backup path on my part.
- **Fix:** Redid it with backups in the scratchpad folder. Both deliberate breakages were caught: letting viewers upload failed two permission tests, and a model column without a migration failed the drift test. The code was restored and all 113 tests pass again.
- **Status:** fixed

### B-015: Port 8000 was already in use
- **Date found:** 2026-10-06
- **Phase:** 7
- **What happened:** `docker compose up` failed with `Bind for 0.0.0.0:8000 failed: port is already allocated`.
- **Root cause:** Another project's container (`taskflow-api-1`) was publishing 8000. Not a bug in this project.
- **Fix:** Made the host port configurable (D-042) and ran this stack on 8010. The other container was left alone.
- **Status:** fixed

### B-016: A failed upload leaves an empty organization folder in storage
- **Date found:** 2026-10-06
- **Phase:** 7
- **What happened:** After the Redis outage test, storage held an empty `<org_id>/` folder. The scan folder inside it was removed, but its parent was not.
- **Root cause:** `delete_prefix` removes the scan's folder only. Deleting a scan does the same.
- **Fix:** Not yet. Harmless, but it leaves one empty folder per organization that ever had a rejected upload or deleted scan. A cleanup could remove empty parents.
- **Status:** open (cosmetic)

### B-017: A test relied on how FastAPI lists routes
- **Date found:** 2026-10-06
- **Phase:** 8
- **What happened:** A new test failed with `'_IncludedRouter' object has no attribute 'path'`. It had looped over `app.routes` to find the cron path.
- **Root cause:** The installed FastAPI wraps included routers, so routes are no longer a flat list.
- **Fix:** The test now calls the cron path the way Vercel will, with the secret, and expects `200`. That is a better test anyway, because it exercises the route.
- **Status:** fixed

### B-018: Could not generate the migration on a fresh database
- **Date found:** 2026-10-06
- **Phase:** 8
- **What happened:** `alembic revision --autogenerate` failed with `Target database is not up to date`.
- **Root cause:** I had deleted `dev.db`, so there was nothing at the latest version to compare against.
- **Fix:** Ran `alembic upgrade head` on a scratch database first, then generated `0002`.
- **Status:** fixed

### B-019: Vercel's own 413 is not JSON
- **Date found:** 2026-10-06
- **Phase:** 8
- **What happened:** Found while reading the docs, not by a test. Past 4.5 MB, Vercel rejects the request before the app sees it, so the page's error handler would show a bare status text.
- **Fix:** The page now shows "That file is too large for this deployment." when a 413 has no JSON body. The app's own cap sits at 4 MB so it normally answers first.
- **Status:** fixed in code, never seen on a real Vercel deployment

### B-020: First Vercel deploy crashed with FUNCTION_INVOCATION_FAILED
- **Date found:** 2026-10-06
- **Phase:** 9
- **What happened:** The deployed page showed `500 FUNCTION_INVOCATION_FAILED`. The runtime log ended in `ValidationError: Set SECRET_KEY to a random value of at least 32 characters when ENVIRONMENT is not 'dev'`. The log's `input_value` held only the Vercel defaults, so no `SECRET_KEY`, `DATABASE_URL` or `CRON_SECRET` had reached that deployment.
- **Root cause:** The variables were missing on that deployment (not set, or set after the build without a redeploy). My startup check, working as designed, refused to start. On Vercel an exception during import shows only as a blank 500 page, so the real reason is visible only in the logs.
- **What the log did confirm:** Vercel found `app/main.py`, installed the dependencies and imported every module up to the settings check. That settles entry-point detection and the install, which were open questions.
- **Fix:** Open demo mode (D-053), so a demo needs no secrets. The README now lists exactly which variables each mode needs and says to redeploy after changing them.
- **Status:** fixed for the demo path. Not yet seen working on Vercel itself.
- **Lesson:** Before telling someone to deploy, I reproduced the failure locally, so I could say what the likely cause was. I could not see the log myself and had to ask for it.

### B-021: A test assumed the shared user could reach the login check
- **Date found:** 2026-10-06
- **Phase:** 9
- **What happened:** A test that logged in as `demo@open.local` got `422`, not `401`.
- **Root cause:** The email check rejects the reserved `.local` domain before any password is looked at. The test was wrong, and the real behaviour is safer than the one I had assumed.
- **Fix:** The test now accepts either answer for that address, and a separate test feeds junk hash values straight to `verify_password` to cover the crash it was meant to catch (D-056).
- **Status:** fixed

### B-002: Test client deprecation warning
- **Date found:** 2026-10-06
- **Phase:** 1 (Skeleton)
- **What happened:** pytest prints `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
- **Root cause:** The installed Starlette prefers a different HTTP client for its test client.
- **Fix:** Not yet. Harmless for now. Check whether `httpx2` is the right swap before changing.
- **Status:** open (low priority)

---

## Open questions
- Python or Node/TypeScript for the backend? (Assumed Python.)
- Real scan files available, or generate test files?
- What size limit for uploads? (Assumed 200 MB.)
