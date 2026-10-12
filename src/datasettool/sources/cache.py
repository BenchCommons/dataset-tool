"""Download cache of source resources (spec 004, R2).

Each resource is cached at <cache>/<source_id>/<filename>, with <filename>.meta.json next to it.

Ported from BenchCommons/dataset-names@e7e8405 src/namescommons/cache.py.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path

from datasettool import REPOSITORY, __version__
from datasettool.sources.adapters import ID_PATTERN, Resource, is_safe_filename

BLOCK = 1 << 16
BACKOFF = 2.0  # seconds before the second attempt; doubles at each new attempt


def make_user_agent(name: str, version: str, url: str) -> str:
    """User-Agent that tells upstream operators who is downloading: '<name>/<version> (+<url>)'."""
    return f"{name}/{version} (+{url})"


DEFAULT_USER_AGENT = make_user_agent("tools-dataset", __version__, REPOSITORY)


class FetchError(Exception):
    """Failure to obtain a resource, from the network or from the cache."""


class BlockedError(FetchError):
    """The server returned an HTML page instead of the file (R2.6); retrying does not help."""


_PAGES = (".html", ".htm")


def cached_path(cache_dir: Path, source_id: str, filename: str) -> Path:
    """<cache_dir>/<source_id>/<filename>; ValueError unless both parts are safe and the path stays in the cache."""
    if not isinstance(source_id, str) or not ID_PATTERN.fullmatch(source_id):
        raise ValueError(f"invalid source id {source_id!r} (use [a-z0-9]+(-[a-z0-9]+)*)")
    if not is_safe_filename(filename):
        raise ValueError(f"invalid file name {filename!r} for the cache")
    root = Path(cache_dir)
    path = root / source_id / filename
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"{path} resolves outside the cache {root}")
    return path


def _write_atomic(dest: Path, content: bytes) -> None:
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(content)
    os.replace(tmp, dest)


def _download(url: str, dest: Path, timeout: float, user_agent: str) -> dict:
    """Download url to dest through a temporary file; return the metadata."""
    tmp = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    h = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()  # lowercase, without parameters
            if content_type == "text/html" and not dest.name.lower().endswith(_PAGES):
                raise BlockedError(f"the server returned an HTML page ({content_type}) instead of {dest.name}")
            with open(tmp, "wb") as fh:
                announced = response.headers.get("Content-Length")
                while block := response.read(BLOCK):
                    fh.write(block)
                    h.update(block)
                    size += len(block)
        if announced is not None:
            try:
                expected = int(announced)
            except ValueError:
                raise FetchError(f"Content-Length {announced!r} is invalid for {url}") from None
            if size != expected:
                raise FetchError(f"incomplete download of {url}: {size} of {announced} bytes")
        meta = {
            "url": url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": h.hexdigest(),
            "size": size,
        }
        # The old metadata goes before the new file comes in: a failure in between leaves the file
        # without metadata (the same state as a file saved by hand), never metadata describing another file.
        meta_file = dest.with_name(dest.name + ".meta.json")
        meta_file.unlink(missing_ok=True)
        os.replace(tmp, dest)
        _write_atomic(meta_file, (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return meta
    finally:
        tmp.unlink(missing_ok=True)


def _final(e: Exception) -> bool:
    """A 4xx (except 408 and 429) is a final answer from the server: trying again changes nothing."""
    return isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code not in (408, 429)


def fetch_resource(
    cache_dir: Path,
    source_id: str,
    resource: Resource,
    *,
    refresh: bool = False,
    offline: bool = False,
    timeout: float = 60.0,
    attempts: int = 3,
    backoff: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
    user_agent: str | None = None,
) -> Path:
    """Path of the resource in the cache, downloading it when needed (R2)."""
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, got {attempts}")
    backoff = BACKOFF if backoff is None else backoff
    user_agent = DEFAULT_USER_AGENT if user_agent is None else user_agent
    if offline and refresh:
        raise ValueError("--offline and --refresh are incompatible")
    dest = cached_path(cache_dir, source_id, resource.filename)
    if dest.is_file() and not refresh:
        return dest
    if offline:
        raise FetchError(f"{dest} missing from the cache and --offline prevents the download")
    dest.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for i in range(attempts):
        try:
            _download(resource.url, dest, timeout, user_agent)
            return dest
        except BlockedError as e:
            raise BlockedError(
                f"failed to download {resource.url}: {e}, probably an automatic-download block: "
                f"download the file with a browser, save it at {dest} and rerun with --offline"
            ) from e
        except (OSError, HTTPException, FetchError) as e:
            last = e
            done = i + 1
            if _final(e):
                break
            if done < attempts:
                sleep(backoff * 2**i)
    message = f"failed to download {resource.url} after {done} attempt(s): {last}"
    if isinstance(last, urllib.error.HTTPError) and last.code == 403:
        message += (
            "; the server refused the automatic download: download the file with a browser, "
            f"save it at {dest} and rerun with --offline"
        )
    raise FetchError(message)
