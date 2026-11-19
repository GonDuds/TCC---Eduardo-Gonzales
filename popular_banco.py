import os
import sqlite3
import uuid
from datetime import datetime, timedelta

# Aponta sempre para o delicia_cupcakes.db na mesma pasta TCC
pasta_atual = os.path.dirname(os.path.abspath(__file__))
caminho_banco = os.path.join(pasta_atual, "delicia_cupcakes.db")

conn = sqlite3.connect(caminho_banco)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

# Limpa dados anteriores caso você rode o script mais de uma vez
tabelas_limpar = [
    "itens_pedido_ingredientes", "itens_pedido", "pedidos",
    "cupons", "ingredientes", "produtos", "categorias",
    "enderecos", "usuarios"
]
for tab in tabelas_limpar:
    cursor.execute(f"DELETE FROM {tab};")

# 1. USUÁRIOS (Cliente Eduardo + Confeiteiro Admin)
id_cliente = str(uuid.uuid4())
id_admin = str(uuid.uuid4())

cursor.executemany("""
    INSERT INTO usuarios (id_usuario, nome, email, senha_hash, telefone, perfil, pontos_fidelidade)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", [
    (id_cliente, "Eduardo Gonzales", "eduardo@email.com", "$2b$12$hashSimuladoCliente123456789", "(41) 99999-1111", "CLIENTE", 150),
    (id_admin, "Chef Confeiteiro", "cozinha@deliciacupcakes.com", "$2b$12$hashSimuladoAdmin987654321", "(41) 98888-2222", "CONFEITEIRO", 0)
])

# 2. ENDEREÇO DO CLIENTE
id_endereco = str(uuid.uuid4())
cursor.execute("""
    INSERT INTO enderecos (id_endereco, id_usuario, cep, logradouro, numero, complemento, bairro, cidade)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (id_endereco, id_cliente, "83005-000", "Rua XV de Novembro", "1240", "Apto 302", "Centro", "São José dos Pinhais"))

# 3. CATEGORIAS (Mesmas dos filtros dos seus Wireframes)
categorias = ["Tradicional", "Vegano", "Sem Lactose", "Mais Vendidos"]
for cat in categorias:
    cursor.execute("INSERT INTO categorias (nome) VALUES (?);", (cat,))

cursor.execute("SELECT id_categoria, nome FROM categorias;")
cat_map = {nome: cid for cid, nome in cursor.fetchall()}

# 4. PRODUTOS (Mesmos cupcakes e preços dos seus Wireframes)
id_prod_red_velvet = str(uuid.uuid4())
id_prod_chocolate = str(uuid.uuid4())
id_prod_vegano = str(uuid.uuid4())
id_prod_sem_lactose = str(uuid.uuid4())
id_prod_morango = str(uuid.uuid4())

cursor.executemany("""
    INSERT INTO produtos (id_produto, id_categoria, nome, descricao, preco_base, imagem_url, ativo)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", [
    (id_prod_red_velvet, cat_map["Tradicional"], "Cupcake Red Velvet", "Massa aveludada de cacau com cobertura cremosa de cream cheese.", 12.50, "/img/red-velvet.png", 1),
    (id_prod_chocolate, cat_map["Tradicional"], "Cupcake de Chocolate", "Massa intensa de chocolate 50% com brigadeiro gourmet.", 10.00, "/img/chocolate.png", 1),
    (id_prod_vegano, cat_map["Vegano"], "Cupcake Vegano", "Massa 100% vegetal de cacau com ganache de leite de coco.", 13.00, "/img/vegano.png", 1),
    (id_prod_sem_lactose, cat_map["Sem Lactose"], "Cupcake Sem Lactose", "Massa fofinha de baunilha com cobertura zero lactose.", 13.00, "/img/sem-lactose.png", 1),
    (id_prod_morango, cat_map["Mais Vendidos"], "Cupcake de Morango", "Massa de baunilha com geleia artesanal e chantilly.", 11.50, "/img/morango.png", 1)
])

# 5. INGREDIENTES (Monte seu Cupcake + Controle de Estoque + Regra Térmica)
ing_massa_rv = str(uuid.uuid4())
ing_massa_choc = str(uuid.uuid4())
ing_massa_baun = str(uuid.uuid4())
ing_rech_nutella = str(uuid.uuid4())
ing_rech_morango = str(uuid.uuid4())
ing_cob_cc = str(uuid.uuid4())
ing_cob_quente = str(uuid.uuid4())
ing_conf_gran = str(uuid.uuid4())

cursor.executemany("""
    INSERT INTO ingredientes (id_ingrediente, nome, tipo, preco_adicional, estoque_atual, estoque_minimo, unidade_medida, e_quente, e_fruta_fresca)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", [
    (ing_massa_rv, "Massa Red Velvet", "MASSA", 4.00, 45.0, 10.0, "UN", 0, 0),
    (ing_massa_choc, "Massa Chocolate", "MASSA", 3.00, 60.0, 15.0, "UN", 0, 0),
    (ing_massa_baun, "Massa Baunilha", "MASSA", 2.50, 8.0, 10.0, "UN", 0, 0),      # Nível Crítico (Vermelho)
    (ing_rech_nutella, "Recheio Nutella", "RECHEIO", 4.50, 30.0, 10.0, "UN", 0, 0),
    (ing_rech_morango, "Morango Fresco Picado", "RECHEIO", 3.50, 18.0, 10.0, "UN", 0, 1), # Fruta fresca
    (ing_cob_cc, "Cobertura Cream Cheese", "COBERTURA", 4.00, 25.0, 10.0, "UN", 0, 0),
    (ing_cob_quente, "Calda Belga Quente", "COBERTURA", 5.00, 20.0, 10.0, "UN", 1, 0),   # Cobertura quente
    (ing_conf_gran, "Confeito Granulado", "CONFEITO", 2.00, 0.0, 10.0, "UN", 0, 0)        # Esgotado!
])

# 6. CUPOM PROMOCIONAL
id_cupom = str(uuid.uuid4())
validade_cupom = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
cursor.execute("""
    INSERT INTO cupons (id_cupom, id_categoria, codigo, tipo_desconto, valor_desconto, validade, ativo)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (id_cupom, None, "CUPCAKE10", "PERCENTUAL", 10.00, validade_cupom, 1))

# 7. PEDIDO EXEMPLO (#24 do seu Wireframe do Kanban!)
id_pedido = str(uuid.uuid4())
agora = datetime.now()
agendamento = (agora + timedelta(hours=26)).strftime("%Y-%m-%d %H:%M:%S")
expiracao_pix = (agora + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

cursor.execute("""
    INSERT INTO pedidos (
        id_pedido, id_usuario, id_endereco, id_cupom, codigo_pedido,
        data_criacao, data_agendamento, tipo_entrega, taxa_entrega,
        valor_desconto, valor_total, status, pix_copia_cola, pix_expiracao
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    id_pedido, id_cliente, id_endereco, None, "#PED-0024",
    agora.strftime("%Y-%m-%d %H:%M:%S"), agendamento, "ENTREGA", 5.00,
    0.00, 39.50, "RECEBIDO",
    "00020126580014BR.GOV.BCB.PIX0136delicia-cupcakes-pix-chave-simulada520400005303986540539.505802BR",
    expiracao_pix
))

# 8. ITENS DO PEDIDO #24 (1 Personalizado + 2 Cupcakes de Chocolate)
id_item_custom = str(uuid.uuid4())
id_item_pronto = str(uuid.uuid4())

cursor.executemany("""
    INSERT INTO itens_pedido (id_item, id_pedido, id_produto, quantidade, preco_unitario, customizado)
    VALUES (?, ?, ?, ?, ?, ?)
""", [
    (id_item_custom, id_pedido, None, 1, 14.50, 1),
    (id_item_pronto, id_pedido, id_prod_chocolate, 2, 10.00, 0)
])

# 9. INGREDIENTES DO CUPCAKE PERSONALIZADO DO PEDIDO #24
cursor.executemany("""
    INSERT INTO itens_pedido_ingredientes (id_item, id_ingrediente, quantidade_utilizada)
    VALUES (?, ?, ?)
""", [
    (id_item_custom, ing_massa_rv, 1.0),
    (id_item_custom, ing_rech_nutella, 1.0),
    (id_item_custom, ing_cob_cc, 1.0),
    (id_item_custom, ing_conf_gran, 1.0)
])

conn.commit()
print("Dados inseridos com sucesso no delicia_cupcakes.db!")
conn.close()