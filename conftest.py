import os

# Variáveis mínimas para que settings.py não falhe durante os testes.
# Valores reais ficam no .env — nunca commitar credenciais aqui.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("TELEGRAM_CHANNEL_ID", "@test_channel")
