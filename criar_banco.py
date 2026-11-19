import sqlite3

# Conecta (ou cria o arquivo delicia_cupcakes.db na mesma pasta)
conn = sqlite3.connect("delicia_cupcakes.db")
cursor = conn.cursor()

# Ativa a verificação de chaves estrangeiras no SQLite
cursor.execute("PRAGMA foreign_keys = ON;")

sql_script = """
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario TEXT PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    telefone VARCHAR(20),
    perfil VARCHAR(20) NOT NULL DEFAULT 'CLIENTE' CHECK (perfil IN ('CLIENTE', 'CONFEITEIRO', 'ADMIN')),
    pontos_fidelidade INTEGER NOT NULL DEFAULT 0 CHECK (pontos_fidelidade >= 0)
);

CREATE TABLE IF NOT EXISTS enderecos (
    id_endereco TEXT PRIMARY KEY,
    id_usuario TEXT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    cep VARCHAR(9) NOT NULL,
    logradouro VARCHAR(150) NOT NULL,
    numero VARCHAR(20) NOT NULL,
    complemento VARCHAR(100),
    bairro VARCHAR(100) NOT NULL,
    cidade VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    id_produto TEXT PRIMARY KEY,
    id_categoria INTEGER NOT NULL REFERENCES categorias(id_categoria),
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    preco_base DECIMAL(10, 2) NOT NULL CHECK (preco_base >= 0),
    imagem_url VARCHAR(255),
    ativo BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ingredientes (
    id_ingrediente TEXT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('MASSA', 'RECHEIO', 'COBERTURA', 'CONFEITO')),
    preco_adicional DECIMAL(10, 2) NOT NULL DEFAULT 0.00 CHECK (preco_adicional >= 0),
    estoque_atual DECIMAL(10, 2) NOT NULL DEFAULT 0 CHECK (estoque_atual >= 0),
    estoque_minimo DECIMAL(10, 2) NOT NULL DEFAULT 10,
    unidade_medida VARCHAR(10) NOT NULL DEFAULT 'UN',
    e_quente BOOLEAN NOT NULL DEFAULT 0,
    e_fruta_fresca BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cupons (
    id_cupom TEXT PRIMARY KEY,
    id_categoria INTEGER REFERENCES categorias(id_categoria),
    codigo VARCHAR(30) UNIQUE NOT NULL,
    tipo_desconto VARCHAR(15) NOT NULL CHECK (tipo_desconto IN ('PERCENTUAL', 'FIXO')),
    valor_desconto DECIMAL(10, 2) NOT NULL CHECK (valor_desconto > 0),
    validade TIMESTAMP NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido TEXT PRIMARY KEY,
    id_usuario TEXT NOT NULL REFERENCES usuarios(id_usuario),
    id_endereco TEXT REFERENCES enderecos(id_endereco),
    id_cupom TEXT REFERENCES cupons(id_cupom),
    codigo_pedido VARCHAR(15) UNIQUE NOT NULL,
    data_criacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_agendamento TIMESTAMP NOT NULL,
    tipo_entrega VARCHAR(15) NOT NULL CHECK (tipo_entrega IN ('ENTREGA', 'RETIRADA')),
    taxa_entrega DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    valor_desconto DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    valor_total DECIMAL(10, 2) NOT NULL CHECK (valor_total >= 0),
    status VARCHAR(25) NOT NULL DEFAULT 'AGUARDANDO_PAGAMENTO'
        CHECK (status IN ('AGUARDANDO_PAGAMENTO', 'RECEBIDO', 'EM_PREPARO', 'PRONTO', 'SAIU_ENTREGA', 'ENTREGUE', 'CANCELADO')),
    pix_copia_cola TEXT,
    pix_expiracao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id_item TEXT PRIMARY KEY,
    id_pedido TEXT NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    id_produto TEXT REFERENCES produtos(id_produto),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario DECIMAL(10, 2) NOT NULL CHECK (preco_unitario >= 0),
    customizado BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS itens_pedido_ingredientes (
    id_item TEXT NOT NULL REFERENCES itens_pedido(id_item) ON DELETE CASCADE,
    id_ingrediente TEXT NOT NULL REFERENCES ingredientes(id_ingrediente),
    quantidade_utilizada DECIMAL(10, 2) NOT NULL DEFAULT 1,
    PRIMARY KEY (id_item, id_ingrediente)
);
"""

cursor.executescript(sql_script)
conn.commit()

# Lista as tabelas criadas para você tirar o print de evidência
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tabelas = cursor.fetchall()

print("Banco de dados criado com sucesso! Tabelas geradas:")
for t in tabelas:
    print(f" - {t[0]}")

conn.close()