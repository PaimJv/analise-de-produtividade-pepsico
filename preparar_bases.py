import pandas as pd

def converter_para_parquet():
    print("Iniciando compressão de dados...")

    # 1. Ajuste o nome dos seus arquivos CSV originais aqui
    arquivo_cc = "facilities/analise-financeira-pepsico/arquivos auxiliares/Base - CC.csv"
    arquivo_contas = "facilities/analise-financeira-pepsico/arquivos auxiliares/Base - Contas e Linha P&L.csv"

    # --- PROCESSANDO CENTROS DE CUSTO ---
    print(f"Lendo {arquivo_cc}...")
    df_cc = pd.read_csv(arquivo_cc, sep=';', encoding='utf-8-sig', dtype=str)
    
    # Comprime os textos em categorias (Reduz muito o tamanho final)
    for col in df_cc.columns:
        df_cc[col] = df_cc[col].astype('category')
        
    df_cc.to_parquet("dim_centros_custo.parquet", engine='pyarrow', index=False)
    print("✅ Centros de Custo salvos como dim_centros_custo.parquet")

    # --- PROCESSANDO CONTAS ---
    print(f"Lendo {arquivo_contas}...")
    df_contas = pd.read_csv(arquivo_contas, sep=';', encoding='utf-8-sig', dtype=str)
    
    for col in df_contas.columns:
        df_contas[col] = df_contas[col].astype('category')
        
    df_contas.to_parquet("dim_contas.parquet", engine='pyarrow', index=False)
    print("✅ Contas salvas como dim_contas.parquet")

if __name__ == "__main__":
    converter_para_parquet()