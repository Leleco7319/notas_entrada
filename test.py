import os
import shutil
from tasks.scrap_nfse import ScrapNotaFiscal
import asyncio
import random

async def main():
    scrap_nota_fiscal = ScrapNotaFiscal()
    numero_aleatorio = random.randint(1, 100)

    # Diretório base onde os perfis são armazenados
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Procura por diretórios que começam com "chrome_profile_"
    for item in os.listdir(base_dir):
        
        if item.startswith("chrome_profile_"):
            profile_path = os.path.join(base_dir, item)
            try:
                if os.path.isdir(profile_path):
                    shutil.rmtree(profile_path)
                    print(f"Perfil removido: {profile_path}")
            except Exception as e:
                print(f"Erro ao remover perfil {profile_path}: {e}")
    
    profile_dir = f"chrome_profile_{numero_aleatorio}"
    driver = scrap_nota_fiscal.abrir_navegador(profile_dir)
    info = scrap_nota_fiscal.get_info(driver, "SERVOPAADM", "adm#2025", ["Maio", "Junho"])
    print(info)
    scrap_nota_fiscal.kill_chrome_instances()
    
    

if __name__ == "__main__":
    asyncio.run(main())
