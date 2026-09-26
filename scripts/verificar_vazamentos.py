"""Procura vazamentos em todos os arquivos que iriam para o repositório. Roda antes de cada commit
e no CI; sai com erro se achar alguma coisa.

    python scripts/verificar_vazamentos.py

Verifica os arquivos versionados e os novos ainda não ignorados (git ls-files):
- arquivos que nunca devem ir para o git (.env, chaves, certificados, materiais/ com PDFs de
  legislação e dicionários de terceiros, diário local, PDFs além do conjunto de treinamento
  usado nos testes);
- segredos: chaves privadas, tokens (GitHub, AWS, Google, Slack, JWT), deploy hook do Render,
  URL de banco com senha, endereço de serviço da Aiven, atribuição de senha/token com valor;
- dados locais: caminhos do computador (C:\\Users\\..., /home/...) e e-mails pessoais;
- os valores do .env local (usuário, banco e senhas do MySQL de desenvolvimento) em qualquer arquivo;
- arquivos grandes demais (acima de 5 MB, fora os dados gerados conhecidos).
"""

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TAMANHO_MAXIMO = 5 * 1024 * 1024
GRANDES_PERMITIDOS = {"dados/fontes/dispositivos.json"}

ARQUIVOS_PROIBIDOS = re.compile(
    r"(^|/)\.env(\.|$)|\.(pem|key|p12|pfx|jks|kdbx)$|(^|/)id_(rsa|ed25519|ecdsa)|^materiais/|^docs/progresso\.md$"
)
PDF_PERMITIDO = "Conjunto de Treinamento - 10 Sentenças Judiciais.pdf"

SEGREDOS = {
    "chave privada": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "token do GitHub": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}",
    "chave da AWS": r"\bAKIA[0-9A-Z]{16}\b",
    "chave do Google": r"\bAIza[0-9A-Za-z_\-]{35}\b",
    "token do Slack": r"\bxox[abprs]-[0-9A-Za-z-]{10,}",
    "JWT": r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "deploy hook do Render": r"api\.render\.com/deploy/srv-[a-z0-9]+\?key=",
    "URL de banco com senha": r"\b(?:mysql|postgres(?:ql)?|mongodb(?:\+srv)?|redis)(?:\+\w+)?://[^:@/\s<>'\"]+:[^@/\s<>'\"$\{]+@",
    "serviço da Aiven": r"[a-z0-9-]+\.aivencloud\.com",
    "senha ou token com valor": (
        r"(?i)\b(?:password|passwd|senha|secret|token|api[_-]?key)\w*\s*[:=]\s*['\"][^'\"\s$\{]{12,}['\"]"
    ),
}
DADOS_LOCAIS = {
    "caminho do computador": r"(?i)\b[C-Z]:\\Users\\|/home/[a-z][\w.-]+/|/Users/[A-Z][\w.-]+/",
    "e-mail pessoal": r"\b[\w.+-]+@(?:gmail|hotmail|outlook|yahoo|icloud|live|bol|uol|terra)\.[a-z.]+\b",
}
# texto que casa com os padrões de propósito: as próprias regras deste arquivo e do CI
IGNORAR_LINHAS = re.compile(r"git grep -n -I -E|^\s*\"[a-zçãé -]+\":\s*r?\"|DADOS_LOCAIS|SEGREDOS")


def arquivos() -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=RAIZ, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return sorted({nome for nome in saida.split("\0") if nome and (RAIZ / nome).is_file()})


def valores_do_env() -> list[str]:
    """Valores do .env local com tamanho de credencial (usuário, banco, senhas)."""
    env = RAIZ / ".env"
    if not env.is_file():
        return []
    valores = []
    for linha in env.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            valor = linha.split("=", 1)[1].strip().strip("'\"")
            # a DATABASE_URL local é composta dos outros valores, que já são procurados um a um
            if len(valor) >= 5 and "://" not in valor:
                valores.append(valor)
    return valores


def verificar() -> list[str]:
    achados: list[str] = []
    padroes = {nome: re.compile(p) for nome, p in {**SEGREDOS, **DADOS_LOCAIS}.items()}
    locais = valores_do_env()
    for nome in arquivos():
        caminho = RAIZ / nome
        if ARQUIVOS_PROIBIDOS.search(nome):
            achados.append(f"{nome}: arquivo que não pode ir para o repositório")
            continue
        if nome.lower().endswith(".pdf") and nome != PDF_PERMITIDO:
            achados.append(f"{nome}: PDF fora do repositório (só o conjunto de treinamento é versionado)")
        if caminho.stat().st_size > TAMANHO_MAXIMO and nome not in GRANDES_PERMITIDOS:
            achados.append(f"{nome}: arquivo grande ({caminho.stat().st_size / 1e6:.1f} MB)")
        conteudo = caminho.read_bytes()
        if b"\0" in conteudo[:8000]:
            continue  # binário
        texto = conteudo.decode("utf-8", errors="replace")
        for numero, linha in enumerate(texto.splitlines(), 1):
            if IGNORAR_LINHAS.search(linha) and nome.startswith(("scripts/verificar_vazamentos", ".github/")):
                continue
            for tipo, padrao in padroes.items():
                if padrao.search(linha):
                    achados.append(f"{nome}:{numero}: {tipo}")
            for valor in locais:
                if re.search(rf"(?<![\w-]){re.escape(valor)}(?![\w-])", linha):
                    achados.append(f"{nome}:{numero}: valor do .env local")
    return achados


if __name__ == "__main__":
    encontrados = verificar()
    if encontrados:
        print("POSSÍVEIS VAZAMENTOS:")
        print("\n".join(f"  {achado}" for achado in encontrados))
        sys.exit(1)
    print(f"Nenhum vazamento encontrado ({len(arquivos())} arquivos verificados).")
