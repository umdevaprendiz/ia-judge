# Dois alvos:
#   api (padrão): só o necessário para servir a API; é o que se usa para hospedar.
#   dev: acrescenta o Jupyter para rodar e editar os testes em notebook.
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
RUN useradd --create-home --uid 1000 dosimetria


FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY --chown=dosimetria:dosimetria . .
USER dosimetria
# Executa o notebook de testes; qualquer assert que falhar faz o comando sair com erro.
# A cópia executada vai para /tmp para não alterar o notebook do projeto.
CMD ["jupyter", "nbconvert", "--to", "notebook", "--execute", "--output-dir", "/tmp", "tests/dosimetria_tests.ipynb"]


FROM base AS api
COPY --chown=dosimetria:dosimetria . .
USER dosimetria
EXPOSE 8000
# Aplica as migrações do banco (se DATABASE_URL estiver definida) e sobe a API.
# A porta pode ser trocada pela variável PORT (plataformas de hospedagem costumam defini-la).
CMD ["sh", "-c", "python -m banco.migrar && exec uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000} --no-server-header"]
