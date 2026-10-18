"""CORS com origens relidas a cada request.

O ``CORSMiddleware`` do Starlette resolve ``allow_origins`` no import do
módulo. No caminho Docker isso até funciona (o ``.env`` já está carregado),
mas no Cloudflare Workers as vars/secrets do Worker só chegam por request —
é o ``worker_runtime.attach`` no primeiro middleware HTTP. Fixar a lista no
import significaria CORS lido do default (vazio) e o frontend bloqueado.

A subclasse abaixo relê ``settings.cors_origins`` por request, então a mesma
configuração vale nos dois caminhos. Credenciais ficam desligadas: a API não
usa cookies, e ``allow_credentials=True`` junto de origem refletida permitiria
requisição com credenciais de qualquer site.
"""

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import parse_cors_origins, settings


class SettingsCORSMiddleware(CORSMiddleware):
    """``CORSMiddleware`` com origens vindas de ``settings.cors_origins``."""

    def __init__(self, app: ASGIApp, **kwargs) -> None:
        # A lista inicial é só o default; ``__call__`` reavalia por request.
        kwargs["allow_origins"] = parse_cors_origins(settings.cors_origins)
        kwargs.setdefault("allow_credentials", False)
        super().__init__(app, **kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.allow_origins = parse_cors_origins(settings.cors_origins)
        await super().__call__(scope, receive, send)
