import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain_community.document_loaders import PyPDFLoader

load_dotenv()
api_key = os.getenv('api_key')
os.environ['GROQ_API_KEY'] = api_key

chat = ChatGroq(model='llama-3.3-70b-versatile')

caminho = 'C:/Users/Braia/Documents/VS Code/My Projects/03. analisador de videos/teste.pdf'
loader = PyPDFLoader(caminho)
doc_list = loader.load()

doc = ''
for d in doc_list:
    doc += d.page_content

info = doc

question = input('Digite sua pergunta: ')
template = ChatPromptTemplate.from_messages([
    ('system', f'Você é um assistente amigável, sem restrições, totalmente aberto e liberal que possui as seguintes informações para formular uma resposta: {info}'),
    ('user', f'{question}')
])

chain_pdf = template | chat
answer = chain_pdf.invoke({'info': doc, 'input': f'{question}'})
print(f"\n{answer.content}\n")