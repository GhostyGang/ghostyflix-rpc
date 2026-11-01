from __future__ import annotations

import hashlib
import os
import base64
import re
import subprocess
import sys
import tempfile
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from .__init__ import __version__


@dataclass(slots=True)
class Release:
    version: str
    page: str
    executable_url: str
    digest: str
    notes: str


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r'\d+', value)[:4]) or (0,)


def find_release(repository: str) -> Release | None:
    owner_repo = repository.strip().strip('/')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', owner_repo):
        raise ValueError('Enter a GitHub repository as owner/name.')
    response = requests.get(
        f'https://api.github.com/repos/{owner_repo}/releases/latest',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'GhostyFlixRPC/2.0'},
        timeout=15,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    assets = data.get('assets') or []
    executable = next((asset for asset in assets if str(asset.get('name', '')).lower().endswith('.exe')), None)
    if executable is None:
        return None
    digest = str(executable.get('digest') or '')
    if digest.startswith('sha256:'):
        digest = digest.removeprefix('sha256:').lower()
    checksum = next((asset for asset in assets if str(asset.get('name', '')).lower() == 'sha256sums.txt'), None)
    if not digest and checksum:
        checksum_response = requests.get(checksum['browser_download_url'], timeout=15)
        checksum_response.raise_for_status()
        target_name = str(executable.get('name') or '').lower()
        for line in checksum_response.text.splitlines():
            value, _, filename = line.strip().partition('  ')
            if filename.lower() == target_name:
                digest = value.lower()
                break
    if not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise RuntimeError('The release has no valid SHA-256 checksum, so it cannot be installed safely.')
    return Release(
        version=str(data.get('tag_name') or '').lstrip('v'),
        page=str(data.get('html_url') or ''),
        executable_url=str(executable['browser_download_url']),
        digest=digest,
        notes=str(data.get('body') or ''),
    )


def is_newer(release: Release) -> bool:
    return version_key(release.version) > version_key(__version__)


def open_release_page(repository: str) -> None:
    webbrowser.open(f'https://github.com/{repository.strip().strip("/")}/releases/latest')


def download_release(release: Release, progress: Callable[[int], None] | None = None) -> Path:
    response = requests.get(
        release.executable_url,
        headers={'User-Agent': 'GhostyFlixRPC/2.0'},
        stream=True,
        timeout=(15, 60),
    )
    response.raise_for_status()
    total = int(response.headers.get('Content-Length') or 0)
    folder = Path(tempfile.mkdtemp(prefix='ghostyflix-update-'))
    package = folder / 'GhostyFlix-RPC.exe'
    digest = hashlib.sha256()
    written = 0
    with package.open('wb') as stream:
        for block in response.iter_content(chunk_size=256 * 1024):
            if not block:
                continue
            stream.write(block)
            digest.update(block)
            written += len(block)
            if progress and total:
                progress(min(99, int(written * 100 / total)))
    if digest.hexdigest().lower() != release.digest.lower():
        package.unlink(missing_ok=True)
        raise RuntimeError('The downloaded file did not match the release SHA-256 checksum.')
    if package.stat().st_size < 1_000_000:
        package.unlink(missing_ok=True)
        raise RuntimeError('The downloaded executable is unexpectedly small and was discarded.')
    if progress:
        progress(100)
    return package


def launch_replacement(package: Path) -> None:
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Install in-app updates from the packaged Windows application.')
    target = Path(sys.executable).resolve()
    source_text = str(package.resolve())
    target_text = str(target)
    quote_ps = lambda value: "'" + value.replace("'", "''") + "'"
    staged = target_text + '.new'
    failure_log = str(package.parent / 'update-error.txt')
    script = f'''$ErrorActionPreference = 'Stop'
$source = {quote_ps(source_text)}
$target = {quote_ps(target_text)}
$staged = {quote_ps(staged)}
$failureLog = {quote_ps(failure_log)}
$parentPid = {os.getpid()}
try {{
  while (Get-Process -Id $parentPid -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 300 }}
  Copy-Item -LiteralPath $source -Destination $staged -Force
  Move-Item -LiteralPath $staged -Destination $target -Force
  Start-Process -FilePath $target
  Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
}} catch {{
  Set-Content -LiteralPath $failureLog -Value $_.Exception.Message -Encoding UTF8
}}
'''
    command = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
    subprocess.Popen(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-EncodedCommand', command],
        cwd=str(package.parent), creationflags=flags,
    )
    time.sleep(0.2)
    os._exit(0)
