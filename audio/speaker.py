import ctypes
import json
import os

# Obtén el directorio actual donde se encuentra el script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define la ruta a la DLL dentro de la subcarpeta 'lib'
dll_path = os.path.join(current_dir, '..', 'lib', 'nvdaControllerClient64.dll')  # Ajusta según el nombre y la ubicación de tu DLL

# Carga la DLL de NVDA Controller
nvda_dll = ctypes.CDLL(dll_path)

# Define el tipo de argumento y el tipo de retorno para la función en la DLL
nvda_dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
nvda_dll.nvdaController_speakText.restype = None

def alert(message, interrupt=False):
    if voice_output_enabled():
        speak_text(message)

def speak_text(text):
    # Llama a la función de la DLL para que NVDA lea el texto
    nvda_dll.nvdaController_speakText(text)

def voice_output_enabled():
    documents_dir = os.path.expanduser("~/Documents")
    app_data_dir = os.path.join(documents_dir, "ml_player_data")
    config_file = os.path.join(app_data_dir, "config.json")
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
            return config.get('voice_output_enabled', False)
    except FileNotFoundError:
        return False

