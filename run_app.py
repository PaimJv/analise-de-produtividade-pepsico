"""
Para gerar o executável:

python -m PyInstaller --onefile --noconsole --name "Analise de produtividade PepsiCo" --copy-metadata streamlit --collect-all streamlit --collect-all groq --collect-all plotly --collect-all openpyxl --hidden-import openpyxl.cell._writer --add-data "main.py;." --add-data "logic.py;." --add-data "sidebar.py;." --add-data "components.py;." --add-data "utils.py;." --add-data "ia_engine.py;." run_app.py

"""

import streamlit.web.cli as stcli
import os, sys

def resolve_path(path):
    """Resolve o caminho do arquivo para o ambiente temporário do PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Se estiver rodando como executável
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__name__)
    return os.path.abspath(os.path.join(base_path, path))

if __name__ == "__main__":
    # Configura os argumentos como se você estivesse no terminal
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("main.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())