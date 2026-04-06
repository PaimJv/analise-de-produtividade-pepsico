import pandas as pd
import json
import os
from utils import mapeamento

def gerar_referencia_por_arquivo(caminho_arquivo):
    """
    Lê um arquivo de exemplo e extrai assinaturas de dados (amostras)
    baseadas nas colunas definidas no dicionário de mapeamento do sistema.
    """
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
        return

    print(f"🔍 Analisando conteúdo de: {caminho_arquivo}...")

    # 1. Leitura inicial (usamos uma amostra de 1000 linhas para ter boa diversidade)
    try:
        if caminho_arquivo.endswith('.csv'):
            # Tenta detectar o encoding e separador para CSV
            df = pd.read_csv(caminho_arquivo, sep=None, engine='python', encoding='utf-8-sig', nrows=1000)
        else:
            # Para Excel, usamos o motor Calamine que você já configurou
            df = pd.read_excel(caminho_arquivo, engine='calamine', nrows=1000)
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo: {e}")
        return

    # 2. Construção da Base de Conhecimento
    # O JSON terá como chave o valor do mapeamento (ex: 'Localidade', 'VP')
    base_conhecimento = {}

    # Colunas que não são métricas nem datas (onde a correspondência de texto faz sentido)
    colunas_interesse = ['VP', 'Localidade', 'Centro_Custo', 'P_L', 'DenClsCst', 'Classe_Custo']

    # Percorremos o mapeamento oficial do seu sistema
    for nome_coluna_sap, nome_sistema in mapeamento.items():
        # Verificamos se esta coluna faz parte das colunas que queremos rastrear por conteúdo
        if nome_sistema in colunas_interesse:
            
            # Verificamos se o nome da coluna SAP existe no arquivo de exemplo
            if nome_coluna_sap in df.columns:
                # Extraímos os valores únicos, removemos nulos e limitamos a 150 exemplos
                # Usamos 150 para garantir que pegamos variações de nomes de cidades e centros de custo
                amostra = df[nome_coluna_sap].dropna().unique().tolist()
                
                # Armazenamos no dicionário usando o NOME DO SISTEMA como chave
                base_conhecimento[nome_sistema] = [str(x) for x in amostra[:150]]
                print(f"✅ Exemplos mapeados para sistema: '{nome_sistema}' (Coluna SAP: {nome_coluna_sap})")
            else:
                print(f"⚠️ Aviso: A coluna SAP '{nome_coluna_sap}' não foi encontrada neste arquivo.")

    # 3. Exportação para JSON
    try:
        with open('referencia_colunas.json', 'w', encoding='utf-8') as f:
            json.dump(base_conhecimento, f, ensure_ascii=False, indent=4)
        print("\n🚀 Sucesso! O arquivo 'referencia_colunas.json' foi gerado e está pronto para o logic.py.")
    except Exception as e:
        print(f"❌ Erro ao salvar o JSON: {e}")

# ==========================================
# CONFIGURAÇÃO: Defina aqui o arquivo modelo
# b==========================================
if __name__ == "__main__":
    # Coloque o caminho do arquivo que você quer usar como "professor" para o sistema
    arquivo_modelo = "Custos Facilities 2025.xlsx" 
    
    gerar_referencia_por_arquivo(arquivo_modelo)
