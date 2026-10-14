<div align="center">

# 🏰 battlecode-bot

**Champions, camps, gems and altars, fought by code.**

[![Build & Release](https://github.com/DE41H/battlecode-bot/actions/workflows/release.yml/badge.svg)](https://github.com/DE41H/battlecode-bot/actions/workflows/release.yml)
[![Lint](https://github.com/DE41H/battlecode-bot/actions/workflows/lint.yml/badge.svg)](https://github.com/DE41H/battlecode-bot/actions/workflows/lint.yml)
[![Release](https://img.shields.io/github/v/release/DE41H/battlecode-bot?include_prereleases&style=for-the-badge&color=ff69b4&label=latest%20bot)](https://github.com/DE41H/battlecode-bot/releases/latest)

![Python](https://img.shields.io/badge/python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=FFD43B)
![uv](https://img.shields.io/badge/uv-managed-DE5FE9?style=for-the-badge&logo=uv&logoColor=white)
![Ruff](https://img.shields.io/badge/ruff-styled-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)
![Pyright](https://img.shields.io/badge/pyright-typed-00C4B3?style=for-the-badge)
![WASI](https://img.shields.io/badge/target-WASI-654FF0?style=for-the-badge&logo=webassembly&logoColor=white)
![Zed](https://img.shields.io/badge/editor-zed-F97316?style=for-the-badge&logo=zedindustries&logoColor=white)
![MIT](https://img.shields.io/badge/license-MIT-22C55E?style=for-the-badge)

</div>

---

## ⚔️ The competition

**CAMBC 2026** (`cambc2026a`): you write the brain of a team of champions.

- 🎯 **Draft** 3 to 5 champions while the whole map is visible
- 👹 **Clear** monster camps, then **capture** them for 💎 gems and 🪙 gold
- 🛕 **Tribute** gems at altars; 🛡️ spend gold on items
- 🏆 **Win** by reaching **1,000 gems** first, or lead at round **2,000**

Full rules: [`GameRules.md`](GameRules.md) · Python API: [`BotAPIPython.md`](BotAPIPython.md)

## 🚀 Quick start

```bash
uv sync                                   # 🐍 Python 3.13 + dev tools
cambc run starter-python starter-python --view   # 🎮 local match + replay
```

## 📦 Submitting a bot

| | Option | How |
|---|---|---|
| 🟣 | **From a release** | Grab `<bot>.zip` from [Releases](https://github.com/DE41H/battlecode-bot/releases) → upload on the platform |
| 🟢 | **Bundle locally** | `cambc bundle <bot>` → upload `<bot>.zip` |
| 🔵 | **Straight from the CLI** | `cambc login` once, then `cambc submit <bot>` |

## 🔁 CI/CD

| Workflow | When | What |
|---|---|---|
| 🧹 [`lint.yml`](.github/workflows/lint.yml) | every push | `ruff check` + `ruff format --check` |
| 🏗️ [`release.yml`](.github/workflows/release.yml) | push to `main` | `cambc build` every bot → `cambc bundle` → GitHub release `build-<n>` with the ZIPs |

Fix style before you push: `uv run ruff format . && uv run ruff check --fix .`

## 🧰 Language & environment

- 🐍 **Python 3.13**: fastest to iterate on; compiled to WASI by `cambc` (SDK `2.1.6`)
- ⚡ **uv**: one lockfile pins Python and the tools, so CI matches your machine
- 🎨 **Ruff**: formatter and linter, with the rules in `pyproject.toml`
- 🔍 **Pyright**: resolves the `cambc` SDK from `sdk/python`, so Zed autocompletes it
- 🟧 **Zed**: picks all of the above up automatically

## 🗂️ Folder structure

```
🏰 battlecode-bot
├── 🤖 bots/              one folder per bot
│   └── starter-python/   reference bot (src/main.py is the entry point)
├── 🧩 sdk/               cambc SDKs (python, rust, cpp, ocaml) and templates
├── 🗺️ maps/              competition map pool (*.map26a)
├── ⚙️ .github/workflows/  lint + build & release
├── 📜 GameRules.md       game handbook
├── 📘 BotAPIPython.md    Python bot API
├── 🧪 cambc.toml         SDK version and languages
└── 🐍 pyproject.toml     uv, ruff and pyright config
```

<div align="center">

![Made with code and caffeine](https://img.shields.io/badge/made_with-☕_and_💎-8B5CF6?style=for-the-badge)

</div>
