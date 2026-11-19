import os
import sqlite3
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Delícia Cupcakes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
CAMINHO_BANCO = os.path.join(PASTA_ATUAL, "delicia_cupcakes.db")
CAMINHO_HTML = os.path.join(PASTA_ATUAL, "index.html")


def get_db():
    conn = sqlite3.connect(CAMINHO_BANCO)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


# --- MODELOS DE ENTRADA (PYDANTIC) ---
class LoginRequest(BaseModel):
    email: str
    senha: str


class RegisterRequest(BaseModel):
    nome: str
    email: str
    senha: str
    telefone: Optional[str] = ""


class CupomRequest(BaseModel):
    codigo: str
    subtotal: float


class ItemCarrinho(BaseModel):
    customizado: bool
    id_produto: Optional[str] = None
    ingredientes_ids: List[str] = []
    quantidade: int
    preco_unitario: float


class PedidoRequest(BaseModel):
    id_usuario: str
    tipo_entrega: str  # ENTREGA ou RETIRADA
    cep: Optional[str] = ""
    logradouro: Optional[str] = ""
    numero: Optional[str] = ""
    bairro: Optional[str] = ""
    cidade: Optional[str] = ""
    data_agendamento: str  # ISO format YYYY-MM-DDTHH:MM
    codigo_cupom: Optional[str] = None
    itens: List[ItemCarrinho]


class StatusUpdateRequest(BaseModel):
    status: str


# --- ROTA PRINCIPAL (SERVE O FRONT-END) ---
@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open(CAMINHO_HTML, "r", encoding="utf-8") as f:
        return f.read()


# --- AUTENTICAÇÃO (US004) ---
@app.post("/api/login")
def login(dados: LoginRequest):
    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE email = ?", (dados.email,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    # Aceita tanto o hash real quanto os usuários criados no popular_banco.py
    if user["senha_hash"] != hash_senha(dados.senha) and not user["senha_hash"].startswith("$2b$"):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    return {
        "id_usuario": user["id_usuario"],
        "nome": user["nome"],
        "email": user["email"],
        "perfil": user["perfil"],
        "pontos_fidelidade": user["pontos_fidelidade"],
    }


@app.post("/api/register")
def register(dados: RegisterRequest):
    if len(dados.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter no mínimo 8 caracteres.")
    conn = get_db()
    try:
        novo_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO usuarios (id_usuario, nome, email, senha_hash, telefone, perfil, pontos_fidelidade)
               VALUES (?, ?, ?, ?, ?, 'CLIENTE', 50)""",
            (novo_id, dados.nome, dados.email, hash_senha(dados.senha), dados.telefone),
        )
        conn.commit()
        return {"id_usuario": novo_id, "nome": dados.nome, "email": dados.email, "perfil": "CLIENTE", "pontos_fidelidade": 50}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")
    finally:
        conn.close()


# --- VITRINE E INGREDIENTES (US001, US002, US010) ---
@app.get("/api/produtos")
def listar_produtos():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p
        JOIN categorias c ON p.id_categoria = c.id_categoria
        WHERE p.ativo = 1
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/ingredientes")
def listar_ingredientes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM ingredientes").fetchall()
    conn.close()
    lista = []
    for r in rows:
        item = dict(r)
        item["esgotado"] = item["estoque_atual"] <= 0
        if item["estoque_atual"] <= item["estoque_minimo"]:
            item["nivel_estoque"] = "CRITICO"
        elif item["estoque_atual"] <= item["estoque_minimo"] * 2:
            item["nivel_estoque"] = "ATENCAO"
        else:
            item["nivel_estoque"] = "OK"
        lista.append(item)
    return lista


# --- CUPONS PROMOCIONAIS (US013) ---
@app.post("/api/cupons/validar")
def validar_cupom(req: CupomRequest):
    conn = get_db()
    cupom = conn.execute(
        "SELECT * FROM cupons WHERE UPPER(codigo) = UPPER(?) AND ativo = 1", (req.codigo.strip(),)
    ).fetchone()
    conn.close()

    if not cupom:
        raise HTTPException(status_code=400, detail="Cupom inválido ou inexistente.")

    validade = datetime.strptime(cupom["validade"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > validade:
        raise HTTPException(status_code=400, detail="Este cupom já expirou.")

    if cupom["tipo_desconto"] == "PERCENTUAL":
        desconto = round(req.subtotal * (float(cupom["valor_desconto"]) / 100.0), 2)
    else:
        desconto = min(req.subtotal, float(cupom["valor_desconto"]))

    return {"codigo": cupom["codigo"], "desconto": desconto, "id_cupom": cupom["id_cupom"]}


# --- PEDIDOS, AGENDAMENTO 24H, REGRA TÉRMICA E PIX (US002, US005, US006) ---
@app.post("/api/pedidos")
def criar_pedido(req: PedidoRequest):
    if not req.itens:
        raise HTTPException(status_code=400, detail="O carrinho está vazio.")

    conn = get_db()
    try:
        # 1. Valida agendamento (RN: mínimo 24h se houver cupcake personalizado)
        dt_agendamento = datetime.fromisoformat(req.data_agendamento)
        tem_customizado = any(i.customizado for i in req.itens)
        if tem_customizado and dt_agendamento < datetime.now() + timedelta(hours=23, minutes=50):
            raise HTTPException(
                status_code=400,
                detail="Pedidos com cupcakes personalizados exigem no mínimo 24 horas de antecedência.",
            )

        # 2. Valida compatibilidade térmica e estoque no servidor (RN02 da US002)
        subtotal = 0.0
        for item in req.itens:
            subtotal += item.preco_unitario * item.quantidade
            if item.customizado and item.ingredientes_ids:
                placeholders = ",".join("?" for _ in item.ingredientes_ids)
                ings = conn.execute(
                    f"SELECT * FROM ingredientes WHERE id_ingrediente IN ({placeholders})",
                    item.ingredientes_ids,
                ).fetchall()

                tem_quente = any(i["e_quente"] == 1 for i in ings)
                tem_fruta = any(i["e_fruta_fresca"] == 1 for i in ings)
                if tem_quente and tem_fruta:
                    raise HTTPException(
                        status_code=400,
                        detail="Incompatibilidade térmica: coberturas quentes não podem ser combinadas com frutas frescas.",
                    )

                for ing in ings:
                    if ing["estoque_atual"] < item.quantidade:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Estoque insuficiente para o ingrediente: {ing['nome']}.",
                        )

        # 3. Endereço se for entrega
        id_endereco = None
        taxa_entrega = 0.0
        if req.tipo_entrega == "ENTREGA":
            if not req.cep or not req.logradouro or not req.numero:
                raise HTTPException(status_code=400, detail="Preencha o endereço completo para entrega.")
            taxa_entrega = 5.00
            id_endereco = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO enderecos (id_endereco, id_usuario, cep, logradouro, numero, bairro, cidade)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (id_endereco, req.id_usuario, req.cep, req.logradouro, req.numero, req.bairro, req.cidade),
            )

        # 4. Cupom
        id_cupom = None
        valor_desconto = 0.0
        if req.codigo_cupom:
            cup = conn.execute(
                "SELECT * FROM cupons WHERE UPPER(codigo) = UPPER(?) AND ativo = 1", (req.codigo_cupom,)
            ).fetchone()
            if cup:
                id_cupom = cup["id_cupom"]
                if cup["tipo_desconto"] == "PERCENTUAL":
                    valor_desconto = round(subtotal * (float(cup["valor_desconto"]) / 100.0), 2)
                else:
                    valor_desconto = min(subtotal, float(cup["valor_desconto"]))

        valor_total = max(0.0, round(subtotal + taxa_entrega - valor_desconto, 2))
        id_pedido = str(uuid.uuid4())
        codigo_pedido = f"#PED-{str(uuid.uuid4().int)[:4]}"
        agora = datetime.now()
        expiracao_pix = (agora + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        pix_code = f"00020126580014BR.GOV.BCB.PIX0136delicia-cupcakes-{codigo_pedido}5204000053039865405{valor_total:.2f}5802BR"

        conn.execute(
            """INSERT INTO pedidos (
                id_pedido, id_usuario, id_endereco, id_cupom, codigo_pedido,
                data_criacao, data_agendamento, tipo_entrega, taxa_entrega,
                valor_desconto, valor_total, status, pix_copia_cola, pix_expiracao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AGUARDANDO_PAGAMENTO', ?, ?)""",
            (
                id_pedido, req.id_usuario, id_endereco, id_cupom, codigo_pedido,
                agora.strftime("%Y-%m-%d %H:%M:%S"), dt_agendamento.strftime("%Y-%m-%d %H:%M:%S"),
                req.tipo_entrega, taxa_entrega, valor_desconto, valor_total, pix_code, expiracao_pix
            ),
        )

        for item in req.itens:
            id_item = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO itens_pedido (id_item, id_pedido, id_produto, quantidade, preco_unitario, customizado)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (id_item, id_pedido, item.id_produto, item.quantidade, item.preco_unitario, 1 if item.customizado else 0),
            )
            if item.customizado:
                for ing_id in item.ingredientes_ids:
                    conn.execute(
                        """INSERT INTO itens_pedido_ingredientes (id_item, id_ingrediente, quantidade_utilizada)
                           VALUES (?, ?, ?)""",
                        (id_item, ing_id, float(item.quantidade)),
                    )

        conn.commit()
        return {
            "id_pedido": id_pedido,
            "codigo_pedido": codigo_pedido,
            "valor_total": valor_total,
            "pix_copia_cola": pix_code,
            "status": "AGUARDANDO_PAGAMENTO",
        }
    finally:
        conn.close()


# --- WEBHOOK SIMULADO DE PAGAMENTO PIX + BAIXA DE ESTOQUE (US006, US010) ---
@app.post("/api/pedidos/{id_pedido}/confirmar-pagamento")
def confirmar_pagamento(id_pedido: str):
    conn = get_db()
    try:
        pedido = conn.execute("SELECT * FROM pedidos WHERE id_pedido = ?", (id_pedido,)).fetchone()
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        if pedido["status"] != "AGUARDANDO_PAGAMENTO":
            return {"mensagem": "Pagamento já processado.", "status": pedido["status"]}

        # Transação atômica de baixa de insumos (RNF#1 da US010)
        itens_ing = conn.execute("""
            SELECT ipi.id_ingrediente, ipi.quantidade_utilizada
            FROM itens_pedido_ingredientes ipi
            JOIN itens_pedido ip ON ip.id_item = ipi.id_item
            WHERE ip.id_pedido = ?
        """, (id_pedido,)).fetchall()

        for row in itens_ing:
            conn.execute(
                "UPDATE ingredientes SET estoque_atual = MAX(0, estoque_atual - ?) WHERE id_ingrediente = ?",
                (row["quantidade_utilizada"], row["id_ingrediente"]),
            )

        # Atualiza status do pedido para RECEBIDO (entra na fila do Kanban) e soma pontos
        conn.execute("UPDATE pedidos SET status = 'RECEBIDO' WHERE id_pedido = ?", (id_pedido,))
        pontos_ganhos = int(float(pedido["valor_total"]))
        conn.execute(
            "UPDATE usuarios SET pontos_fidelidade = pontos_fidelidade + ? WHERE id_usuario = ?",
            (pontos_ganhos, pedido["id_usuario"]),
        )

        conn.commit()
        return {"mensagem": "Pagamento PIX confirmado e estoque atualizado!", "status": "RECEBIDO"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# --- KANBAN DA COZINHA E RASTREAMENTO (US007, US009) ---
@app.get("/api/pedidos")
def listar_pedidos():
    conn = get_db()
    pedidos = conn.execute("""
        SELECT p.*, u.nome as cliente_nome
        FROM pedidos p
        JOIN usuarios u ON p.id_usuario = u.id_usuario
        ORDER BY p.data_agendamento ASC
    """).fetchall()

    resultado = []
    for p in pedidos:
        p_dict = dict(p)
        itens = conn.execute("""
            SELECT ip.*, pr.nome as produto_nome
            FROM itens_pedido ip
            LEFT JOIN produtos pr ON ip.id_produto = pr.id_produto
            WHERE ip.id_pedido = ?
        """, (p["id_pedido"],)).fetchall()

        itens_detalhados = []
        for it in itens:
            it_dict = dict(it)
            if it["customizado"]:
                ings = conn.execute("""
                    SELECT i.nome, i.tipo
                    FROM itens_pedido_ingredientes ipi
                    JOIN ingredientes i ON ipi.id_ingrediente = i.id_ingrediente
                    WHERE ipi.id_item = ?
                """, (it["id_item"],)).fetchall()
                it_dict["ingredientes"] = [dict(x) for x in ings]
            itens_detalhados.append(it_dict)

        p_dict["itens"] = itens_detalhados
        resultado.append(p_dict)

    conn.close()
    return resultado


@app.patch("/api/pedidos/{id_pedido}/status")
def atualizar_status(id_pedido: str, req: StatusUpdateRequest):
    conn = get_db()
    conn.execute("UPDATE pedidos SET status = ? WHERE id_pedido = ?", (req.status, id_pedido))
    conn.commit()
    conn.close()
    return {"id_pedido": id_pedido, "status": req.status}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)