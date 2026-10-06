# Project Plan: 3D Scan Upload, Process, View

## What this is
A web service where a user uploads a 3D scan. The server checks the file, makes a much smaller preview copy in the background, and tracks its status. Once the preview is ready, the user opens it in a 3D viewer in the browser. Access is controlled by organization roles.

## Goals
- Upload a scan, process it, and view it, end to end.
- Show the status of every scan from upload to ready.
- Make the preview much smaller than the original. The target is about 90 percent smaller, and the real number gets measured and recorded.
- Offer a versioned REST API with generated docs.
- Control access with organization roles: owner, editor, viewer.
- Test the full upload path, bad files, and permissions.

## Scope
**In scope**
- One input format: PLY (point cloud or mesh).
- Output: a decimated GLB preview.
- Background processing with a worker.
- Local file storage behind a small storage interface.
- Email and password auth with a JWT.
- A plain viewer page built on Three.js.

**Out of scope**
- Payments, real-time collaboration, mobile, scan capture, annotations.
- OAuth and single sign-on.
- A polished UI.
- Other formats (OBJ, GLB input, E57, LAS). Maybe later, only if time is left.
- Cloud storage (S3 or MinIO). Optional, last.

## Stack
| Part | Choice |
|---|---|
| API | Python, FastAPI |
| Database | PostgreSQL, SQLAlchemy, Alembic (SQLite in tests if easier) |
| Queue | Redis with RQ |
| Processing | trimesh and Open3D (fallback: trimesh with fast-simplification, plus voxel downsampling for point clouds) |
| Viewer | Three.js, plain or with Vite |
| Tests | pytest, httpx |
| Running it | Docker Compose: API, worker, Postgres, Redis |

Check the current Open3D and trimesh docs before committing. Open3D wheels have lagged behind new Python versions before.

## Data model
- **users:** id, email, password hash
- **organizations:** id, name
- **memberships:** user, organization, role (`owner`, `editor`, `viewer`)
- **scans:** id, organization, uploaded_by, name, status, original_size, preview_size, reduction_pct, error_message, timestamps

### Status flow
`uploaded` -> `validating` -> `processing` -> `ready`
Any step can end in `failed` with a readable reason.
Only the worker moves a scan forward. A scan never moves backward.

## Roles
| Action | Viewer | Editor | Owner |
|---|---|---|---|
| View and list scans | yes | yes | yes |
| Upload scans | no | yes | yes |
| Delete scans | no | yes | yes |
| Manage members | no | no | yes |

All role checks live in one shared dependency that every route uses. No role logic inside individual handlers.

## API (v1)
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/orgs`
- `GET /api/v1/orgs/{id}`
- `POST /api/v1/orgs/{id}/members`, plus `PATCH` and `DELETE` for members
- `POST /api/v1/orgs/{id}/scans` (multipart upload, returns `202` with the scan id)
- `GET /api/v1/orgs/{id}/scans`
- `GET /api/v1/scans/{id}` (status and metadata)
- `GET /api/v1/scans/{id}/preview` (the GLB, permission checked)
- `DELETE /api/v1/scans/{id}`

One error shape everywhere: `{ "error": "code", "message": "..." }`.
Docs come from FastAPI's OpenAPI output, served at `/docs`.

## Validation
**At upload, before anything is queued**
1. Wrong extension or wrong magic header: `400`.
2. Empty file: `400`.
3. File over the size limit (for example 200 MB): `413`. Checked while streaming so the whole file is never held in memory.

**In the worker, which parses the file** (scan becomes `failed` with a message)
4. Corrupt or truncated PLY.
5. Zero vertices.
6. NaN or infinite coordinates.

## Processing pipeline
1. Load the file.
2. Mesh: decimate to a target triangle count. Point cloud: voxel downsample.
3. Export a GLB, with Draco compression if the exporter supports it.
4. Record original size, preview size, and `reduction_pct`.
5. Set the status to `ready`, or to `failed` with the error.

The 90 percent figure is a target, not a promise. Run the pipeline on 5 to 10 scans of different sizes and report the real average.

## Viewer
One page with a status badge. It polls the scan endpoint every couple of seconds while the status is `uploaded`, `validating`, or `processing`. When the status is `ready` it loads the GLB with `GLTFLoader` and `OrbitControls`. It also handles these states: loading, failed (shows the error), and permission denied.

## Tests
- **Full upload path:** register, create an org, upload a valid file, run the worker, poll until `ready`, fetch the preview.
- **Bad files:** wrong type, empty, oversized, corrupt, NaN. Each gets the right response or the right `failed` status.
- **Permissions:** a table-driven test that runs every endpoint as every role, plus a user from another org who must get `403` or `404`.
- **Processing unit tests:** the output is smaller and still loads.

## Build order
Each phase ends with something that runs. Nothing gets built until this plan is approved.

| Phase | Days | Work |
|---|---|---|
| 1. Skeleton | 1 | Repo, Docker Compose, FastAPI app, DB connection, health check, one passing test in CI |
| 2. Auth and orgs | 2-3 | Register, login, orgs, memberships, permission dependency, tests |
| 3. Upload and validation | 4-5 | Streaming upload, storage interface, scan record, early validation errors |
| 4. Worker and processing | 6-8 | Queue, status transitions, decimation, GLB export, size measurement |
| 5. Viewer | 9-10 | The page, polling, error states |
| 6. Hardening | 11-12 | Full permission matrix, bad-file tests, versioning cleanup, docs polish |
| 7. Write-up | 13 | README with a diagram, a short demo GIF, measured numbers |

If time runs short, cut in this order: cloud storage, extra formats, member-management endpoints. Never cut the tests or the permission checks.

## Repo layout
```
app/
  api/v1/        routes
  core/          config, security, permissions
  models/        database models
  services/      storage, validation, processing
  worker.py
viewer/          Three.js page
tests/
  test_upload_flow.py
  test_bad_files.py
  test_permissions.py
docs/
  LOG.md         bugs, design choices, trade-offs
docker-compose.yml
README.md
PLAN.md
```

## Definition of done
- `docker compose up` starts everything, and a fresh clone works from the README alone.
- `/docs` shows the generated API docs.
- All tests pass.
- The README states the real measured size reduction.
- `LOG.md` is current: every bug and every decision is written down.

## Open questions
- Python or Node/TypeScript for the backend? Current assumption: Python.
- Are there real scan files to test with, or should test files be generated?
