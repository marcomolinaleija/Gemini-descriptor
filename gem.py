"""
Gemini descriptor te permite enviar un archivo, ya sea de video o imágen a google gemini para obtener una descripción del contenido del mismo
Tiene opciones para ingresar un prompt personalizado, adjuntar el archivo, enviar el contenido junto con el prompt, copiar, guardar y eliminar la respuesta generada.
** Nota **
En muchas ocasiones hago referencia a la barra de estado, refiriéndome al texto estático que se muestra en el programa, no es una barra de estado tal cual.
"""

# Importaciones

import os
import time
import json
import threading

import wx
import pyperclip
from google import genai

from audio.speaker import alert

class ApiKeyManager:
	"""
	Clase para gestionar la API Key de Gemini
	"""
	# Archivo de la api_key en json.
	API_FILE = "api.json"
	
	@staticmethod
	def get_api_key():
		"""
		Obtiene la API key desde variables de entorno, si está configurada. si no, obtiene desde el archivo.
		"""
		# Intentamos obtener desde variable de entorno
		api_key = os.getenv("API_GEMINI")
		
		# Si no existe en variables de entorno, intentar cargar desde archivo
		if not api_key:
			try:
				# Verificamos existencia del archivo.
				if os.path.exists(ApiKeyManager.API_FILE):
					# Abrimos el archivo en modo lectura.
					with open(ApiKeyManager.API_FILE, 'r') as f:
						# Obtenemos el contenido con formato json.
						api_data = json.load(f)
						# Buscamos y obtenemos la api key
						api_key = api_data.get('api_key')
			except Exception as e:
				print(f"Error al cargar API key desde archivo: {e}")
		
		return api_key
	
	@staticmethod
	def save_api_key(api_key):
		"""
		Guarda la API key en un archivo
		"""
		try:
			# Abrimos el archivo en modo escritura
			with open(ApiKeyManager.API_FILE, 'w') as f:
				# Escribimos el contenido con formato json.
				json.dump({'api_key': api_key}, f)
			# Retornamos True si todo salió bien.
			return True
		except Exception as e:
			print(f"Error al guardar API key: {e}")
			return False

class GeminiUploaderApp(wx.Frame):
	"""
	Clase que contiene los controles para la interfaz junto con los métodos para interactuar con el modelo de gemini.
	"""
	# Archivo para el prompt
	PROMPT_FILE = "prompt.txt"

	def __init__(self):
		"""
		Inicialización de la interfaz
		"""
		# Llamamos al constructor.
		super().__init__(None, title="Carga de videos e imágenes con Gemini", size=(700, 600))
		
		# obtenemos la api key
		self.initialize_api_key()
		
		# Configuración visual.
		# Establecer color de fondo en gris.
		self.SetBackgroundColour(wx.Colour(240, 240, 240))
		
		# Panel principal
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		
		# Botón para configurar API Key
		api_button = wx.Button(panel, label="Configurar API Key")
		api_button.Bind(wx.EVT_BUTTON, self.configure_api_key)
		main_sizer.Add(api_button, flag=wx.ALIGN_RIGHT | wx.RIGHT, border=20)
		
		# Botón para salir de la aplicación
		exit_button = wx.Button(panel, label="Salir")
		exit_button.Bind(wx.EVT_BUTTON, self.on_exit)
		main_sizer.Add(exit_button, flag=wx.ALIGN_RIGHT | wx.RIGHT, border=20)
		
		# Sección de prompt
		prompt_box = wx.StaticBox(panel, label="Instrucciones para Gemini. Presiona tecla aplicaciones o f10 para mostrar opciones adicionales.")
		prompt_sizer = wx.StaticBoxSizer(prompt_box, wx.VERTICAL)
		# Creamos un cuadro de texto multilínea con un ancho que se ajusta automáticamente en base al panel, y una altura de 80 px.
		self.prompt_input = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 80))
		# Cargamos el prompt desde el archivo txt.
		self.load_prompt()
		# Evento para menú contextual en el cuadro de texto.
		self.prompt_input.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		# Manejador de teclas en el cuadro.
		self.prompt_input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
		prompt_sizer.Add(self.prompt_input, flag=wx.EXPAND | wx.ALL, border=10)
		
		main_sizer.Add(prompt_sizer, flag=wx.EXPAND | wx.ALL, border=10)
		
		# Sección de controles de archivo
		file_box = wx.StaticBox(panel, label="Selección de Archivo")
		file_sizer = wx.StaticBoxSizer(file_box, wx.VERTICAL)
		
		file_controls = wx.BoxSizer(wx.HORIZONTAL)
		# Cuadro de texto donde se mostrará la ruta del archivo seleccionado.
		self.file_path_text = wx.TextCtrl(panel, style=wx.TE_READONLY)
		file_controls.Add(self.file_path_text, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
		# Botón para seleccionar archivos.
		self.attach_button = wx.Button(panel, label="&Seleccionar archivo")
		self.attach_button.Bind(wx.EVT_BUTTON, self.attach_file)
		file_controls.Add(self.attach_button, flag=wx.ALIGN_CENTER_VERTICAL)
		
		file_sizer.Add(file_controls, flag=wx.EXPAND | wx.ALL, border=10)
		
		main_sizer.Add(file_sizer, flag=wx.EXPAND | wx.ALL, border=10)
		
		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		# Botón para enviar el archivo seleccionado
		self.send_button = wx.Button(panel, label="&Enviar archivo a Gemini")
		self.send_button.Bind(wx.EVT_BUTTON, self.send_file)
		# Deshabilitar hasta que el archivo esté seleccionado.
		self.send_button.Disable()
		# Establece el tamaño mínimo del botón send_button, con un ancho de 200 píxeles y altura ajustable automáticamente.
		self.send_button.SetMinSize((200, -1))
		button_sizer.Add(self.send_button, flag=wx.ALL, border=5)
		
		main_sizer.Add(button_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
		
		# Barra de progreso
		self.progress_gauge = wx.Gauge(panel, range=100, size=(-1, 20))
		# Ocultamos la barra de progreso.
		self.progress_gauge.Hide()
		main_sizer.Add(self.progress_gauge, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=20)
		
		# Campo de estado
		self.status_text = wx.StaticText(panel, label="")
		main_sizer.Add(self.status_text, flag=wx.ALL | wx.ALIGN_CENTER, border=5)
		
		# Sección de respuesta
		response_box = wx.StaticBox(panel, label="&Respuesta de Gemini")
		response_sizer = wx.StaticBoxSizer(response_box, wx.VERTICAL)
		
		self.response_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP, size=(-1, 200))
		response_sizer.Add(self.response_text, flag=wx.EXPAND | wx.ALL, border=10)
		
		main_sizer.Add(response_sizer, flag=wx.EXPAND | wx.ALL, border=10)
		
		# Botones de acción para la respuesta
		action_sizer = wx.BoxSizer(wx.HORIZONTAL)
		# Botón para copiar la respuesta generada
		self.copy_button = wx.Button(panel, label="&Copiar respuesta")
		self.copy_button.Bind(wx.EVT_BUTTON, self.copy_to_clipboard)
		# Ocultamos hasta que se proporcione respuesta.
		self.copy_button.Hide()
		action_sizer.Add(self.copy_button, flag=wx.RIGHT, border=10)
		# Botón para eliminar la respuesta del cuadro de texto.
		self.clear_button = wx.Button(panel, label="&Limpiar campo de respuesta")
		self.clear_button.Bind(wx.EVT_BUTTON, self.clear_description)
		self.clear_button.Hide()
		action_sizer.Add(self.clear_button)
		# Botón para guardar la respuesta en un archivo
		self.save_button = wx.Button(panel, label="&Guardar respuesta")
		self.save_button.Bind(wx.EVT_BUTTON, self.save_response)
		self.save_button.Hide()
		action_sizer.Add(self.save_button, flag=wx.LEFT, border=10)
		
		main_sizer.Add(action_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
		
		panel.SetSizer(main_sizer)
		
		# Barra de estado
		self.CreateStatusBar()
		# Configuramos el texto de la barra de estado con un texto que indica al usuario que el programa está listo para recivir archivos.
		self.SetStatusText("Listo para procesar archivos.")
		
		# Variables para controlar el proceso
		self.selected_file = None
		self.processing = False
		
		# Centrar en pantalla
		self.Centre()
		
		# Verificamos si tenemos una API key válida
		self.check_api_key_validity()

	def initialize_api_key(self):
		"""
		Inicializa la API key al iniciar la aplicación
		"""
		# Intentamos obtener la api key
		self.api_key = ApiKeyManager.get_api_key()
		
		# Si no hay API key disponible, la solicitamos al usuario
		if not self.api_key:
			self.request_api_key()

		# Inicializar cliente de Gemini con la API key obtenida
		if self.api_key:
			self.initialize_gemini_client()

	def initialize_gemini_client(self):
		"""
		Inicializa el cliente de Gemini con la API key actual
		"""
		
		try:
			self.client = genai.Client(api_key=self.api_key)
			return True
		except Exception as e:
			self.show_error(f"Error al inicializar cliente Gemini: {str(e)}")
			return False

	def request_api_key(self):
		"""
		Solicita la API key al usuario mediante un diálogo
		"""
		
		dlg = wx.TextEntryDialog(
			self, 
			"No se encontró API Key de Gemini. Por favor, introduce tu API Key:",
			"Configuración de API Key"
		)
		
		if dlg.ShowModal() == wx.ID_OK:
			# Obtenemos la API key del diálogo
			self.api_key = dlg.GetValue().strip()
			if self.api_key:
				# Guardamos la API key en el archivo
				if ApiKeyManager.save_api_key(self.api_key):
					self.update_status("API Key guardada correctamente.")
					alert("API Key guardada correctamente")
					# Inicializar cliente de Gemini
					self.initialize_gemini_client()
				else:
					self.show_error("No se pudo guardar la API Key.")
			else:
				self.show_error("La API Key no puede estar vacía.")
		
		dlg.Destroy()

	def configure_api_key(self, event):
		"""
		Permite al usuario configurar manualmente la API Key
		"""
		# Obtenemos la API key. si no hay configurada, se inicializa la variable sin contenido.
		current_key = self.api_key if self.api_key else ""
		
		dlg = wx.TextEntryDialog(
			self, 
			"Introduce tu API Key de Gemini:",
			"Configuración de API Key",
			value=current_key
		)
		
		if dlg.ShowModal() == wx.ID_OK:
			# Obtenemos la API key del diálogo
			new_key = dlg.GetValue().strip()
			# Si la API key ingresada es distinta a la configurada, actualizamos y recargamos el cliente de genai
			if new_key and new_key != self.api_key:
				self.api_key = new_key
				if ApiKeyManager.save_api_key(self.api_key):
					self.update_status("API Key actualizada correctamente.")
					alert("API Key actualizada correctamente")
					self.initialize_gemini_client()
				else:
					self.show_error("No se pudo guardar la API Key.")
		
		dlg.Destroy()

	def check_api_key_validity(self):
		"""
		Verifica si la API key actual es válida
		"""
		# Si no tenemos una API key, actualizamos el texto de la barra de estado indicando que no hay API key configurada.
		if not self.api_key:
			self.update_status("API Key no configurada. Configure su API Key para usar la aplicación.")
			alert("API Key no configurada")
			return False
		
		# Aquí se podría añadir una llamada a la API para verificar que sea válida. Por ahora, se dejará así
		return True

	def attach_file(self, event):
		"""
		Método para seleccionar un archivo
		"""
		# Verificamos primero si tenemos una API key válida
		if not self.check_api_key_validity():
			self.show_error("Debe configurar una API Key válida antes de usar la aplicación.")
			return
			
		wildcard = "Archivos multimedia (*.mp4;*.mov;*.avi;*.png;*.jpg)|*.mp4;*.mov;*.avi;*.png;*.jpg"
		# Iniciamos el diálogo para la carga de archivos
		with wx.FileDialog(self, "Selecciona un archivo", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
			if dialog.ShowModal() == wx.ID_OK:
				# Obtenemos la ruta seleccionada
				self.selected_file = dialog.GetPath()
				# Configuramos el texto en el cuadro para la ruta.
				self.file_path_text.SetValue(self.selected_file)
				# Habilitamos el botón para enviar
				self.send_button.Enable()
				# Actualizamos el texto de la barra de estado
				self.update_status(f"Archivo seleccionado: {os.path.basename(self.selected_file)}")
				alert(f"Archivo seleccionado: {os.path.basename(self.selected_file)}")
				
				# Limpiar respuestas anteriores
				self.response_text.SetValue("")
				self.hide_result_buttons()

	def send_file(self, event):
		"""
		Método para enviar el archivo
		"""
		
		# Verificamos primero si tenemos una API key válida
		if not self.check_api_key_validity():
			self.show_error("Debe configurar una API Key válida antes de usar la aplicación.")
			return
			
		# Si no se seleccionó una ruta, le indicamos al usuario que lo haga antes de continuar
		if not self.selected_file:
			self.show_error("Por favor, selecciona un archivo primero.")
			return
		# Si self.processing es True, no se permiten más cargas y se le indica al usuario que ya hay un proceso activo.
		if self.processing:
			self.show_error("Ya hay un proceso en curso. Por favor espera.")
			return
		
		# Deshabilitamos controles durante el procesamiento
		# Modificamos self.PROCESSING a True, y deshabilitamos los botones para seleccionar archivo y para enviar
		self.processing = True
		self.send_button.Disable()
		self.attach_button.Disable()
		self.response_text.SetValue("")
		# Actualizamos la barra de estado.
		self.update_status("Iniciando procesamiento del archivo...")
		alert("Iniciando procesamiento del archivo")
		
		# Mostramos indicador de progreso
		self.progress_gauge.SetValue(0)
		self.progress_gauge.Show()
		
		# Ejecutamos la solicitud en un hilo separado para evitar bloquear la interfaz
		threading.Thread(target=self.process_file).start()

	def process_file(self):
		"""
		Método para procesar el archivo enviado
		"""
		try:
			# Actualizamos progreso: 10%
			wx.CallAfter(self.update_progress, 10, "Subiendo archivo...")
			
			# Subimos el archivo
			video_file = self.client.files.upload(file=self.selected_file)
			
			# Actualizamos progreso: 40%
			wx.CallAfter(self.update_progress, 40, "Archivo subido. Procesando...")
			
			# Verificamos estado del archivo
			processing_iterations = 0
			while video_file.state.name == "PROCESSING":
				# Mientras el archivo esté en procesamiento, esperamos 2 segundos antes de añadir una iteración a la variable y validar si seguimos en el proceso del video
				time.sleep(2)
				processing_iterations += 1
				video_file = self.client.files.get(name=video_file.name)
				
				# Incrementamos progreso de 40% a 70% durante el procesamiento
				progress = min(40 + processing_iterations * 2, 70)
				wx.CallAfter(self.update_progress, progress, "Procesando archivo en Gemini...")
			# Si el procesamiento del archivo falló, mostramos el error.
			if video_file.state.name == "FAILED":
				wx.CallAfter(self.show_error, "Error al procesar el archivo en Gemini.")
				return
			
			# Actualizamos progreso: 70%
			wx.CallAfter(self.update_progress, 70, "Archivo procesado. Generando respuesta...")
			
			# Obtenemos el contenido del prompt
			prompt = self.prompt_input.GetValue().strip()
			if not prompt:
				# Si no se ingresa uno, se utiliza uno por defecto.
				prompt = "Describe en detalle lo que se muestra en este archivo en español."
			
			# Creamos la solicitud a Gemini
			response = self.client.models.generate_content(
				model="gemini-2.0-flash-exp",
				contents=[video_file, prompt]
			)
			
			# Actualizamos progreso: 100%
			wx.CallAfter(self.update_progress, 100, "Respuesta generada correctamente.")
			
			# Mostramos la respuesta en el cuadro de texto
			wx.CallAfter(self.update_response, response.text)
			
		except Exception as e:
			error_message = f"Error: {str(e)}"
			wx.CallAfter(self.show_error, error_message)
		
		finally:
			# Restauramos controles cuando se completa el proceso
			wx.CallAfter(self.complete_processing)

	def update_progress(self, value, status_message):
		"""
		Método que actualiza la barra de estado y de progreso
		"""
		# Configuramos los valores de la barra de progreso, de estado y notificamos con el método alert los textos de la barra de estado.
		self.progress_gauge.SetValue(value)
		self.update_status(status_message)
		alert(status_message)

	def update_response(self, response_text):
		"""
		Método para actualizar la respuesta en el campo de texto
		"""
		
		# Mostramos la respuesta generada en el cuadro de texto
		self.response_text.SetValue(response_text)
		
		message = "Respuesta de Gemini generada correctamente."
		self.update_status(message)
		alert(message)
		
		# Mostramos botones de acción
		self.show_result_buttons()

	def complete_processing(self):
		"""
		Método que devuelve los controles a como estaban originalmente, manteniendo los botones de acción para la respuesta vicibles, indicando que la respuesta fue resivida por el usuario
		"""
		
		# Ocultamos la barra de progreso
		self.progress_gauge.Hide()
		
		# Habilitamos controles
		self.send_button.Enable()
		self.attach_button.Enable()
		# Devolvemos PROCESSING a False
		self.processing = False
		
		# Actualizamos la disposición
		self.Layout()

	def copy_to_clipboard(self, event):
		"""
		Método para copiar la respuesta generada al portapapeles
		"""
		# Obtenemos el texto desde el cuadro para la respuesta.
		text = self.response_text.GetValue()
		if text:
			# Si hay texto, se copia y se actualiza la barra de estado.
			pyperclip.copy(text)
			self.update_status("Respuesta copiada al portapapeles.")
			alert("Respuesta copiada al portapapeles")
		else:
			self.update_status("No hay respuesta para copiar.")
			alert("No hay respuesta para copiar")

	def clear_description(self, event):
		"""
		Método para eliminar la respuesta generada del cuadro de texto
		"""
		
		self.response_text.SetValue("")
		# Ocultamos los botones de acción y actualizamos la barra de estado
		self.hide_result_buttons()
		self.update_status("Respuesta borrada.")
		alert("Respuesta borrada")

	def save_response(self, event):
		"""
		Método para guardar la respuesta generada en un archivo de texto (*.txt)
		"""
		# Obtenemos el contenido del cuadro de respuesta
		text = self.response_text.GetValue()
		if not text:
			# Si no hay texto actualizamos la barra de estado
			self.update_status("No hay respuesta para guardar.")
			alert("No hay respuesta para guardar")
			return
			
		# Iniciamos el diálogo para guardar el archivo
		with wx.FileDialog(self, "Guardar respuesta", 
						  wildcard="Archivos de texto (*.txt)|*.txt",
						  style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
			
			if fileDialog.ShowModal() == wx.ID_CANCEL:
				# Si se cancela el diálogo, retornamos.
				return
				
			# Obtenemos el nombre ingresado en el diálogo
			pathname = fileDialog.GetPath()
			try:
				# Intentamos guardar el archivo, escribiendo la respuesta
				with open(pathname, 'w', encoding='utf-8') as file:
					file.write(text)
				# Actualizamos la barra de estado.
				self.update_status(f"Respuesta guardada en {pathname}")
				alert("Respuesta guardada correctamente")
			except IOError:
				self.show_error(f"No se pudo guardar en {pathname}")

	def show_error(self, message):
		"""
		Método para mostrar los errores que ocurran dentro del programa
		"""
		
		wx.MessageBox(message, "Error", wx.ICON_ERROR)
		self.update_status(f"ERROR: {message}")
		alert(f"Error: {message}")
		
		# Restauramos los controles
		self.send_button.Enable()
		self.attach_button.Enable()
		self.progress_gauge.Hide()
		self.processing = False
		self.Layout()

	def update_status(self, message):
		"""
		Método para actualizar el StaticText
		"""
		
		self.status_text.SetLabel(message)
		self.SetStatusText(message)
		self.Layout()

	def show_result_buttons(self):
		"""
		Método para mostrar los botones de acción para la Respuesta
		"""
		
		self.copy_button.Show()
		self.clear_button.Show()
		self.save_button.Show()
		self.Layout()

	def hide_result_buttons(self):
		"""
		Método para ocultar los botones de acción cuando se elimina la respuesta del cuadro de texto
		"""
		
		self.copy_button.Hide()
		self.clear_button.Hide()
		self.save_button.Hide()
		self.Layout()

	def on_exit(self, event):
		"""
		Método para salir del programa
		"""
		
		self.Close()

	def on_context_menu(self, event):
		"""
		Método para crear el menú contextual
		"""
		
		menu = wx.Menu()
		# Items, guardar prompt
		save_item = menu.Append(wx.ID_ANY, "Guardar prompt")
		# Items, copiar prompt al portapapeles
		copy_item = menu.Append(wx.ID_ANY, "Copiar al portapapeles")
		
		self.Bind(wx.EVT_MENU, self.save_prompt_to_file, save_item)
		self.Bind(wx.EVT_MENU, self.copy_prompt_to_clipboard, copy_item)
		
		self.PopupMenu(menu)
		menu.Destroy()

	def on_key_down(self, event):
		"""
		Método para el manejo de teclas y mostrar el menú contextual al presionar f10 o tecla aplicaciones
		"""
		
		if event.GetKeyCode() in [wx.WXK_F10, wx.WXK_WINDOWS_MENU]:
			self.on_context_menu(event)
		event.Skip()

	def save_prompt_to_file(self, event):
		"""
		Método para guardar el prompt en un archivo de texto (*.txt)
		"""
		# Obtenemos el texto del prompt desde el cuadro de texto
		prompt_text = self.prompt_input.GetValue()
		if not prompt_text:
			# Si no hay prompt, se muestra mensaje de error
			self.update_status("No hay prompt para guardar.")
			alert("No hay prompt para guardar")
			return
		
		try:
			# Intentamos guardar el archivo escribiendo el prompt obtenido
			with open(self.PROMPT_FILE, 'w', encoding='utf-8') as file:
				file.write(prompt_text)
			# Actualizamos estado
			self.update_status(f"Prompt guardado en {self.PROMPT_FILE}")
			alert("Prompt guardado correctamente")
		except IOError:
			self.show_error(f"No se pudo guardar en {self.PROMPT_FILE}")

	def copy_prompt_to_clipboard(self, event):
		"""
		método para copiar el prompt al portapapeles
		"""
		# Obtenemos el prompt del cuadro de texto
		prompt_text = self.prompt_input.GetValue()
		if prompt_text:
			# Si hay texto, se copia al portapapeles y se actualiza el estado
			pyperclip.copy(prompt_text)
			self.update_status("Prompt copiado al portapapeles.")
			alert("Prompt copiado al portapapeles")
		else:
			self.update_status("No hay prompt para copiar.")
			alert("No hay prompt para copiar")

	def load_prompt(self):
		"""
		Método para cargar el prompt desde el archivo de texto
		"""
		
		try:
			# Verificamos la existencia del archivo
			if os.path.exists(self.PROMPT_FILE):
				# Si existe, lo abrimos en modo lectura y obtenemos el texto ingresado
				with open(self.PROMPT_FILE, 'r', encoding='utf-8') as file:
					prompt_text = file.read()
				# Lo configuramos en el cuadro de texto
				self.prompt_input.SetValue(prompt_text)
			else:
				# Valor predeterminado si no existe el archivo
				self.prompt_input.SetValue("Describe en detalle lo que se muestra en este archivo en español.")
		except IOError:
			self.update_status(f"Error al cargar el prompt desde {self.PROMPT_FILE}")
			alert(f"Error al cargar el prompt desde {self.PROMPT_FILE}")

if __name__ == "__main__":
	app = wx.App(False)
	frame = GeminiUploaderApp()
	frame.Show()
	app.MainLoop()
