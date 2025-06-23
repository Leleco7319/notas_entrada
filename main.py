from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from typing import List
import os

from tasks.scrap_nfse import ScrapNotaFiscal

app = FastAPI(title="API de Notas Fiscais")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NotaFiscalRequest(BaseModel):
    login: str
    password: str
    chrome_profile: str = "chrome_profile_nfse"

class NotaFiscalResponse(BaseModel):
    sucesso: bool
    mensagem: str
    arquivos_baixados: List[str] = []

@app.post("/baixar-notas-fiscais", response_model=NotaFiscalResponse)
async def baixar_notas_fiscais(request: NotaFiscalRequest):
    try:
        scraper = ScrapNotaFiscal()
        driver = scraper.abrir_navegador(request.chrome_profile)
        
        try:
            scraper.get_info(driver, request.login, request.password)
            
            # Lista os arquivos baixados
            arquivos_baixados = os.listdir(scraper.download_dir)
            
            return NotaFiscalResponse(
                sucesso=True,
                mensagem="Notas fiscais baixadas com sucesso",
                arquivos_baixados=arquivos_baixados
            )
        finally:
            driver.quit()
            scraper.kill_chrome_instances()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao baixar notas fiscais: {str(e)}")

@app.get("/")
async def root():
    return {"mensagem": "API de notas fiscais está funcionando. Use o endpoint /baixar-notas-fiscais"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 