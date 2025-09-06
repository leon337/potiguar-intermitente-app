# Potiguar Intermitente - Painel HR

Aplicação Flask com SQLite para gerenciar colaboradores intermitentes por **cards** e **botões** (sem formulários complexos).

## Rodar local
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
# abrir http://127.0.0.1:5000
```

## Deploy rápido (Replit)
1. Crie um repl de **Python** e faça upload destes arquivos.
2. Em *Packages*, instale as libs do `requirements.txt` ou rode `pip install -r requirements.txt`.
3. Em *Run*, configure: `python app.py`.

## Deploy (Railway/Render)
- Railway: Novo Project → Deploy from Repo → *Add Variables* (nenhuma obrigatória). Use `Procfile` + `gunicorn`.
- Render: Web Service → Build `pip install -r requirements.txt` → Start `gunicorn app:app`.

## Importar planilha ODS
Na interface, use **Admin → Importar ODS** e envie um arquivo `.ods` no mesmo formato da planilha.
