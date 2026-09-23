"""Cria o .env local (fora do git) com o usuário, o banco e as senhas do MySQL de desenvolvimento.

    python scripts/preparar_ambiente.py

Roda uma vez por máquina (e no CI). Se o .env já existir, só acrescenta o que faltar;
nunca troca uma senha já gerada. Nenhuma credencial fica no repositório, nem o nome do
usuário: numa máquina nova, usuário e banco também são sorteados.
"""

import secrets
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / ".env"


def main() -> None:
    atuais: dict[str, str] = {}
    if ARQUIVO.exists():
        for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                chave, valor = linha.split("=", 1)
                atuais[chave.strip()] = valor.strip()

    # .env criado antes de o usuário e o banco virem daqui: o MySQL local já existe com "app",
    # então esse nome continua (só no .env, fora do git) para o banco de testes seguir funcionando
    padrao = "app" if "DATABASE_URL" in atuais else None
    usuario = atuais.get("MYSQL_USUARIO") or padrao or f"app_{secrets.token_hex(4)}"
    banco = atuais.get("MYSQL_BANCO") or padrao or f"dev_{secrets.token_hex(4)}"
    senha_app = atuais.get("MYSQL_SENHA_APP") or secrets.token_urlsafe(24)
    novos = {
        "MYSQL_SENHA_ROOT": atuais.get("MYSQL_SENHA_ROOT") or secrets.token_urlsafe(24),
        "MYSQL_SENHA_APP": senha_app,
        "MYSQL_USUARIO": usuario,
        "MYSQL_BANCO": banco,
        # usada pelo notebook rodando na sua máquina (MySQL do docker compose na porta 33307; outros projetos costumam usar 3306/3307)
        "DATABASE_URL": atuais.get("DATABASE_URL") or f"mysql+pymysql://{usuario}:{senha_app}@127.0.0.1:33307/{banco}",
    }
    faltando = {k: v for k, v in novos.items() if k not in atuais}
    if not faltando:
        print(".env já está completo")
        return
    with ARQUIVO.open("a", encoding="utf-8") as arquivo:
        if not atuais:
            arquivo.write("# Gerado por scripts/preparar_ambiente.py. Fora do git: não compartilhe.\n")
        for chave, valor in faltando.items():
            arquivo.write(f"{chave}={valor}\n")
    print(".env atualizado com:", ", ".join(faltando))


if __name__ == "__main__":
    main()
