<div align="center">

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://docs.github.com/actions)
[![Sacred](https://img.shields.io/badge/Sacred-Community-8B1A1A?style=for-the-badge&labelColor=1C1410)](https://ancaria.dev)
[![License](https://img.shields.io/badge/License-MIT-4B5563?style=for-the-badge)](LICENSE)

[Русский](README.md) · [English](README.EN.md)

</div>

# devops

[![Lines of code](https://img.shields.io/endpoint?url=https%3A%2F%2Fancaria.dev%2Ffiles%2Fbadges%2Fdevops.json)](https://github.com/ancaria-dev/devops)

Die Release-Pipeline von ancaria, für mich und alle, die beim Veröffentlichen
des Loaders helfen.

Jedes Repository erscheint per Knopfdruck: Du gibst eine Version ein, und sein
`release.yml` baut, veröffentlicht und legt das GitHub Release an.
Versionsdateien und festgenagelte Versionen der Nachbarn gibt es nicht mehr.
Eine Version existiert nur als Tag `v<Version>` mit seinem Release.

Nach jedem Release veröffentlicht devops alles, was davon abhängt, in der
richtigen Reihenfolge. Danach erneuert es `meta.json`, aus der der Launcher
erfährt, welche Komponenten er herunterlädt. Einmal am Tag zählt es außerdem
die Codezeilen für die Badges in den READMEs neu.

## Was nach einem Release passiert

Der Schritt `finish` in `release.yml` startet `train.yml` in devops mit
`released=<Repository>@<Version>`. Der Zug liest `graph.yml` und geht es von
oben nach unten durch:

| Von | Nach | Wann |
|---|---|---|
| `mappings` | `agent` | nach jedem Release |
| `coderpack` | `build` | wenn sich `api`, `api-kotlin`, `api-skiko` oder `api-compose` geändert hat |
| `build` | `idea` | nach jedem Release |

Ein nachgelagertes Repository bekommt seinen eigenen höchsten Tag plus einen
Patch, außer `versions` nennt eine andere Version. Die Version des
vorgelagerten erhält es über den Input, den `graph.yml` nennt. Jedes
Repository erscheint einmal, nach all seinen veröffentlichten Vorgängern. Der
Zug wartet auf jeden Lauf und hält beim ersten Fehler an.

## meta.json

Am Ende eines Zugs baut `meta.yml` die `meta.json` aus den neuesten Releases:
die `.exe` des Launchers, `protocol.exe`, `api.jar` und `zygote.jar` aus
coderpack und `agent.zip` aus agent. `apiLevel` liest es aus `Api.VERSION` am
neuesten Tag von coderpack. Weicht die Datei von der veröffentlichten ab, lädt
wrangler sie nach R2, und der Launcher liest sie unter
`https://ancaria.dev/files/launcher/meta.json`.

`meta.yml` und `cloc.yml` kannst du auch ohne Release von Hand starten.

## Secrets und Variablen

| Name | Wo | Was |
|---|---|---|
| `DEVOPS_APP_ID` | Variable der Organisation | ID der GitHub App |
| `DEVOPS_APP_KEY` | Secret der Organisation | privater Schlüssel dieser App |
| `CLOUDFLARE_API_TOKEN` | Secret in devops | Token mit Schreibrecht auf den R2-Bucket `ancaria-files` |
| `CLOUDFLARE_ACCOUNT_ID` | Secret in devops | ID des Cloudflare-Kontos |

Die GitHub App braucht Lese- und Schreibrechte für Contents und Actions.
Installier sie auf allen Repositorys von ancaria-dev: Über sie starten
Releases den Zug, und der Zug startet Releases und liest private Repositorys
für die Badges.

## Bauen

devops baut nichts. Lokal prüfst du es so:

```sh
pip install pyyaml
python -m unittest
python scripts/train.py --dry-run --versions "coderpack=2.1.0"
```

Der Probelauf nutzt deine eigene Anmeldung bei `gh` und startet nichts.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
