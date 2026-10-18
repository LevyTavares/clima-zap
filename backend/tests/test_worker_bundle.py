"""Guarda do bundle: o grafo de imports do Worker não pode trazer SQLAlchemy.

O bundle é montado a partir de ``backend/pyproject.toml``, que só lista o que o
Pyodide importa — SQLAlchemy + APScheduler + tzdata (~12 MB) ficam de fora e são
alcançados apenas pelo caminho Docker, via ``app.db.orm`` (import tardio).

Este teste roda num subprocesso se passando pelo workerd
(``sys.platform == "emscripten"``, que é como ``worker_runtime`` detecta o
runtime) com um import hook que barra os pacotes pesados. Se algum import de
topo voltar para o grafo do Worker, o teste falha aqui em vez de falhar no
deploy.
"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

_SCRIPT = """
import sys
import types

# Bibliotecas de terceiros primeiro (algumas ramificam por sys.platform).
import asyncio  # noqa: F401
import fastapi  # noqa: F401
import httpx  # noqa: F401
import pydantic  # noqa: F401

PESADOS = ("sqlalchemy", "apscheduler", "tzdata", "tzlocal")


class BloqueiaPesados:
    \"\"\"Import hook: qualquer tentativa de carregar um pacote pesado estoura.\"\"\"

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in PESADOS:
            raise ImportError(f"{fullname} nao pode entrar no bundle do Worker")
        return None


sys.platform = "emscripten"  # é assim que worker_runtime detecta o workerd
sys.meta_path.insert(0, BloqueiaPesados())

# SDK do Workers não está no venv dos testes: stub mínimo para importar o
# entrypoint real (backend/worker.py) e validar o grafo inteiro.
sdk = types.ModuleType("workers")
sdk.asgi = types.SimpleNamespace(entrypoint=lambda app: object)
sys.modules["workers"] = sdk

import worker  # noqa: E402,F401
from app.main import app  # noqa: E402,F401
from app.services import alert_history, persistence, weather_dispatch  # noqa: E402,F401

print("ok")
"""


def test_grafo_de_imports_do_worker_nao_carrega_sqlalchemy():
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONPATH": "."},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")
