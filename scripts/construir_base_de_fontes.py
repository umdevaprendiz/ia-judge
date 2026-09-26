"""Gera dados/fontes/dispositivos.json a partir dos PDFs de legislação em materiais/legislacao/.

    python scripts/construir_base_de_fontes.py

É a "ingestão" do agente: roda de novo só quando entra um PDF novo ou uma edição mais
recente (fontes/catalogo.py diz quais PDFs entram). O resultado vai para o git, e o site
não precisa dos PDFs para funcionar. PDFs que faltarem são pulados com aviso.
"""

import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pypdf import PdfReader  # noqa: E402

from sources.catalogo import FONTES  # noqa: E402
from sources.extracao import escolher_versoes, extrair_documento  # noqa: E402
from sources.texto import limpar_paginas  # noqa: E402

PASTA_PDFS = RAIZ / "materiais" / "legislacao"
SAIDA = RAIZ / "data" / "sources" / "dispositivos.json"


def main() -> None:
    artigos_por_fonte = {}
    usadas = []
    for fonte in FONTES:
        arquivo = PASTA_PDFS / fonte.arquivo
        if not arquivo.is_file():
            print(f"AVISO: {fonte.arquivo} não encontrado; pulando")
            continue
        paginas = [pagina.extract_text() or "" for pagina in PdfReader(arquivo).pages]
        artigos_por_fonte[fonte.id] = extrair_documento(fonte, limpar_paginas(paginas))
        usadas.append(fonte)
        print(f"{fonte.arquivo}: {len(artigos_por_fonte[fonte.id])} artigos")

    datas = {fonte.id: fonte.atualizado_ate for fonte in usadas}
    artigos = escolher_versoes(artigos_por_fonte, datas)

    contagem = Counter((a.lei, a.nome_lei, a.fonte) for a in artigos)
    print("\nNa base:")
    for (lei, nome, fonte_id), total in sorted(contagem.items(), key=lambda item: -item[1]):
        print(f"  {lei:8} {total:5}  {nome[:60]}  [{fonte_id}]")

    fontes_na_base = {a.fonte for a in artigos}
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    cabecalho = {
        "descricao": "Artigos de lei extraídos dos PDFs oficiais (Senado e Câmara); um registro por artigo.",
        "fontes": [
            {"id": f.id, "titulo": f.titulo, "arquivo": f.arquivo, "atualizado_ate": f.atualizado_ate}
            for f in usadas
            if f.id in fontes_na_base
        ],
    }
    linhas = [json.dumps(asdict(artigo), ensure_ascii=False) for artigo in artigos]
    corpo = json.dumps(cabecalho, ensure_ascii=False, indent=1)[:-2]
    SAIDA.write_text(corpo + ',\n "dispositivos": [\n' + ",\n".join(linhas) + "\n ]\n}\n", encoding="utf-8")
    print(f"\n{len(artigos)} artigos gravados em {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
