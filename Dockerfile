# Imagem do motor de dosimetria com as ferramentas para rodar os testes em notebook.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

RUN useradd --create-home --uid 1000 dosimetria
COPY --chown=dosimetria:dosimetria . .
USER dosimetria

# Executa o notebook de testes; qualquer assert que falhar faz o comando sair com erro.
# A cópia executada vai para /tmp para não alterar o notebook do projeto.
CMD ["jupyter", "nbconvert", "--to", "notebook", "--execute", "--output-dir", "/tmp", "tests/dosimetria_tests.ipynb"]
