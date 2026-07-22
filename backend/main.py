from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI(title="UltraTelecom AI Assistant")

# Permite comunicação com o Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCS_DIR = "../database/docs"
os.makedirs(DOCS_DIR, exist_ok=True)

class QueryRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_endpoint(request: QueryRequest):
    user_query = request.message.lower()
    
    # Lógica base de resposta - RAG simulated
    if "pppoe" in user_query:
        response = "### Configuração PPPoE\n1. Acesse `192.168.1.1`\n2. Vá em **WAN**\n3. Selecione **PPPoE**\n\n| Parâmetro | Valor |\n|---|---|\n| VLAN | 100 |\n| MTU | 1492 |"
    elif "onu" in user_query:
        response = "### Instalação de ONU\nPara provisionar a ONU, verifique a potência óptica no sinal de RX (-15 a -25 dBm) e vincule no sistema."
    else:
        response = "Não encontrei essa informação na base de conhecimento da UltraTelecom."
        
    return {"reply": response}

@app.get("/api/documents")
async def list_documents():
    files = os.listdir(DOCS_DIR)
    return {"documents": files, "count": len(files)}

@app.post("/api/documents/upload")
async def upload_document(category: str = Form(...), file: UploadFile = File(...)):
    file_path = os.path.join(DOCS_DIR, f"[{category.upper()}]_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"message": f"Documento '{file.filename}' adicionado com sucesso na categoria '{category}'!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)