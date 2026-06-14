FROM python:3.12-slim

WORKDIR /app

# Instala uv diretamente da imagem oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copia arquivos de dependências primeiro (aproveita cache de layer)
COPY pyproject.toml uv.lock ./

# Instala dependências Python (sem grupo dev)
RUN uv sync --frozen --no-dev

# Instala Chromium + todas as dependências de sistema necessárias
RUN uv run playwright install --with-deps chromium

# Copia o código-fonte
COPY src/ ./src/
COPY main.py conftest.py ./

# Garante que os diretórios de runtime existem
RUN mkdir -p data logs

CMD ["uv", "run", "python", "main.py"]
