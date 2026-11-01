# Contributing

Thanks for helping improve GhostyFlix RPC. Before opening an issue, search the existing [issues](https://github.com/GhostyGang/ghostyflix-rpc/issues) for a report of the same problem.

## Bug reports

Include your Windows version, GhostyFlix version, steps to reproduce, and what you expected to happen. If you include logs or screenshots, remove Jellyfin addresses, usernames, API keys, sign-in tokens, Quick Connect codes, and personal media details.

## Changes

Keep changes focused and describe the behavior they affect. For UI changes, include a screenshot when practical. Do not commit settings files, local logs, release executables, or credentials.

## Local build

Use Python 3.12 or newer and uv:

```powershell
uv sync --locked --extra gui --no-dev
uv run python -m ghostyflix_rpc
```

To package the Windows app:

```powershell
uv run pyinstaller --noconfirm main.spec
```

## Releases

The Windows release workflow runs when a `v*` tag is pushed. Keep the project version in `pyproject.toml` and `src/ghostyflix_rpc/__init__.py` aligned with the release tag. The workflow builds the executable, generates a SHA-256 checksum, and publishes both assets.
