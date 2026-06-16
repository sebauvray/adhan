"""Provider docker control — spawn/stop the chosen audio provider container.

The api container has /var/run/docker.sock mounted and the docker CLI installed,
so we can drive `docker compose` from here. The compose file + .env + sibling
folders live under /compose/ (read-only mounts). We use --project-name to make
sure the spawned containers join the same compose project (and thus share
volumes/networks named `adhan_*`).

Bootstrap state (idle | starting | bootstrapping | ready | failed) is held
in a process-local dict + threading.Lock so the wizard can poll progress.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .base import MusicAssistantAlreadyConfigured

logger = logging.getLogger("audio.runner")


COMPOSE_DIR = os.environ.get("COMPOSE_DIR", "/compose")
COMPOSE_FILE = os.path.join(COMPOSE_DIR, "docker-compose.yml")
COMPOSE_PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "adhan")

PROVIDER_HEALTH_URLS = {
    "owntone": "http://host.docker.internal:3689/api/config",
    "music-assistant": "http://host.docker.internal:8095/info",
}

START_TIMEOUT_SECONDS = 60
HEALTH_POLL_INTERVAL = 1.5


@dataclass
class StartStatus:
    """Snapshot of the in-flight (or last) provider start."""
    provider: str = ""
    state: str = "idle"  # idle | starting | bootstrapping | ready | failed
    message: str = ""
    started_at: float = 0.0
    error: Optional[str] = None
    # Machine-readable failure reason for cases the UI handles specially
    # (e.g. "ma_already_configured" → offer a clean-reinstall choice).
    error_code: Optional[str] = None


_status = StartStatus()
_lock = threading.Lock()
_thread: Optional[threading.Thread] = None


def get_status() -> dict:
    with _lock:
        return {
            "provider": _status.provider,
            "state": _status.state,
            "message": _status.message,
            "started_at": _status.started_at,
            "error": _status.error,
            "error_code": _status.error_code,
        }


def _set_status(**kwargs) -> None:
    with _lock:
        for k, v in kwargs.items():
            setattr(_status, k, v)


def _docker_available() -> bool:
    return shutil.which("docker") is not None and os.path.exists("/var/run/docker.sock")


def _compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Run `docker compose -f <file> -p <project> ...`. Raises CalledProcessError on failure."""
    cmd = [
        "docker", "compose",
        "-f", COMPOSE_FILE,
        "-p", COMPOSE_PROJECT,
        *args,
    ]
    logger.info("compose: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        check=True,
        capture_output=capture,
        text=True,
        cwd=COMPOSE_DIR,
    )


PROVIDER_CONTAINER_NAMES = {
    "owntone": "adhan-owntone",
    "music-assistant": "adhan-music-assistant",
}


def _container_running(name: str) -> bool:
    """True iff the named container is in a 'running' state on the docker daemon.
    Guards against false-positive healthchecks where another service on the
    host happens to answer on the same port (e.g. user's standalone MA)."""
    try:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True, text=True, timeout=5,
        )
        return out.returncode == 0 and out.stdout.strip() == "true"
    except Exception:
        return False


def _wait_for_health(provider: str) -> bool:
    """Wait for the provider container to be up AND answering on its healthcheck URL.

    Both checks matter:
    - Container check rules out the case where the URL is answered by an
      unrelated service on the host (port conflict situation)
    - HTTP check ensures the provider has finished booting and is ready to serve
    """
    import urllib.request
    url = PROVIDER_HEALTH_URLS.get(provider)
    container = PROVIDER_CONTAINER_NAMES.get(provider)
    deadline = time.time() + START_TIMEOUT_SECONDS
    while time.time() < deadline:
        if container and not _container_running(container):
            time.sleep(HEALTH_POLL_INTERVAL)
            continue
        if not url:
            return True
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(HEALTH_POLL_INTERVAL)
    return False


def _stop_other_providers(active: str) -> None:
    """Stop containers from other audio profiles so only the chosen one runs."""
    for other in PROVIDER_HEALTH_URLS:
        if other == active:
            continue
        try:
            subprocess.run(
                ["docker", "compose",
                 "-f", COMPOSE_FILE,
                 "-p", COMPOSE_PROJECT,
                 "--profile", other,
                 "stop", other],
                cwd=COMPOSE_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.warning("Could not stop %s: %s", other, e)


def _start_provider_thread(provider: str, on_ready) -> None:
    """Background worker: launch the provider container, wait for health, then
    invoke `on_ready(provider)` for follow-up work like MA bootstrap."""
    try:
        if not _docker_available():
            _set_status(state="failed", error="docker socket non monté")
            return

        _set_status(state="starting", message=f"Démarrage du container {provider}…")
        _stop_other_providers(provider)
        _compose("--profile", provider, "up", "-d", provider)

        _set_status(state="starting", message="Attente de la disponibilité du service…")
        if not _wait_for_health(provider):
            _set_status(state="failed", error=f"{provider} n'a pas répondu dans les {START_TIMEOUT_SECONDS}s")
            return

        if on_ready:
            try:
                _set_status(state="bootstrapping", message="Configuration automatique…")
                on_ready(provider)
            except MusicAssistantAlreadyConfigured as e:
                logger.warning("MA already configured with different credentials: %s", e)
                _set_status(state="failed", error=str(e), error_code="ma_already_configured")
                return
            except Exception as e:
                logger.exception("Bootstrap failed for %s", provider)
                _set_status(state="failed", error=f"bootstrap: {e}")
                return

        _set_status(state="ready", message="Prêt")
    except subprocess.CalledProcessError as e:
        logger.exception("docker compose failed")
        _set_status(state="failed", error=(e.stderr or str(e))[:300])
    except Exception as e:
        logger.exception("Unexpected error starting provider")
        _set_status(state="failed", error=str(e))


def start_provider(provider: str, on_ready=None) -> dict:
    """Kick off a background start. Returns immediately with the initial status.
    `on_ready(provider)` is called once the container is healthy, useful for MA bootstrap."""
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return {"already_running": True, **get_status()}
        _status.provider = provider
        _status.state = "starting"
        _status.message = "Préparation…"
        _status.started_at = time.time()
        _status.error = None
        _status.error_code = None
        _thread = threading.Thread(
            target=_start_provider_thread,
            args=(provider, on_ready),
            daemon=True,
        )
        _thread.start()
    return get_status()


def stop_provider(provider: str) -> None:
    """Best-effort container stop (used when switching providers)."""
    if not _docker_available():
        return
    try:
        _compose("--profile", provider, "stop", provider)
    except subprocess.CalledProcessError:
        pass


# Named volumes holding a provider's persistent state. Removing one resets the
# provider to a pristine, never-installed state (used by "start fresh").
PROVIDER_DATA_VOLUMES = {
    "music-assistant": "ma-data",
}


def reset_provider_data(provider: str) -> None:
    """Stop the provider and delete its data volume, so the next start onboards
    from scratch. Used when MA was already onboarded with unknown credentials.

    Raises RuntimeError if docker isn't available or the volume can't be removed
    (other than 'not found', which is fine — nothing to reset)."""
    if not _docker_available():
        raise RuntimeError("docker indisponible — impossible de réinitialiser le provider")

    volume_suffix = PROVIDER_DATA_VOLUMES.get(provider)
    if not volume_suffix:
        raise RuntimeError(f"Aucun volume de données à réinitialiser pour {provider}")

    stop_provider(provider)

    volume = f"{COMPOSE_PROJECT}_{volume_suffix}"
    result = subprocess.run(
        ["docker", "volume", "rm", volume],
        capture_output=True, text=True,
    )
    if result.returncode != 0 and "no such volume" not in result.stderr.lower():
        raise RuntimeError(f"Échec suppression du volume {volume} : {result.stderr.strip()}")
    logger.info("Reset provider data: removed volume %s", volume)
