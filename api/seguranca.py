"""Proteções aplicadas a todas as respostas e requisições do app.

- Cabeçalhos de segurança (CSP, anti-frame, nosniff, HSTS em HTTPS, política de referência).
- Limite de tamanho do corpo das requisições, verificado enquanto o corpo chega
  (não depende do cabeçalho Content-Length, que o cliente pode omitir ou falsificar).
- Limite de requisições por cliente, em memória (o serviço roda em uma instância só).
"""

import json
import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

TAMANHO_MAXIMO_CORPO = 256 * 1024  # 256 KB: sobra para a maior descrição aceita (20 mil caracteres)

# páginas e API: só recursos do próprio site; nada de scripts de terceiros ou inline
CSP_PADRAO = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
# a documentação automática (/docs, /redoc) carrega o Swagger/ReDoc de uma CDN e usa script inline
CSP_DOCUMENTACAO = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    """Middleware ASGI: cabeçalhos de segurança e limite de tamanho do corpo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        caminho = scope.get("path", "")
        https = scope.get("scheme") == "https" or _https_pelo_proxy(scope)

        # recusa logo pelo Content-Length, sem ler o corpo
        for nome, valor in scope.get("headers", []):
            if nome == b"content-length" and valor.isdigit() and int(valor) > TAMANHO_MAXIMO_CORPO:
                await _responder_413(send)
                return

        recebidos = 0
        corpo_grande = False
        resposta_substituida = False

        async def receber():
            # corpo sem Content-Length (chunked): conta enquanto chega e corta ao passar do limite
            nonlocal recebidos, corpo_grande
            if corpo_grande:
                return {"type": "http.disconnect"}
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebidos += len(mensagem.get("body", b""))
                if recebidos > TAMANHO_MAXIMO_CORPO:
                    corpo_grande = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return mensagem

        async def enviar(mensagem):
            nonlocal resposta_substituida
            if corpo_grande:
                # descarta a resposta do app (que viu um corpo cortado) e responde 413
                if not resposta_substituida:
                    resposta_substituida = True
                    await _responder_413(send)
                return
            if mensagem["type"] == "http.response.start":
                cabecalhos = list(mensagem.get("headers", []))
                documentacao = caminho.startswith(("/docs", "/redoc"))
                cabecalhos += [
                    (b"content-security-policy", (CSP_DOCUMENTACAO if documentacao else CSP_PADRAO).encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                ]
                if https:
                    cabecalhos.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                if caminho.startswith("/casos"):
                    # descrições de casos nunca ficam em cache de navegador ou de proxy
                    cabecalhos.append((b"cache-control", b"no-store"))
                mensagem = {**mensagem, "headers": cabecalhos}
            await send(mensagem)

        await self.app(scope, receber, enviar)


def _https_pelo_proxy(scope) -> bool:
    """Atrás do proxy do Render, o HTTPS termina no proxy; ele informa o protocolo original."""
    if os.environ.get("CONFIAR_PROXY") != "1":
        return False
    for nome, valor in scope.get("headers", []):
        if nome == b"x-forwarded-proto":
            return valor.decode("latin-1").split(",")[-1].strip() == "https"
    return False


async def _responder_413(enviar) -> None:
    corpo = b'{"detail":"A requisi\\u00e7\\u00e3o \\u00e9 grande demais."}'
    await enviar(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(corpo)).encode()),
                (b"x-content-type-options", b"nosniff"),
            ],
        }
    )
    await enviar({"type": "http.response.body", "body": corpo})


def ip_do_cliente(request: Request) -> str:
    """IP de quem fez a requisição.

    Atrás do proxy do Render (CONFIAR_PROXY=1), o IP real está no X-Forwarded-For. Usa o
    último valor da lista, que é o anexado pelo proxy: os valores à esquerda podem ter sido
    enviados pelo próprio cliente para falsificar o IP. Sem CONFIAR_PROXY, o cabeçalho é
    ignorado, porque qualquer um poderia escrevê-lo.
    """
    if os.environ.get("CONFIAR_PROXY") == "1":
        encaminhado = request.headers.get("x-forwarded-for", "")
        ultimos = [ip.strip() for ip in encaminhado.split(",") if ip.strip()]
        if ultimos:
            return ultimos[-1]
    return request.client.host if request.client else "desconhecido"


class RateLimiter:
    """Janela deslizante: no máximo `limite` requisições por cliente e `limite_global` no total,
    a cada `janela` segundos. O teto global protege mesmo contra quem usa vários IPs."""

    def __init__(self, nome: str, limite: int, janela: float, limite_global: int | None = None):
        self.nome, self.limite, self.janela = nome, limite, janela
        self.limite_global = limite_global
        self._chamadas: dict[str, deque] = defaultdict(deque)
        self._todas: deque = deque()
        self._trava = Lock()

    def _recusar(self, espera: float, mensagem: str) -> None:
        segundos = int(espera) + 1
        raise HTTPException(status_code=429, detail=mensagem.format(segundos=segundos), headers={"Retry-After": str(segundos)})

    def __call__(self, request: Request) -> None:
        cliente = ip_do_cliente(request)
        agora = time.monotonic()
        with self._trava:
            chamadas = self._chamadas[cliente]
            for fila in (chamadas, self._todas):
                while fila and agora - fila[0] > self.janela:
                    fila.popleft()
            if len(chamadas) >= self.limite:
                self._recusar(self.janela - (agora - chamadas[0]), "Muitas requisições seguidas. Tente de novo em {segundos} segundos.")
            if self.limite_global is not None and len(self._todas) >= self.limite_global:
                self._recusar(self.janela - (agora - self._todas[0]), "O serviço está recebendo muitos envios agora. Tente de novo em {segundos} segundos.")
            chamadas.append(agora)
            self._todas.append(agora)
            if len(self._chamadas) > 10_000:  # evita crescer sem limite com muitos IPs diferentes
                for chave in [c for c, fila in self._chamadas.items() if not fila]:
                    del self._chamadas[chave]

    def limpar(self) -> None:
        """Usado pelos testes."""
        with self._trava:
            self._chamadas.clear()
            self._todas.clear()
