"""Executa o notebook de testes (tests/dosimetria_tests.ipynb) e imprime um resumo:
quantas verificações (assert) cada seção tem, quanto tempo levou e se passou. O mesmo
resumo também é gravado em JSON.

    python scripts/rodar_testes.py [--relatorio caminho.json] [--notebook-executado caminho.ipynb]

Roda célula a célula, na ordem do notebook: qualquer assert que falhar interrompe no
mesmo ponto (mesmo comportamento de "jupyter nbconvert --execute"), e o relatório mostra
até onde chegou.
"""

import argparse
import ast
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

RAIZ = Path(__file__).resolve().parent.parent
NOTEBOOK = RAIZ / "tests" / "dosimetria_tests.ipynb"


def contar_verificacoes(codigo: str) -> int:
    """Quantos `assert` tem no código da célula (contagem estática: uma vez por assert
    escrito, não por iteração de laço)."""
    try:
        arvore = ast.parse(codigo)
    except SyntaxError:
        return 0
    return sum(1 for no in ast.walk(arvore) if isinstance(no, ast.Assert))


def mapear_secoes(celulas: list) -> list[dict]:
    """Uma entrada por célula de código, com a seção (título "## ..." mais próximo acima)
    e quantas verificações ela tem."""
    mapeadas = []
    secao_atual = "(sem seção)"
    for indice, celula in enumerate(celulas):
        if celula["cell_type"] == "markdown":
            titulo = next((linha for linha in celula["source"].splitlines() if linha.startswith("## ")), None)
            if titulo:
                secao_atual = titulo.removeprefix("## ").strip()
        elif celula["cell_type"] == "code":
            mapeadas.append(
                {"indice": indice, "secao": secao_atual, "verificacoes": contar_verificacoes(celula["source"])}
            )
    return mapeadas


def limpar_execucao_anterior(nb) -> None:
    """Apaga contagem de execução e saídas de uma execução salva antes; assim, ao final,
    uma célula com execution_count preenchido é garantidamente desta execução."""
    for celula in nb.cells:
        if celula["cell_type"] == "code":
            celula["execution_count"] = None
            celula["outputs"] = []


def executar(nb) -> dict | None:
    """Executa célula a célula. Devolve os dados da falha (None se passou)."""
    cliente = NotebookClient(nb, timeout=600, kernel_name="python3")
    try:
        cliente.execute()
        return None
    except CellExecutionError:
        for indice, celula in enumerate(nb.cells):
            for saida in celula.get("outputs", []):
                if saida.get("output_type") == "error":
                    return {"celula": indice, "tipo": saida.get("ename"), "mensagem": saida.get("evalue")}
        return {"celula": None, "tipo": None, "mensagem": "falhou, mas nenhuma célula com erro foi encontrada"}


def montar_relatorio(nb, mapeadas: list[dict], falha: dict | None, duracao: float) -> dict:
    executadas = {m["indice"] for m in mapeadas if nb.cells[m["indice"]]["execution_count"] is not None}
    por_secao: dict[str, int] = {}
    for mapeada in mapeadas:
        if mapeada["indice"] not in executadas:
            continue
        por_secao[mapeada["secao"]] = por_secao.get(mapeada["secao"], 0) + mapeada["verificacoes"]
    por_secao = {nome: quantidade for nome, quantidade in por_secao.items() if quantidade > 0}
    return {
        "data_hora": datetime.now().astimezone().isoformat(timespec="seconds"),
        "resultado": "falhou" if falha else "passou",
        "duracao_segundos": round(duracao, 1),
        "secoes": [{"nome": nome, "verificacoes": quantidade} for nome, quantidade in por_secao.items()],
        "total_secoes": len(por_secao),
        "total_verificacoes": sum(por_secao.values()),
        "falha": falha,
    }


def imprimir(relatorio: dict, caminho_relatorio: Path) -> None:
    print(f"Testes do motor de dosimetria: {relatorio['resultado'].upper()}")
    print(
        f"  {relatorio['total_verificacoes']} verificações em {relatorio['total_secoes']} seções, "
        f"{relatorio['duracao_segundos']}s"
    )
    for secao in relatorio["secoes"]:
        print(f"    {secao['nome']}: {secao['verificacoes']}")
    if relatorio["falha"]:
        falha = relatorio["falha"]
        print(f"  Falhou na célula {falha['celula']}: {falha['tipo']}: {falha['mensagem']}")
    print(f"  Relatório: {caminho_relatorio}")


def main() -> None:
    analisador = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analisador.add_argument("--relatorio", type=Path, default=Path("/tmp/relatorio_testes.json"))
    analisador.add_argument("--notebook-executado", type=Path, default=Path("/tmp/dosimetria_tests_executado.ipynb"))
    argumentos = analisador.parse_args()

    nb = nbformat.read(NOTEBOOK, as_version=4)
    mapeadas = mapear_secoes(nb.cells)
    limpar_execucao_anterior(nb)

    inicio = time.monotonic()
    falha = executar(nb)
    duracao = time.monotonic() - inicio

    argumentos.notebook_executado.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, argumentos.notebook_executado)

    relatorio = montar_relatorio(nb, mapeadas, falha, duracao)
    argumentos.relatorio.parent.mkdir(parents=True, exist_ok=True)
    argumentos.relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    imprimir(relatorio, argumentos.relatorio)
    sys.exit(1 if falha else 0)


if __name__ == "__main__":
    main()
