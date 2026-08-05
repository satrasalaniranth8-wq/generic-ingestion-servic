# Generic Data Ingestion Service

A config-driven service that ingests data from arbitrary REST APIs and
persists it, without being written for any one source. Adding a new source
means writing a YAML file, not touching code.

## How to run it

**Option A — Docker Compose (single command, includes Postgres):**

```bash
docker compose up --build
```

The API is then live at `http://localhost:8000`. Interactive docs (Swagger)
at `http://localhost:8000/docs`.

**Option B — locally:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Defaults to a local SQLite file (`ingestion.db`) if `DATABASE_URL` isn't set,
so no external services are required to try it.

### Trigger ingestion

```bash
# List configured sources
curl localhost:8000/sources

# Trigger a run
curl -X POST localhost:8000/ingest/rickandmorty
curl -X POST localhost:8000/ingest/reqres
curl -X POST localhost:8000/ingest/dummyjson

# Observe results
curl localhost:8000/runs
curl localhost:8000/records/rickandmorty?limit=5
```

### Run tests

```bash
pip install -r requirements.txt
pytest tests/
```

Tests mock the HTTP layer (response shapes modeled on the real APIs) so they
run offline and exercise the real pagination/auth/extraction/persistence
code paths.

## The public APIs used

Two structurally different APIs, plus a bonus third, to prove the design is
genuinely generic:

| Source | Auth | Pagination |
|---|---|---|
| [Rick and Morty API](https://rickandmortyapi.com/) | none | cursor URL embedded in response (`info.next`) |
| [ReqRes](https://reqres.in/) | API key in header (`x-api-key`) | page number, bounded by a `total_pages` field |
| [DummyJSON](https://dummyjson.com/) (bonus) | none | offset/limit (`skip`/`limit`) |

Each is fully described in `configs/*.yaml` — no source-specific code exists
anywhere in `app/`.

## Architecture

```
configs/*.yaml  →  SourceConfig (pydantic)
                         │
                    IngestionPipeline
                         │
        ┌────────────────┼────────────────┐
   AuthStrategy   PaginationStrategy   Fetcher (retries,
   (auth.py)      (pagination.py)      backoff, rate limit)
                         │
                  extract_records() (extract.py)
                         │
                    Sink[] (sinks/)
                    ├── DBSink   → generic ingested_records table
                    └── FileSink → JSONL on disk (S3 stand-in)
```

**Config, not code, defines a source.** A `SourceConfig` (`app/config.py`)
declares base URL, endpoint, auth style, pagination style, and where in the
JSON response the records + a "next page" signal live (via simple dot-paths,
e.g. `info.next`, `results`). The pipeline (`app/pipeline.py`) only ever
talks to these declarative shapes plus three small strategy interfaces —
it has no knowledge of Rick and Morty, ReqRes, or anything else.

**Auth and pagination are pluggable strategies**, each behind a common
interface (`AuthStrategy.apply`, `PaginationStrategy.first_request` /
`.next_request`). Four pagination styles are implemented (none, offset/limit,
page-number-with-total, cursor URL); adding e.g. `Link`-header pagination or
OAuth2 client-credentials means adding one class, not touching the pipeline.

**Storage is schema-agnostic by design.** Since sources are arbitrary and
unknown ahead of time, `IngestedRecord` stores each record as JSON
(`source_name`, `external_id`, `payload`) rather than one table per source.
This is the tradeoff that buys generality: no schema migration is needed for
a new source, at the cost of not getting typed columns / native SQL
filtering on record fields for free. A `record_id_path` per source drives
idempotent upserts; records with no natural id fall back to a content hash
so re-ingesting the same data doesn't duplicate rows.

**Destination is a `Sink` interface**, not a hardcoded DB call. Two sinks run
side-by-side out of the box: `DBSink` (Postgres/SQLite via SQLAlchemy — swap
via `DATABASE_URL`, zero code changes) and `FileSink` (local JSONL, a stand-in
for object storage). `sinks/file_sink.py` includes the ~10-line diff an S3
sink would actually be, to make the extensibility claim concrete rather than
theoretical.

**Handling real-API realities:** per-source timeout, retry with exponential
backoff on connection errors and 5xx (via `tenacity`), honoring `Retry-After`
on 429s, a client-side requests/sec limiter, and a hard `max_pages` safety
cap so a misbehaving or misconfigured pagination config can't loop forever.
4xx errors (except 429) fail fast rather than retrying, since retrying a bad
request just wastes the target API's time.

## Tradeoffs and assumptions

- **Synchronous ingestion triggered via HTTP POST**, run inline in the
  request. Fine for a demo and for APIs with a few hundred records; for
  large/slow sources this should be a background job (Celery/RQ, or just
  `BackgroundTasks`) with the endpoint returning a run ID immediately. I
  called this out rather than build a job queue in two days.
- **Dot-path resolver instead of full JSONPath.** Covers every case the demo
  sources need; a source with a genuinely irregular shape (e.g. "records
  live under whichever of these three keys is present") would need a real
  JSONPath library or a small per-source transform hook.
- **No schema validation/typing per record** — by design (see above), since
  the whole point is not knowing the shape ahead of time. A consumer of
  `ingested_records` needs to know the source's shape to query `payload`
  meaningfully (Postgres JSONB queries work fine here; SQLite less so).
- **Auth secrets** are read from env vars via `${VAR}` / `${VAR:-default}`
  syntax in the YAML, never hardcoded — but there's no secret-store
  integration (Vault/Secrets Manager), which I'd add before this touched
  real production credentials.
- **No dedicated ingestion-log/dead-letter table for partial-page failures**
  — a run currently succeeds or fails as a whole. Partial success (e.g. page
  7 of 20 fails) does persist pages 1–6 already saved, but doesn't
  auto-resume from page 7 on retry.

## What I'd do with more time

- Background job execution + scheduling (cron-style recurring ingestion per
  source) instead of synchronous trigger-and-wait.
- Incremental/delta ingestion (an `updated_since` param wired into a
  source's query params from the last successful run's timestamp) instead of
  full re-pull every time.
- A real S3 sink (swap-in shown in `file_sink.py`'s docstring) plus a
  streaming/message-queue sink for downstream consumers.
- Per-source field-level schema hints (optional, not required) to enable
  typed columns for sources where the caller does know the shape and wants
  fast SQL filtering instead of only JSON queries.
- Structured run-level and page-level logs shipped somewhere queryable, and
  metrics (pages/sec, error rate per source) for real operational visibility.
- Resume-from-failure for partially completed multi-page runs.

## Note on AI tool use

I used Claude to scaffold this project — the strategy-pattern structure
(auth/pagination/sink interfaces), the FastAPI wiring, and the SQLAlchemy
models were AI-assisted, then reviewed and adjusted.

**One place it got something wrong, and how I caught it:** the first draft
of `OffsetLimitPagination.next_request` decided whether to fetch another page
by inspecting the raw HTTP response itself — trying `response_json.get("data")
or response_json.get("products")` to guess where the records list lived, so
it could check whether the page came back short. That's exactly the kind of
source-specific guessing the whole design is supposed to avoid: it would
silently break on any API whose records live somewhere else. I caught it
during review by asking "what happens on a source where the top-level key is
neither `data` nor `products`?" and tracing it through by hand. The fix was
architectural, not a one-line patch: the pipeline already computes the
extracted record list once per page via each source's own `records_path`
config, so I changed the `PaginationStrategy.next_request` interface to
receive that already-extracted list instead of the raw response, and updated
all four strategy implementations and the pipeline call site to match. That
removed the guessing entirely and is covered by
`test_page_number_pagination_respects_total_pages` /
`test_cursor_url_pagination_ingests_all_pages` in `tests/test_pipeline.py`.

I also want to be upfront about a real constraint on my end: my sandbox
environment for this write-up had no outbound network access, so I could not
`pip install` the dependencies or make live calls to Rick and Morty/ReqRes/
DummyJSON to test end-to-end here. I mitigated this by (a) unit-testing the
dependency-free `extract.py` module directly (dot-path resolution, list
normalization, id-hash fallback — all passing), and (b) writing
`tests/test_pipeline.py` to mock the HTTP layer with response shapes copied
from each API's real documented format, exercising the actual
pagination/auth/persistence code paths end-to-end offline. Both are
runnable and passing; I'd still run a live `docker compose up` smoke test
against the real endpoints before calling this done in a real work setting.
