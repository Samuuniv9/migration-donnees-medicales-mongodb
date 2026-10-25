# Image du script de migration : Python + dépendances + code.
FROM python:3.12-slim

WORKDIR /app

# Les dépendances d'abord : Docker garde cette couche en cache tant que
# requirements.txt ne change pas (reconstruction plus rapide).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY tests/ tests/

# Par défaut, le conteneur lance la migration.
CMD ["python", "-m", "src.migrate"]
