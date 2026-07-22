import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt

# Configurações de Segurança JWT
SECRET_KEY = "SUA_CHAVE_SECRETA_SUPER_SEGURA_ULTRATELECOM"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="UltraTelecom IA API")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretórios e Banco de Dados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DB_PATH = os.path.join(BASE_DIR, "database.db")
os.makedirs(DOCS_DIR, exist_ok=True)

# ---------------------------------------------------------
# BANCO DE DADOS (SQLite)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Tabela de Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    # Tabela de Conversas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            messages TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# MODELOS PYDANTIC
# ---------------------------------------------------------
class UserRegister(BaseModel):
    email: str
    password: str
    admin_secret: Optional[str] = None  # Se enviar a chave secreta, vira admin!

class ChatMessage(BaseModel):
    chat_id: Optional[int] = None
    message: str

# ---------------------------------------------------------
# FUNÇÕES DE AUTENTICAÇÃO
# ---------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: sqlite3.Connection = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de autenticação inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if user is None:
        raise credentials_exception
    return dict(user)

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: Somente administradores autorizados."
        )
    return current_user

# ---------------------------------------------------------
# ROTAS DE USUÁRIO E LOGIN
# ---------------------------------------------------------
@app.post("/register")
def register(user_data: UserRegister, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    # Define se é Admin (Senha mestre do sistema para criar admins)
    role = "user"
    if user_data.admin_secret == "ULTRA_ADMIN_2026":
        role = "admin"

    hashed_pwd = hash_password(user_data.password)
    cursor.execute("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)", 
                   (user_data.email, hashed_pwd, role))
    db.commit()
    return {"message": "Usuário criado com sucesso!", "role": role}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (form_data.username,))
    user = cursor.fetchone()
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="E-mail ou senha incorretos.")

    access_token = create_access_token(data={"sub": user["email"], "role": user["role"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
        "email": user["email"]
    }

@app.get("/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    return {"email": current_user["email"], "role": current_user["role"]}

# ---------------------------------------------------------
# ROTAS DE CHAT E HISTÓRICO
# ---------------------------------------------------------
@app.post("/chat")
def chat(data: ChatMessage, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    user_msg = data.message
    
    # Lógica simples de resposta da IA
    bot_reply = f"Processando sua dúvida: '{user_msg}'. Em breve integraremos com seus documentos!"
    
    chat_id = data.chat_id
    messages = []

    if chat_id:
        cursor.execute("SELECT messages FROM chats WHERE id = ? AND user_id = ?", (chat_id, current_user["id"]))
        row = cursor.fetchone()
        if row:
            messages = json.loads(row["messages"])

    messages.append({"sender": "user", "text": user_msg})
    messages.append({"sender": "bot", "text": bot_reply})

    if chat_id:
        cursor.execute("UPDATE chats SET messages = ? WHERE id = ?", (json.dumps(messages), chat_id))
    else:
        title = user_msg[:30] + "..." if len(user_msg) > 30 else user_msg
        cursor.execute("INSERT INTO chats (user_id, title, messages) VALUES (?, ?, ?)",
                       (current_user["id"], title, json.dumps(messages)))
        chat_id = cursor.lastrowid

    db.commit()
    return {"chat_id": chat_id, "reply": bot_reply, "history": messages}

@app.get("/chats")
def list_chats(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, created_at FROM chats WHERE user_id = ? ORDER BY id DESC", (current_user["id"],))
    return cursor.fetchall()

@app.get("/chats/{chat_id}")
def get_chat(chat_id: int, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, current_user["id"]))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return {"id": row["id"], "title": row["title"], "messages": json.loads(row["messages"])}

# ---------------------------------------------------------
# ROTA PROTEGIDA: PAINEL ADMIN
# ---------------------------------------------------------
@app.get("/admin/docs")
def list_admin_docs(admin_user: dict = Depends(require_admin)):
    # Somente acessível se role == 'admin'
    files = os.listdir(DOCS_DIR)
    return {"status": "Acesso concedido", "admin": admin_user["email"], "files": files}
