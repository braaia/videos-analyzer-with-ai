import re, requests, warnings
from time import time
from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.animation import Animation
from youtube_transcript_api import YouTubeTranscriptApi
from kivy.properties import BooleanProperty, NumericProperty
from kivy.core.text import LabelBase
from kivy.metrics import sp
from kivy.uix.settings import Settings
from kivy.uix.spinner import Spinner
from kivy.config import ConfigParser
from configparser import NoOptionError
from kivy.uix.settings import SettingsWithSidebar
from kivy.uix.popup import Popup
from kivy.config import Config
from kivy.utils import platform

Config.set('kivy', 'exit_on_escape', '0')  # Desativa saída com ESC
warnings.filterwarnings("ignore", category=UserWarning)  # Ignora alguns avisos

# Configurações para melhorar a experiência com o teclado
Config.set('kivy', 'keyboard_mode', 'systemanddock')
Window.softinput_mode = 'below_target'
Window.clearcolor = (0.96, 0.96, 0.96, 1)

LabelBase.register(name='JetBrainsMono',
                  fn_regular='fonts/JetBrainsMono-Regular.ttf',  # Coloque na pasta fonts/
                  fn_bold='fonts/JetBrainsMono-Bold.ttf')

class SettingsWithSpinner(Settings):
    """Implementação alternativa do Settings com Spinner"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.spinner = None
        
    def add_spinner(self):
        """Adiciona um spinner de carregamento"""
        if not self.spinner:
            from kivy.uix.spinner import Spinner
            self.spinner = Spinner(
                size_hint=(None, None),
                size=(dp(100), dp(100)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5},
                active=True,
                color=(0.2, 0.6, 1, 1)
            )
            self.add_widget(self.spinner)
    
    def remove_spinner(self):
        """Remove o spinner"""
        if self.spinner:
            self.remove_widget(self.spinner)
            self.spinner = None

class AndroidFriendlyScrollView(ScrollView):
    """ScrollView otimizado para Android com rolagem por gestos"""
    scroll_sensitivity = NumericProperty(dp(20))
    scroll_velocity_threshold = NumericProperty(dp(100))
    smooth_scroll = BooleanProperty(True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._touch_start = None
        self._velocity = 0
        self._scroll_animation = None
        self._fling_animation = None
        self._last_touch_time = 0
        
        # Configurações de visualização
        self.bar_width = dp(10)
        self.bar_color = [.6, .6, .6, .9]
        self.bar_inactive_color = [.6, .6, .6, .3]
        self.scroll_type = ['bars', 'content']
        self.effect_cls = 'DampedScrollEffect'
        
        # Configura o efeito de scroll
        if hasattr(self.effect_x, 'scroll_friction'):
            self.effect.scroll_friction = 0.05

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
            
        if self._scroll_animation:
            self._scroll_animation.cancel(self)
        if self._fling_animation:
            self._fling_animation.cancel(self)
            
        self._touch_start = (touch.pos, time())
        self._velocity = 0
        self._last_touch_time = time()
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        # Detecta gesto de pinça para zoom
        if len(touch.grab_list) > 1:  # Multitouch
            self.adjust_font_size_based_on_gesture(touch)

        if touch.grab_current is not self:
            return False
            
        if not self._touch_start:
            return True
            
        current_time = time()
        start_pos, start_time = self._touch_start
        dy = start_pos[1] - touch.pos[1]  # Alteração principal aqui
        
        # Atualiza scroll
        new_scroll_y = self.scroll_y + (dy / self.height)
        new_scroll_y = max(0, min(1, new_scroll_y))
        
        # Calcula velocidade
        dt = current_time - start_time
        if dt > 0:
            self._velocity = dy / dt
        else:
            self._velocity = 0
            
        self.scroll_y = new_scroll_y
        self._touch_start = (touch.pos, current_time)
        self._last_touch_time = current_time
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
            
        touch.ungrab(self)
        current_time = time()
        
        # Calcula velocidade final
        if self._touch_start:
            start_pos, start_time = self._touch_start
            dt = current_time - start_time
            dy = touch.pos[1] - start_pos[1]
            if dt > 0:
                self._velocity = dy / dt
        
        # Aplica efeito de fling se necessário
        if abs(self._velocity) > self.scroll_velocity_threshold:
            self._apply_fling_effect()
            
        self._touch_start = None
        return True

    def _apply_fling_effect(self):
        """Efeito de continuidade quando o usuário desliza rápido"""
        if self._fling_animation:
            self._fling_animation.cancel(self)
            
        distance = (self._velocity / 1000)
        new_y = max(0, min(1, self.scroll_y + distance))
        
        self._fling_animation = Animation(
            scroll_y=new_y,
            d=abs(distance)*0.5,
            t='out_quad'
        )
        self._fling_animation.start(self)

    def scroll_to_target(self, target_widget, padding=dp(20)):
        """Rola suavemente para um widget específico"""
        if not self.parent or not target_widget:
            return
            
        widget_pos = target_widget.to_window(*target_widget.pos)
        scroll_pos = self.to_window(*self.pos)
        relative_y = widget_pos[1] - scroll_pos[1]
        new_scroll = max(0, min(1, relative_y / self.parent.height))
        
        Animation(scroll_y=new_scroll, d=0.3, t='out_quad').start(self)

class SelfSizingGridLayout(GridLayout):
    """Layout que se auto-ajusta perfeitamente"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            minimum_height=self._update_height,
            children=self._update_height
        )

    def _update_height(self, *args):
        if self.parent:
            self.height = max(self.minimum_height, self.parent.height)
            if getattr(self.parent, 'auto_scroll', False) and self.parent.scroll_y < 0.1:
                self.parent.scroll_y = 0

class VideoAnalyzerApp(App):
    font_size = NumericProperty(16)  # Tamanho base da fonte em sp

    def __init__(self):
        super().__init__()
        self.chat_history = None
        self.scroll_view = None
        self.question_input = None
        self.load_btn = None
        self.current_video_id = None
        self.current_transcript = None
        self.video_loaded = None
        self.main_layout = None
        self.url_input = None

    def build(self):
        # Configurações específicas para Android
        self.title = "Analisador de Vídeos"
        self.config = ConfigParser()
        self.load_font_config()

        from kivy.config import Config
        Config.set('input', 'mouse', 'mouse,disable_multitouch')
        
        self.main_layout = BoxLayout(orientation='vertical', spacing=dp(5))        
        
        # Área de URL
        self.build_url_input()
        
        # Área de chat
        self.build_chat_interface()
        
        # Variáveis de estado
        self.current_video_id = ""
        self.current_transcript = ""
        self.video_loaded = False
        
        return self.main_layout
    
    def initialize_config(self):
        """Configuração inicial"""
        self.config.read('config.ini')
        if not self.config.has_section('app'):
            self.config.add_section('app')
        if not self.config.has_option('app', 'font_size'):
            self.config.set('app', 'font_size', '16')
        self.config.write()
        
        """Inicializa o arquivo de configuração com valores padrão"""
        # Cria a seção 'app' se não existir
        if not self.config.has_section('app'):
            self.config.add_section('app')
        
        # Define valores padrão
        default_settings = {
            'font_size': '16',
            'font_family': 'JetBrainsMono'
        }
        
        # Aplica padrões para configurações faltantes
        for key, value in default_settings.items():
            if not self.config.has_option('app', key):
                self.config.set('app', key, value)
        
        # Salva o arquivo de configuração
        self.config.write()
        
        # Agora podemos carregar com segurança
        self.load_font_config()

    def load_font_config(self):
        """Carrega as configurações de fonte garantindo valores válidos"""
        try:
            # Tenta ler o arquivo de configuração
            self.config.read('config.ini')
            
            # Garante que a seção existe
            if not self.config.has_section('app'):
                self.initialize_config()
            
            # Obtém o tamanho da fonte com fallback seguro
            try:
                self.font_size = int(self.config.get('app', 'font_size'))
            except (ValueError, NoOptionError):
                self.font_size = 16
                self.config.set('app', 'font_size', '16')
            
            # Aplica o tamanho da fonte
            Clock.schedule_once(lambda dt: self.apply_font_size(), 0.1)
            
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
            self.font_size = 16  # Valor padrão

    def apply_font_size(self):
        """Aplica o tamanho de fonte atual a todos os widgets de texto"""
        if hasattr(self, 'chat_history'):
            for message in self.chat_history.children:
                for widget in message.children:
                    if isinstance(widget, Label):
                        widget.font_size = sp(self.font_size)
        
        if hasattr(self, 'question_input'):
            self.question_input.font_size = sp(self.font_size)
        
        if hasattr(self, 'url_input'):
            self.url_input.font_size = sp(self.font_size)
        
        if hasattr(self, 'load_btn'):
            self.load_btn.font_size = sp(self.font_size)
        
    def build_settings(self):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        
        # Layout principal que conterá o settings e o botão
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # Cria o painel de configurações normal
        settings = SettingsWithSidebar()
        settings.add_kivy_panel()
        settings.add_json_panel(
            'Configurações',
            self.config,
            'settings.json'
        )
        
        # Adiciona o botão de fechar
        close_btn = Button(
            text='Fechar',
            size_hint_y=None,
            height=dp(50),
            background_color=(0.8, 0.2, 0.2, 1)
        )
        close_btn.bind(on_press=lambda x: self._settings_popup.dismiss())
        close_btn.background_normal = ''
        close_btn.background_color = (0.8, 0.2, 0.2, 1)
        close_btn.color = (1, 1, 1, 1)
        close_btn.font_name = 'JetBrainsMono'
        close_btn.font_size = sp(18)
        
        # Adiciona ao layout
        layout.add_widget(settings)
        layout.add_widget(close_btn)
        
        return layout

    def open_settings(self, instance):
        """Abre o painel de configurações com fechamento funcional"""
        try:
            # Fecha o popup existente se houver
            if hasattr(self, '_settings_popup') and self._settings_popup:
                self._settings_popup.dismiss()
                self._settings_popup = None
            
            # Cria o conteúdo ANTES do popup
            try:
                content = self.build_settings()
            except Exception as e:
                print(f"Erro ao criar conteúdo: {e}")
                self.show_error_message("Erro ao criar configurações")
                return

            self._settings_popup = Popup(
                title='Configurações',
                content=content,
                size_hint=(0.8, 0.8) if platform == 'android' else (0.7, 0.8),
                auto_dismiss=False  # Importante para controlar o fechamento
            )
        
            self._settings_popup.opacity = 0
            Animation(opacity=1, duration=0.2).start(self._settings_popup)
            self._settings_popup.bind(
                on_dismiss=lambda x: Animation(opacity=0, duration=0.2).start(x)
            )

            # Botão de voltar no Android
            if platform == 'android':
                self._setup_android_back_handler()

            self._settings_popup.open()
        except Exception as e:
            print(f"Erro ao abrir configurações: {e}")
            self.show_error_message("Erro ao abrir configurações")
    
    def _setup_android_back_handler(self):
        """Configura o botão voltar do Android"""
        if platform != 'android':
            return
            
        try:
            from android import run_on_ui_thread
            from jnius import autoclass
            
            @run_on_ui_thread
            def back_handler():
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                activity.runOnUiThread(autoclass('java.lang.Runnable')(lambda: (
                    self._settings_popup.dismiss() if hasattr(self, '_settings_popup') else None
                )))
            
            self._android_back_handler = back_handler
        except Exception as e:
            print(f"Erro no handler Android: {e}")

    def on_settings_dismiss(self, instance):
        """Limpa referências quando o popup é fechado"""
        if hasattr(self, '_settings_popup'):
            self._settings_popup = None

    def show_error_message(self, message):
        """Mostra mensagens de erro"""
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        
        content = Label(text=message)
        popup = Popup(title='Erro',
                    content=content,
                    size_hint=(0.6, 0.3))
        popup.open()

    def on_config_change(self, config, section, key, value):
        """Atualiza as configurações quando alteradas"""
        try:
            if key == 'font_size':
                size = max(12, min(24, int(value)))  # Garante entre 12 e 24
                if 12 <= size <= 24:  # Validação manual
                    self.font_size = size
                    self.apply_font_size()
                    self.config.set('app', 'font_size', str(size))
                    self.config.write()
        except Exception as e:
            print(f"Erro ao atualizar configuração: {e}")

    def create_font_size_button(self):
        """Cria um botão flutuante para ajuste rápido"""
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.slider import Slider
        
        self.font_adjuster = FloatLayout(size_hint=(None, None), size=(300, 80))
        
        slider = Slider(min=12, max=24, value=self.font_size,
                       size_hint=(0.8, 0.5), pos_hint={'center_x': 0.5})
        slider.bind(value=self.on_font_slider_change)
        
        self.font_adjuster.add_widget(slider)
        return self.font_adjuster

    def on_font_slider_change(self, instance, value):
        """Quando o slider de fonte é movido"""
        self.font_size = int(value)
        self.apply_font_size()

    def create_settings(self):
        """Cria o painel de configurações com spinner"""
        settings = SettingsWithSpinner()
        
        # Adiciona um spinner enquanto carrega
        settings.add_spinner()
        
        # Adiciona as configurações após um pequeno delay
        Clock.schedule_once(lambda dt: self._finish_settings(settings), 0.1)
        
        return settings

    def _finish_settings(self, settings):
        """Finaliza a configuração do painel"""
        settings.remove_spinner()
        settings.add_kivy_panel()  # Painel padrão do Kivy
        settings.add_json_panel('Configurações', self.config, 'settings.json')

    def build_url_input(self):
        """Área de entrada de URL"""
        url_layout = BoxLayout(
            orientation='horizontal',
            spacing=dp(5),
            size_hint_y=None,
            height=dp(50),
            padding=[dp(10), dp(5), dp(10), dp(5)]
        )

        self.url_input = TextInput(
            hint_text='Cole a URL do YouTube aqui...',
            size_hint_x=0.8,
            height=dp(40),
            multiline=False
        )

        self.load_btn = Button(
            text='Carregar Vídeo',
            size_hint_x=0.2,
            height=dp(40),
            background_color=(0.5, 0, 1, 1)
        )
        self.load_btn.bind(on_press=self.analyze_video)

        url_layout.add_widget(self.url_input)
        url_layout.add_widget(self.load_btn)
        self.main_layout.add_widget(url_layout)

    def build_chat_interface(self):
        """Área de chat com scroll otimizado para Android"""
        chat_container = BoxLayout(orientation='vertical')
        
        # Histórico de chat
        self.chat_history = SelfSizingGridLayout(
            cols=1,
            spacing=dp(10),
            size_hint_y=None,
            padding=[dp(10), dp(10)]
        )
        
        # ScrollView otimizado para Android
        self.scroll_view = AndroidFriendlyScrollView()
        self.scroll_view.add_widget(self.chat_history)

        
        # Área de perguntas
        question_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(60),
            padding=[dp(10), 0, dp(10), dp(10)]
        )

        self.question_input = TextInput(
            hint_text='Digite sua pergunta...',
            size_hint_x=0.7
        )

        clear_btn = Button(
            text='Limpar',
            size_hint_x=0.15,
            background_color=(1, 0.5, 0, 1)
        )
        clear_btn.bind(on_press=self.clear_chat)

        send_btn = Button(
            text='Enviar',
            size_hint_x=0.15,
            background_color=(0, 1, 1, 1)
        )
        send_btn.bind(on_press=self.send_question)

        question_layout.add_widget(clear_btn)
        question_layout.add_widget(self.question_input)
        question_layout.add_widget(send_btn)

        chat_container.add_widget(self.scroll_view)
        chat_container.add_widget(question_layout)
        self.main_layout.add_widget(chat_container)

        # Adicione um botão de configurações
        settings_btn = Button(
            text='Ajustes',
            size_hint_x=0.15,
            background_color=(0.3, 0.3, 0.3, 1)
        )
        settings_btn.bind(on_press=self.open_settings)
        
        # Adicione ao layout de perguntas
        question_layout.add_widget(settings_btn)

    def add_message(self, sender, text):
        """Adiciona uma mensagem ao chat com formatação adequada"""
        message_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=dp(5),
            padding=[dp(5), dp(5), dp(5), dp(5)]
        )

        sender_label = Label(
            font_context='JetBrainsMono',  # Contexto de renderização
            font_hinting='normal',  # Melhora a renderização
            text=f"[b]{'Você' if sender == 'user' else 'BOT'}:[/b]",
            markup=True,
            size_hint_x=None,
            width=dp(30),
            halign='right',
            valign='middle',
            color=(0.2, 0.4, 0.8, 1) if sender == 'user' else (0.8, 0.2, 0.4, 1)
        )

        message_label = Label(
            font_context='JetBrainsMono',  # Contexto de renderização
            font_hinting='normal',  # Melhora a renderização
            text=text,
            font_name='JetBrainsMono',  # Fonte customizada
            size_hint_x=1,
            halign='left',
            valign='middle',
            text_size=(Window.width - dp(150), None),
            color=(0.1, 0.1, 0.1, 1),
            padding=(dp(5), dp(5)),
            font_size=sp(self.font_size)  # Tamanho dinâmico
        )

        message_box.add_widget(sender_label)
        message_box.add_widget(message_label)
        
        if sender == "assistant":
            copy_btn = Button(
                text='Copiar',
                size_hint_x=None,
                width=dp(60),
                background_color=(0, 0.7, 0, 0.7))
            copy_btn.bind(on_press=lambda x: self.copy_to_clipboard(text))
            message_box.add_widget(copy_btn)

        # Adiciona no início (mensagens mais novas no topo)
        self.chat_history.add_widget(message_box, index=0)

        # Configura o scroll
        def do_scroll(*args):
            if len(self.chat_history.children) > 0:
                target = self.chat_history.children[0]
                self.scroll_view.scroll_to_target(target)

        # Ajusta a altura da mensagem conforme o conteúdo
        message_label.bind(texture_size=self.update_message_height)
        
        Clock.schedule_once(do_scroll, 0.1)

    def update_message_height(self, instance, size):
        """Atualiza a altura da mensagem conforme o conteúdo"""
        # Encontra o BoxLayout pai (a mensagem)
        for child in self.chat_history.children:
            if instance in child.children:
                child.height = max(dp(40), size[1] + dp(5))
                break

    def clear_chat(self, instance):
        self.chat_history.clear_widgets()
        self.add_message("system", "Chat limpo. Você pode continuar fazendo perguntas.")

    def copy_to_clipboard(self, text):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(text)
        self.add_message("system", "Resposta copiada para a área de transferência!")

    def analyze_video(self, instance):
        self.load_btn.disabled = True
        self.load_btn.text = "Processando..."
        self.add_message("system", "Carregando vídeo...")

        Clock.schedule_once(lambda dt: self._analyze_video_async(), 0.1)

    def extract_video_id(self, url):
        """Extrai o ID do vídeo de qualquer formato de URL do YouTube"""
        patterns = [
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)',
            r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^?]+)',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([^?]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _analyze_video_async(self):
        video_url = self.url_input.text.strip()

        try:
            video_id = self.extract_video_id(video_url)
            if not video_id:
                self.add_message("system", "Formato de URL inválido!")
                self.add_message("system", "Exemplos válidos:\n• https://youtu.be/VIDEO_ID\n• https://www.youtube.com/watch?v=VIDEO_ID")
                return

            self.add_message("system", "Obtendo transcrição do vídeo...")
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en'])
            self.current_transcript = " ".join([t['text'] for t in transcript])

            self.add_message("system", "Gerando resumo automático...")
            summary = self._ask_groq("Veja os principais pontos dos vídeo, gere e mostre apenas perguntas essenciais para se fzr sobre o assunto do vídeo:")

            self.add_message("assistant", summary)
            self.video_loaded = True

        except Exception as e:
            self.add_message("system", f"Error: {str(e)}")
        finally:
            self.load_btn.disabled = False
            self.load_btn.text = "Carregar Vídeo"

    def send_question(self, instance):
        if not self.video_loaded:
            self.add_message("system", "Por favor, carregue um vídeo primeiro")
            return

        question = self.question_input.text.strip()
        if not question:
            return

        self.add_message("user", question)
        self.question_input.text = ""

        self.add_message("system", "Processando sua pergunta...")
        Clock.schedule_once(lambda dt: self._process_question_async(question), 0.1)

    def _process_question_async(self, question):
        try:
            answer = self._ask_groq(question)
            self.add_message("assistant", answer)
        except Exception as e:
            self.add_message("system", f"Erro ao processar pergunta: {str(e)}")

    def _ask_groq(self, prompt):
        headers = {"Authorization": "Bearer "}
        data = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": f"Você é um assistente muito profissional que sabe sobre qualquer e todo assunto, responda baseado neste vídeo: {self.current_transcript}"},
                {"role": "user", "content": prompt}
            ],
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=data,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        return response.json()['choices'][0]['message']['content']
    
    def on_stop(self):
        """Método chamado quando o app está fechando"""
        try:
            # Fecha o popup de configurações se estiver aberto
            if hasattr(self, '_settings_popup'):
                try:
                    self._settings_popup.dismiss()
                except:
                    pass
                self._settings_popup = None
            
            # Limpa manualmente os widgets principais
            if hasattr(self, 'main_layout'):
                for child in self.main_layout.children[:]:
                    try:
                        self.main_layout.remove_widget(child)
                    except:
                        pass
                self.main_layout = None
                
            # Salva configurações
            if hasattr(self, 'config'):
                try:
                    self.config.write()
                except:
                    pass
                
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            return super().on_stop()
        
    def safe_clear_widgets(self):
        """Limpa todos os widgets de forma segura"""
        widgets_to_clear = [
            'main_layout', 'chat_history', 'scroll_view',
            'question_input', 'load_btn', 'url_input'
        ]
        
        for attr in widgets_to_clear:
            if hasattr(self, attr):
                try:
                    widget = getattr(self, attr)
                    if widget and hasattr(widget, 'children'):
                        for child in widget.children[:]:
                            try:
                                widget.remove_widget(child)
                            except:
                                pass
                    setattr(self, attr, None)
                except:
                    pass

    def cleanup(self):
        """Limpeza explícita de recursos"""
        self.safe_clear_widgets()
        if hasattr(self, 'config'):
            try:
                self.config.write()
            except:
                pass


if __name__ == '__main__':
    VideoAnalyzerApp().run()