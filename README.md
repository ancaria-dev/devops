<div align="center">

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://docs.github.com/actions)
[![Sacred](https://img.shields.io/badge/Sacred-Community-8B1A1A?style=for-the-badge&labelColor=1C1410)](https://ancaria.dev)
[![License](https://img.shields.io/badge/License-MIT-4B5563?style=for-the-badge)](LICENSE)

[English](README.EN.md) · [Deutsch](README.DE.md)

</div>

# devops

[![Lines of code](https://img.shields.io/endpoint?url=https%3A%2F%2Fancaria.dev%2Ffiles%2Fbadges%2Fdevops.json)](https://github.com/ancaria-dev/devops)

Релизный конвейер ancaria для меня и всех, кто помогает выпускать загрузчик.

Каждый репозиторий выпускается кнопкой: вы вводите версию, и его `release.yml`
собирает, публикует и создаёт GitHub Release. Файлов с версиями и закреплённых
версий соседей больше нет. Версия существует только как тег `v<версия>` с
релизом.

После любого релиза devops сам выпускает то, что от него зависит, в нужном
порядке. Затем он обновляет `meta.json`, из которого лаунчер узнаёт, какие
компоненты скачать. Раз в сутки он же пересчитывает строки кода для значков в
README.

## Что происходит после релиза

Шаг `finish` в `release.yml` запускает `train.yml` в devops с
`released=<репозиторий>@<версия>`. Поезд читает `graph.yml` и идёт по нему
сверху вниз:

| Откуда | Куда | Когда |
|---|---|---|
| `mappings` | `agent` | после каждого релиза |
| `coderpack` | `build` | если изменились `api`, `api-kotlin`, `api-skiko` или `api-compose` |
| `build` | `idea` | после каждого релиза |

Нижний репозиторий получает свой старший тег плюс патч, если `versions` не
задаёт другую версию. Версию верхнего он получает через input с тем же именем,
что и в `graph.yml`. Каждый репозиторий выходит один раз, после всех своих
выпущенных верхних. Поезд ждёт каждый запуск и останавливается на первой
ошибке.

## meta.json

В конце поезда `meta.yml` собирает `meta.json` из последних релизов:
`.exe` лаунчера, `protocol.exe`, `api.jar` и `zygote.jar` из coderpack,
`agent.zip` из agent. `apiLevel` он берёт из `Api.VERSION` на последнем теге
coderpack. Если файл отличается от опубликованного, wrangler загружает его в
R2, и лаунчер читает его по адресу
`https://ancaria.dev/files/launcher/meta.json`.

`meta.yml` и `cloc.yml` можно запустить и вручную, без релиза.

## Секреты и переменные

| Имя | Где | Что это |
|---|---|---|
| `DEVOPS_APP_ID` | переменная организации | ID GitHub App |
| `DEVOPS_APP_KEY` | секрет организации | закрытый ключ этого приложения |
| `CLOUDFLARE_API_TOKEN` | секрет devops | токен с правом записи в R2-бакет `ancaria-files` |
| `CLOUDFLARE_ACCOUNT_ID` | секрет devops | ID аккаунта Cloudflare |

GitHub App нужны права Contents и Actions на чтение и запись. Установите его
на все репозитории ancaria-dev: через него релизы запускают поезд, а поезд
запускает релизы и читает приватные репозитории для значков.

## Сборка

devops ничего не собирает. Проверить его можно локально:

```sh
pip install pyyaml
python -m unittest
python scripts/train.py --dry-run --versions "coderpack=2.1.0"
```

Пробный прогон работает с вашим входом в `gh` и ничего не запускает.

## Лицензия

MIT, см. [LICENSE](LICENSE).
