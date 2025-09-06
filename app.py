\
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, flash
from flask import g
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base
import pandas as pd

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "potiguar.db")
SEED_CSV = os.path.join(BASE_DIR, "data", "seed_funcionarios.csv")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "potiguar-secret")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Funcionario(Base):
    __tablename__ = "funcionarios"
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False, default="")
    funcao = Column(String, nullable=False, default="")
    local_trabalho = Column(String, nullable=False, default="")
    tipo_contrato = Column(String, nullable=False, default="INTERMITENTE")
    status_exame = Column(String, nullable=False, default="PENDENTE")  # OK | PENDENTE
    status_contrato = Column(String, nullable=False, default="PENDENTE")  # OK | PENDENTE
    valor_diaria = Column(Float, nullable=False, default=0.0)

def get_db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db

@app.teardown_appcontext
def teardown_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def bootstrap_from_seed(db):
    if not os.path.exists(SEED_CSV):
        return
    if db.query(Funcionario).count() > 0:
        return
    df = pd.read_csv(SEED_CSV)
    for _, row in df.iterrows():
        f = Funcionario(
            nome=str(row.get("nome","")).strip(),
            funcao=str(row.get("funcao","")).strip(),
            local_trabalho=str(row.get("local_trabalho","")).strip(),
            tipo_contrato=str(row.get("tipo_contrato","") or "INTERMITENTE").strip().upper(),
            status_exame=("OK" if str(row.get("status_exame","")).strip().upper()=="OK" else "PENDENTE"),
            status_contrato=("OK" if str(row.get("status_contrato","")).strip().upper()=="OK" else "PENDENTE"),
            valor_diaria=float(row.get("valor_diaria", 0.0) or 0.0),
        )
        db.add(f)
    db.commit()

@app.route("/")
def index():
    db = get_db()
    q = request.args.get("q","").strip()
    filtro = request.args.get("filtro","todos")
    query = db.query(Funcionario)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Funcionario.nome.ilike(like)) |
            (Funcionario.funcao.ilike(like)) |
            (Funcionario.local_trabalho.ilike(like))
        )
    if filtro == "pendencias":
        query = query.filter((Funcionario.status_exame!="OK") | (Funcionario.status_contrato!="OK"))
    elif filtro == "exame_pendente":
        query = query.filter(Funcionario.status_exame!="OK")
    elif filtro == "contrato_pendente":
        query = query.filter(Funcionario.status_contrato!="OK")
    funcionarios = query.order_by(Funcionario.nome.asc()).all()
    return render_template("index.html", funcionarios=funcionarios, q=q, filtro=filtro)

@app.route("/func/<int:fid>/toggle_exame", methods=["POST"])
def toggle_exame(fid):
    db = get_db()
    f = db.query(Funcionario).get(fid)
    if not f: return ("", 404)
    f.status_exame = "OK" if f.status_exame != "OK" else "PENDENTE"
    db.commit()
    return render_template("_card.html", f=f)

@app.route("/func/<int:fid>/toggle_contrato", methods=["POST"])
def toggle_contrato(fid):
    db = get_db()
    f = db.query(Funcionario).get(fid)
    if not f: return ("", 404)
    f.status_contrato = "OK" if f.status_contrato != "OK" else "PENDENTE"
    db.commit()
    return render_template("_card.html", f=f)

@app.route("/func/<int:fid>/ajusta_diaria", methods=["POST"])
def ajusta_diaria(fid):
    db = get_db()
    f = db.query(Funcionario).get(fid)
    if not f: return ("", 404)
    delta = float(request.form.get("delta", 0))
    novo = max(0.0, round((f.valor_diaria or 0.0) + delta, 2))
    f.valor_diaria = novo
    db.commit()
    return render_template("_card.html", f=f)

@app.route("/func/novo", methods=["POST"])
def novo():
    db = get_db()
    f = Funcionario(
        nome=request.form.get("nome","").strip(),
        funcao=request.form.get("funcao","").strip(),
        local_trabalho=request.form.get("local_trabalho","").strip(),
        tipo_contrato=request.form.get("tipo_contrato","INTERMITENTE").strip().upper(),
        status_exame="PENDENTE",
        status_contrato="PENDENTE",
        valor_diaria=float(request.form.get("valor_diaria","0") or 0.0)
    )
    db.add(f)
    db.commit()
    flash("Colaborador adicionado.", "ok")
    return redirect(url_for("index"))

@app.route("/admin/importar_ods", methods=["GET","POST"])
def importar_ods():
    if request.method == "GET":
        return render_template("importar_ods.html")
    file = request.files.get("arquivo")
    if not file or not file.filename.lower().endswith(".ods"):
        flash("Envie um arquivo .ods válido.", "erro")
        return redirect(url_for("importar_ods"))
    try:
        df = pd.read_excel(file, engine="odf", sheet_name=0)
        # mapear colunas esperadas
        mapping = {
            'NOME ': 'nome', 'NOME': 'nome',
            'FUNÇÃO': 'funcao',
            'VALOR DA DIARIA': 'valor_diaria',
            'LOCAL DE TRABALHO': 'local_trabalho',
            'CONTRATO': 'tipo_contrato',
            'FEZ EXAME ?': 'status_exame',
            'SOLICITAÇÃO DO CONTRATRO': 'status_contrato',
        }
        norm = {}
        for k, v in mapping.items():
            if k in df.columns:
                norm[v] = df[k]
        new = pd.DataFrame(norm).fillna("")
        db = get_db()
        # limpar tudo e importar
        db.query(Funcionario).delete()
        db.commit()
        for _, r in new.iterrows():
            f = Funcionario(
                nome=str(r.get("nome","")).strip(),
                funcao=str(r.get("funcao","")).strip(),
                local_trabalho=str(r.get("local_trabalho","")).strip(),
                tipo_contrato=str(r.get("tipo_contrato","") or "INTERMITENTE").strip().upper(),
                status_exame=("OK" if str(r.get("status_exame","")).strip().upper()=="OK" else "PENDENTE"),
                status_contrato=("OK" if str(r.get("status_contrato","")).strip().upper()=="OK" else "PENDENTE"),
                valor_diaria=float(r.get("valor_diaria", 0.0) or 0.0),
            )
            db.add(f)
        db.commit()
        flash("Importação concluída.", "ok")
    except Exception as e:
        flash(f"Erro ao importar: {e}", "erro")
    return redirect(url_for("index"))

@app.context_processor
def inject_brand():
    return {"brand_logo": "/static/logo.png" if os.path.exists(os.path.join(BASE_DIR, "static", "logo.png")) else None}

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_from_seed(db)
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

# -- Garantir init do DB também quando importado pelo gunicorn
init_db()
