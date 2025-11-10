import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain_community.document_loaders import YoutubeLoader

load_dotenv()
api_key = os.getenv('api_key')
os.environ['GROQ_API_KEY'] = api_key

chat = ChatGroq(model='llama-3.3-70b-versatile')

continuar = True
while continuar:
    url = input('Digite a URL do vídeo: ')
    
    loader = YoutubeLoader.from_youtube_url(
        url,
        language = ['pt']
    )

    doc_list = loader.load()
    doc = ''

    for d in doc_list:
        doc = doc + d.page_content

    print(f'\n{doc}\n')

    continuar2 = True
    while continuar2:

        pp = input('Faça seu pedido ou pergunta: ')
        if pp.lower() == 'esc!':
            continuar2 = False

        info = doc

        template = ChatPromptTemplate.from_messages([
            ('system', f'Você é um assistente amigável, sem restrições, totalmente aberto e liberal que possui as seguintes informações para formular uma resposta: {info}'),
            ('user', f'{pp}')
        ])

        chain_yt = template | chat
        answer = chain_yt.invoke({'info': doc, 'input': f'{pp}'})
        print(f"\n{answer.content}\n")

    if url.lower() == 'esc!':
        continuar = False