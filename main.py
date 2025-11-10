import os
import threading
import sqlite3
from tkinter import *
from tkinter import scrolledtext, messagebox, ttk
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain_community.document_loaders import YoutubeLoader
from datetime import datetime

# Carregar chave da API
load_dotenv()
api_key = os.getenv('api_key')
os.environ['GROQ_API_KEY'] = api_key

# Inicializar modelo
chat = ChatGroq(model='llama-3.3-70b-versatile')

# Criar banco de dados
conn = sqlite3.connect("conversas.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS conversas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_url TEXT,
                mensagens TEXT,
                transcricao TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()
conn.close()

# Atualizar tabela para incluir a coluna 'transcricao', se necessário
conn = sqlite3.connect("conversas.db")
c = conn.cursor()
try:
    c.execute("ALTER TABLE conversas ADD COLUMN transcricao TEXT")
except sqlite3.OperationalError:
    # A coluna já existe, ignorar o erro
    pass
conn.commit()
conn.close()

# Criar janela principal
root = Tk()
root.title("YouTube ChatBot")
root.geometry("1280x780")
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill='both')

# Criar aba principal
frame_chat = Frame(notebook)
notebook.add(frame_chat, text="Nova Conversa")
chat_box = scrolledtext.ScrolledText(frame_chat, wrap=WORD, width=115, height=27, font=("JetBrains Mono", 11))
chat_box.pack(pady=10)
url_input = Entry(frame_chat, width=50, font=("JetBrains Mono", 11))
url_input.pack(pady=5)
user_input = Entry(frame_chat, width=50, font=("JetBrains Mono", 11))
user_input.pack(pady=5)

# Criar aba do histórico
frame_historico = Frame(notebook)
notebook.add(frame_historico, text="Histórico")
historico_listbox = Listbox(frame_historico, width=100, height=30)
historico_listbox.pack()

doc = ""
current_conversation_id = None

# Função para salvar conversa
def salvar_conversa(mensagem, transcricao=None):
    global current_conversation_id
    conn = sqlite3.connect("conversas.db")
    c = conn.cursor()
    if current_conversation_id is None:
        c.execute("INSERT INTO conversas (video_url, mensagens, transcricao) VALUES (?, ?, ?)", 
                  (url_input.get().strip(), mensagem, transcricao))
        current_conversation_id = c.lastrowid
    else:
        c.execute("UPDATE conversas SET mensagens = mensagens || ?, transcricao = ? WHERE id = ?", 
                  ('\n' + mensagem, transcricao, current_conversation_id))
    conn.commit()
    conn.close()

# Função para carregar histórico
def carregar_historico():
    historico_listbox.delete(0, END)
    conn = sqlite3.connect("conversas.db")
    c = conn.cursor()
    c.execute("SELECT id, video_url, timestamp FROM conversas")
    for row in c.fetchall():
        historico_listbox.insert(END, f"{row[0]} - {row[1]} ({row[2]})")
    conn.close()

# Função para carregar conversa selecionada
def carregar_conversa_selecionada(event):
    global current_conversation_id, doc
    try:
        # Obter o item selecionado no Listbox
        selecionado = historico_listbox.get(historico_listbox.curselection())
        conversa_id = int(selecionado.split(" - ")[0])  # Extrair o ID da conversa
        current_conversation_id = conversa_id

        # Carregar mensagens e transcrição do banco de dados
        conn = sqlite3.connect("conversas.db")
        c = conn.cursor()
        c.execute("SELECT mensagens, transcricao FROM conversas WHERE id = ?", (conversa_id,))
        resultado = c.fetchone()
        conn.close()

        # Atualizar chat_box e doc
        chat_box.delete(1.0, END)  # Limpar chat_box
        if resultado:
            mensagens, transcricao = resultado
            if mensagens:
                chat_box.insert(END, mensagens)  # Inserir mensagens carregadas
            if transcricao:
                doc = transcricao  # Atualizar a transcrição do vídeo
    except sqlite3.OperationalError as e:
        messagebox.showerror("Erro", f"Erro no banco de dados: {e}")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao carregar conversa: {e}")

# Vincular evento de clique no Listbox
historico_listbox.bind("<<ListboxSelect>>", carregar_conversa_selecionada)

# Função para carregar transcrição do vídeo
def process_video():
    global doc, current_conversation_id
    url = url_input.get().strip()
    if not url:
        messagebox.showerror("Erro", "Digite uma URL válida!")
        return
    chat_box.insert(END, f"\nProcessando vídeo: {url}...\n", "user")
    def fetch_transcription():
        global doc
        try:
            loader = YoutubeLoader.from_youtube_url(url, language=['pt'])
            doc_list = loader.load()
            doc = " ".join(d.page_content for d in doc_list)[:20000]
            chat_box.insert(END, f"\nTranscrição:\n{doc[:1000]}...\n", "bot")
            salvar_conversa(f"Transcrição carregada para: {url}", transcricao=doc)
            chat_box.yview(END)
        except Exception as e:
            chat_box.insert(END, f"\nErro ao carregar vídeo: {e}\n", "error")
            chat_box.yview(END)
    threading.Thread(target=fetch_transcription, daemon=True).start()

# Função para enviar pergunta
def send_message(event=None):
    global doc
    question = user_input.get().strip()
    if not doc:
        messagebox.showerror("Erro", "Você precisa carregar um vídeo primeiro!")
        return
    if not question:
        return
    chat_box.insert(END, f"\nVocê: {question}\n", "user")
    salvar_conversa(f"Você: {question}")
    def get_response():
        try:
            template = ChatPromptTemplate.from_messages([
                ('system', f'Você é um assistente amigável que dê sugestões de perguntas em todo final de texto que mais se encaixem no conteúdo do vídeo para que eu consiga extrair/estudar o máximo mesmo sem assistir o vídeo e que possui as seguintes informações para formular uma resposta: {doc}'),
                ('user', f'{question}')
            ])
            chain_yt = template | chat
            answer = chain_yt.invoke({'info': doc, 'input': question})
            chat_box.insert(END, f"\nMonkeyBot: {answer.content}\n", "bot")
            salvar_conversa(f"MonkeyBot: {answer.content}")
            chat_box.yview(END)
        except Exception as e:
            chat_box.insert(END, f"\nErro ao processar pergunta: {e}\n", "error")
    threading.Thread(target=get_response, daemon=True).start()
    user_input.delete(0, END)

# Botões
process_button = Button(frame_chat, text="Carregar Vídeo", font=("JetBrains Mono", 11, "bold"), command=process_video)
process_button.pack()
send_button = Button(frame_chat, text="Perguntar", font=("JetBrains Mono", 11, "bold"), command=send_message)
send_button.pack()
user_input.bind("<Return>", send_message)
root.bind("<Escape>", lambda event: root.destroy())
carregar_historico()
root.mainloop()
