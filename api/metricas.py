"""Loga em JSON as ações que o estudante dispara pelos botões da página (calcular, corrigir,
enviar um caso, pesquisar...): data e hora, a ação, quanto demorou e o que foi enviado.

Só ações reconhecidas (ROTULOS_DE_ACAO) geram log; navegação de página, /saude e arquivos
estáticos não entram. Textos longos (a descrição de um caso, por exemplo, que pode ter dados
pessoais antes da anonimização) aparecem só pelo tamanho, nunca pelo conteúdo.
"""

import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs

TAMANHO_MAXIMO_CAMPO = 80

log = logging.getLogger("sergius.metricas")
log.propagate = False
if not log.handlers:
    _saida = logging.StreamHandler()
    _saida.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_saida)
log.setLevel(logging.INFO)

# (método, rota como o FastAPI a registrou) -> nome da ação, do jeito que o botão chama na página
ROTULOS_DE_ACAO = {
    ("POST", "/dosimetria/calcular"): "calcular pena",
    ("POST", "/ensino/comparar"): "corrigir resposta",
    ("POST", "/casos/previa"): "ver prévia da anonimização",
    ("POST", "/casos"): "enviar descrição do caso",
    ("DELETE", "/casos/{codigo}"): "excluir caso",
    ("GET", "/fontes/buscar"): "pesquisar na legislação",
    ("POST", "/agente/analisar"): "analisar indícios do caso",
    ("POST", "/agente/estrutura"): "trocar o crime sugerido",
    ("POST", "/agente/calcular"): "calcular pena sugerida pelo agente",
}


def _resumir(valor):
    """Textos longos viram só o tamanho: o corpo pode trazer a descrição de um caso, ainda
    sem anonimizar."""
    if isinstance(valor, str):
        return valor if len(valor) <= TAMANHO_MAXIMO_CAMPO else f"<texto de {len(valor)} caracteres>"
    if isinstance(valor, dict):
        return {chave: _resumir(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [_resumir(item) for item in valor]
    return valor


class MetricsMiddleware:
    """Middleware ASGI: uma linha de log em JSON por ação reconhecida (ROTULOS_DE_ACAO).

    Fica por dentro do SecurityHeadersMiddleware (que limita o tamanho do corpo): assim, o
    que este middleware guarda para logar já vem com o tamanho cortado, nunca o que o
    visitante mandou antes do corte.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        pedacos: list[bytes] = []

        async def receber():
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                pedacos.append(mensagem.get("body", b""))
            return mensagem

        resposta: dict = {}

        async def enviar(mensagem):
            if mensagem["type"] == "http.response.start":
                resposta["status"] = mensagem["status"]
            await send(mensagem)

        inicio = time.monotonic()
        await self.app(scope, receber, enviar)
        duracao_ms = round((time.monotonic() - inicio) * 1000, 1)

        rota = scope.get("route")
        modelo_da_rota = getattr(rota, "path", None)
        rotulo = ROTULOS_DE_ACAO.get((scope.get("method", ""), modelo_da_rota))
        if rotulo is None:
            return

        corpo_bruto = b"".join(pedacos)
        if corpo_bruto:
            try:
                enviado = _resumir(json.loads(corpo_bruto))
            except ValueError:
                enviado = f"<corpo de {len(corpo_bruto)} bytes, não é JSON>"
        else:
            # ações por GET (ex.: pesquisar na legislação) mandam os parâmetros na URL, não no corpo
            consulta = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="replace"))
            enviado = _resumir({chave: valores[0] for chave, valores in consulta.items()}) or None

        registro = {
            "data_hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "acao": rotulo,
            "rota": modelo_da_rota,
            "status": resposta.get("status"),
            "duracao_ms": duracao_ms,
            "enviado": enviado,
        }
        log.info(json.dumps(registro, ensure_ascii=False))
