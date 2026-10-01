# devops

Workspace rules, typography, and commits: see `../CLAUDE.md`.

## What devops owns

- The release train (`train.yml`, `scripts/train.py`): after any release it releases what lies downstream in `graph.yml`.
- The composite actions every `release.yml` calls: `.github/actions/prepare`, `central`, `finish`. Callers use them at `@master`, so a change here reaches every repository's next release at once. Keep inputs and outputs backward compatible.
- `meta.json` (`meta.yml`, `scripts/meta.py`): the component list the launcher downloads, at R2 key `launcher/meta.json`, served as `https://ancaria.dev/files/launcher/meta.json`.
- Lines-of-code badges (`cloc.yml`, `scripts/cloc.py`): R2 keys `badges/<repo>.json`.
- Never put application code, version files, or pins here. A version exists only as a tag `v<version>` with a GitHub Release.

## Graph

- `graph.yml` `repos` lists every repository the train may release; `edges` say who must follow whom. An edge's `input` is the `release.yml` input the downstream reads the upstream version from. An edge with `paths` propagates only when a file matching one of them (`**` crosses directories) changed between the upstream's previous tag and its new one; with no previous tag it always propagates.
- A downstream repository is released once, after all its released upstreams, at its own highest tag plus a patch (`1.3.0-rc.1` becomes `1.3.0`) unless `versions` names it.
- To add a repository: give it a `release.yml` that follows the contract, then add it to `repos`. To add an edge: add the matching input to the downstream's `release.yml` first, then the edge. Add a `meta.components` entry only for something the launcher downloads.
- `scripts/cloc.py` keeps its own list of code repositories (`REPOS`); add new code repositories there too.
- `python -m unittest` must pass. Planning (`walk`, `topo_order`, `preview`) is pure; keep GitHub calls in `GitHub` and `Train`.

## Idempotency

- Every step must survive a rerun of a finished or half-finished job.
- `prepare` says `done=true` only for a published (not draft) release. `finish` creates a draft, uploads with `--clobber`, then publishes it, so a failed upload leaves a draft the rerun completes.
- The train skips a repository whose target release is already published. A rerun keeps `GITHUB_RUN_ID`, so it finds its earlier dispatches by the run title `Release <version> · train <id>` and reuses their versions instead of bumping again. Never change that title format without changing `train_run_version`.
- `meta.py` uploads only when `meta.json` differs from the live file. Badges are always overwritten.

## Secrets and variables

- Org variable `DEVOPS_APP_ID` and org secret `DEVOPS_APP_KEY`: a GitHub App with Contents read and write and Actions read and write, installed on every ancaria-dev repository. `finish` uses it to start the train; the train uses it to dispatch and watch releases; `cloc` uses it to read private repositories.
- In devops: `CLOUDFLARE_API_TOKEN` (R2 write on `ancaria-files`) and `CLOUDFLARE_ACCOUNT_ID`.
- Pin `wrangler` to an exact version in both upload steps.

## Local checks

- `python scripts/train.py --dry-run --versions "coderpack=2.1.0"` prints the plan with your own `gh` login and dispatches nothing.
- `actionlint` lints the workflows; it does not read the composite actions, so run `shellcheck` on their scripts after changing them.
