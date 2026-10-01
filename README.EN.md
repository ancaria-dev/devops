<div align="center">

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://docs.github.com/actions)
[![Sacred](https://img.shields.io/badge/Sacred-Community-8B1A1A?style=for-the-badge&labelColor=1C1410)](https://ancaria.dev)
[![License](https://img.shields.io/badge/License-MIT-4B5563?style=for-the-badge)](LICENSE)

[Русский](README.md) · [Deutsch](README.DE.md)

</div>

# devops

[![Lines of code](https://img.shields.io/endpoint?url=https%3A%2F%2Fancaria.dev%2Ffiles%2Fbadges%2Fdevops.json)](https://github.com/ancaria-dev/devops)

The ancaria release pipeline, for me and everyone who helps ship the loader.

Every repository releases with a button: you type a version, and its
`release.yml` builds, publishes, and creates the GitHub Release. There are no
version files and no pinned sibling versions anymore. A version exists only as
a `v<version>` tag with its release.

After any release, devops releases what depends on it, in the right order.
Then it refreshes `meta.json`, which tells the launcher which components to
download. Once a day it also recounts the lines of code behind the README
badges.

## Getting started

To release one repository:

1. Open its Actions tab and pick the `release` workflow.
2. Press Run workflow and type a version, such as `2.1.0` or `2.1.0-rc.1`.
3. Wait for the run to turn green. devops does the rest.

To release several repositories, or all of them:

1. Open the `train` workflow in devops.
2. List the versions in `versions`, separated by spaces:
   `coderpack=2.1.0 protocol=2.0.1`. `all=2.0.0` releases every repository in
   `graph.yml` at one version.
3. Tick `dry-run` first: the train prints its plan and releases nothing.

A run that failed halfway can simply be rerun. Every step checks what’s
already done and finishes the rest without duplicates.

## What happens after a release

The `finish` step of `release.yml` starts devops’ `train.yml` with
`released=<repo>@<version>`. The train reads `graph.yml` and walks it top
down:

| From | To | When |
|---|---|---|
| `mappings` | `agent` | after every release |
| `coderpack` | `build` | when `api`, `api-kotlin`, `api-skiko`, or `api-compose` changed |
| `build` | `idea` | after every release |

A downstream repository gets its own highest tag plus a patch, unless
`versions` names another version. It receives the upstream version through
the input named in `graph.yml`. Each repository releases once, after all its
released upstreams. The train waits for every run and stops at the first
failure.

## meta.json

At the end of a train, `meta.yml` builds `meta.json` from the latest
releases: the launcher’s `.exe`, `protocol.exe`, `api.jar` and `zygote.jar`
from coderpack, and `agent.zip` from agent. It reads `apiLevel` from
`Api.VERSION` at coderpack’s latest tag. When the file differs from the
published one, wrangler uploads it to R2, and the launcher reads it from
`https://ancaria.dev/files/launcher/meta.json`.

You can also run `meta.yml` and `cloc.yml` by hand, without a release.

## Secrets and variables

| Name | Where | What |
|---|---|---|
| `DEVOPS_APP_ID` | organisation variable | the GitHub App’s ID |
| `DEVOPS_APP_KEY` | organisation secret | that app’s private key |
| `CLOUDFLARE_API_TOKEN` | devops secret | a token with R2 write access to the `ancaria-files` bucket |
| `CLOUDFLARE_ACCOUNT_ID` | devops secret | the Cloudflare account ID |

The GitHub App needs read and write access to Contents and Actions. Install it
on every ancaria-dev repository: releases start the train through it, and the
train starts releases and reads private repositories for the badges.

## Building

devops builds nothing. You can check it locally:

```sh
pip install pyyaml
python -m unittest
python scripts/train.py --dry-run --versions "coderpack=2.1.0"
```

The dry run uses your own `gh` login and starts nothing.

## Releases

devops has no releases. Repositories call its actions at `@master`, so a
change here reaches the next release of each of them.

## License

MIT, see [LICENSE](LICENSE).
