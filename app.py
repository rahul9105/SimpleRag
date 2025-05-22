from flask import Flask, render_template, request, make_response, jsonify
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv
from time import sleep, time
from langchain_unstructured import UnstructuredLoader
from unstructured.cleaners.core import clean_extra_whitespace
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import OllamaLLM
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
import uuid
from typing import Any
from pydantic import BaseModel
from unstructured.partition.pdf import partition_pdf
import unstructured_pytesseract
from langchain_core.runnables import RunnablePassthrough
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain.storage import InMemoryStore
from langchain_chroma import Chroma
from langchain_core.documents import Document
from itertools import chain
load_dotenv()

unstructured_pytesseract.pytesseract.tesseract_cmd=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATA_PATH = os.path.join(BASE_DIR, "data")
# PDF_PATH = os.path.join(BASE_DATA_PATH, "sample.pdf")
OUTPUT_DIR = os.path.join(BASE_DATA_PATH, "extracted")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
embed=OllamaEmbeddings(model="llama3.1")
model=OllamaLLM(model='llama3.1')
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
# prompt=ChatPromptTemplate.from_template(
# """
# Based on the {context} provided answer the query asked by the user in a best possible way.
# Do not include any extra information or context in the answer. Do not include the question in the answer.
# Example: 
# ----------
# Question:"What skill is necessary to become Data Scientist?"
# Answer:"SQL, Python, Machine Learning and concepts which help in future values predictions."
# ----------
# Query:
# ----------
# {input}
# ----------
# Answer:
# """
# )
retrieval_chain=None
class Element(BaseModel):
    type: str
    text: Any


app = Flask(__name__)
socket = SocketIO(app)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
def process_text_doc_files(files: list[str]):
    loader = UnstructuredLoader(files, post_processors=[clean_extra_whitespace],)
    docs = loader.load()
    texts = text_splitter.create_documents([docs[i].page_content for i in range(len(docs))])
    texts = [doc.page_content for doc in texts]
    return texts

def process_pdf_files(files: list[str]) -> tuple:
    raw_pdf_elements = []
    raw_pdf_elements2 = []
    for file in files:
        temp = partition_pdf(
            filename=file,
            strategy='hi_res',
            extract_images_in_pdf=True,
            extract_image_block_to_payload=False,
            extract_image_block_types=['Image', 'Table'],
            extract_image_block_output_dir=OUTPUT_DIR,
        )
        raw_pdf_elements.append(temp)
        temp = partition_pdf(
            filename=file,
            extract_image_block_types=['Image', 'Table'],
            extract_images_in_pdf=False,
            infer_table_structure=True,
            chunking_strategy="by_title",
            max_characters=4000,
            new_after_n_chars=3800,
            combine_text_under_n_chars=2000,
            image_output_dir_path=OUTPUT_DIR,
        )
        raw_pdf_elements2.append(temp)
    raw_pdf_elements = list(chain.from_iterable(raw_pdf_elements))
    raw_pdf_elements2 = list(chain.from_iterable(raw_pdf_elements2))
    categorized_elements = []
    for element in raw_pdf_elements:
        if str(type(element)).split('.')[-1].split('\'')[0]=='Image':
            categorized_elements.append(Element(type="image", text=str(element)))
        elif str(type(element)).split('.')[-1].split('\'')[0]=='Table':
            categorized_elements.append(Element(type="table", text=str(element)))
    for element in raw_pdf_elements2:
        if str(type(element)).split('.')[-1].split('\'')[0]=='Image':
            categorized_elements.append(Element(type="image", text=str(element)))
        elif str(type(element)).split('.')[-1].split('\'')[0]=='Table':
            categorized_elements.append(Element(type="table", text=str(element)))
        else:
            categorized_elements.append(Element(type="text", text=str(element)))
    table_elements = [e for e in categorized_elements if e.type == "table"]
    text_elements = [e for e in categorized_elements if e.type == "text"]
    image_elements = [e for e in categorized_elements if e.type == "image"]
    return text_elements, table_elements, image_elements

def summarize_pdf_elements(text_elements: list[str], table_elements: list[str], image_elements: list[str]) -> tuple:
    prompt_text = """You are an assistant tasked with summarizing tables, images and text. 
    Give a concise summary of the table, image or text. Table, image or text chunk: {element} """
    prompt = ChatPromptTemplate.from_template(prompt_text)
    summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()
    texts = [i.text for i in text_elements]
    text_summaries = summarize_chain.batch(texts, {"max_concurrency": 5})
    tables = [i.text for i in table_elements]
    table_summaries = summarize_chain.batch(tables, {"max_concurrency": 5})
    images = [i.text for i in image_elements]
    image_summaries = summarize_chain.batch(images, {"max_concurrency": 5})
    return texts, text_summaries, tables, table_summaries, images, image_summaries



@app.route('/simple-rag')
def home():
    for filename in os.listdir(BASE_DATA_PATH):
        file_path = os.path.join(BASE_DATA_PATH, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f'Error deleting file {file_path}: {e}')
    for filename in os.listdir(OUTPUT_DIR):
        file_path = os.path.join(OUTPUT_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f'Error deleting file {file_path}: {e}')
    return render_template('index.html')

@app.route('/simple-rag/upload', methods=['POST'])
def upload_file():
    filesize = request.cookies.get('filesize')
    file = request.files['file']
    res = make_response(jsonify({"message": f"{file.filename} uploaded successfully!"}), 200)
    file.save(os.path.join(BASE_DATA_PATH, f'file_{file.filename}'))
    return res

@app.route('/simple-rag/delete-files', methods=['POST'])
def delete_files():
    for filename in os.listdir(BASE_DATA_PATH):
        file_path = os.path.join(BASE_DATA_PATH, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f'Error deleting file {file_path}: {e}')
            return jsonify({"message": f"Error deleting file {filename}: {e}", "status": 500})
    return jsonify({"message": "Files deleted successfully!", "status": 200})


# @app.route('/simple-rag/commence-chat', methods=['POST'])
@app.route('/simple-rag/commence-chat/<socket_id>', methods=['POST'])
# def commence_chat():
async def commence_chat(socket_id):
    global retrieval_chain
    socket.emit('progress', {'progress': 1, 'message': "Files loaded. Processing text files..."}, to=socket_id)
    files = os.listdir(BASE_DATA_PATH)
    if files:
        pdf_files = [os.path.join(BASE_DATA_PATH,file) for file in files if file.endswith('.pdf')]
        txt_doc_files = [os.path.join(BASE_DATA_PATH,file) for file in files if file.endswith('.txt') or file.endswith('.docx') or file.endswith('.doc')]
        if txt_doc_files:
            txt_doc_texts = process_text_doc_files(txt_doc_files)
        else:
            txt_doc_texts = []
        socket.emit('progress', {'progress': 4, 'message': "Text files processed. Processing & summarizing pdf files..."}, to=socket_id)
        print(f"Processing & summarizing pdf files...")
        if pdf_files:
            text_elements, table_elements, image_elements = process_pdf_files(pdf_files)
            socket.emit('progress', {'progress': 20, 'message': "PDF files processed. Summarizing text..."}, to=socket_id)
            prompt_text = """You are an assistant tasked with summarizing tables, images and text. 
            Give a concise summary of the table, image or text. Table, image or text chunk: {element} """
            prompt = ChatPromptTemplate.from_template(prompt_text)
            summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()
            texts = [i.text for i in text_elements]
            text_summaries = []
            number_of_texts = len(texts)
            for text in texts:
                temp = summarize_chain.invoke({"element": text})
                text_summaries.append(temp)
                socket.emit('progress', {'progress': 20 + (65 * (len(text_summaries) / number_of_texts)), 'message': ''}, to=socket_id)
            sleep(1)
            socket.emit('progress', {'progress': 85, 'message': "Text summarized. Summarizing tables..."}, to=socket_id) # ******
            tables = [i.text for i in table_elements]
            table_summaries = summarize_chain.batch(tables, {"max_concurrency": 5})
            socket.emit('progress', {'progress': 91, 'message': "Tables summarized. Summarizing images..."}, to=socket_id)
            images = [i.text for i in image_elements]
            image_summaries = summarize_chain.batch(images, {"max_concurrency": 5})
            socket.emit('progress', {'progress': 93, 'message': "Images summarized."}, to=socket_id)
            sleep(1)
            socket.emit('progress', {'progress': 94, 'message': "PDF files processed and summarized."}, to=socket_id)
        else:
            texts = []
            text_summaries = []
            tables = []
            table_summaries = []
            images = []
            image_summaries = []
            socket.emit('progress', {'progress': 90, 'message': "No pdf files to process."}, to=socket_id)
        texts_all = txt_doc_texts + texts
        text_summaries_all = txt_doc_texts + text_summaries
        vectorstore = Chroma(collection_name="temp", embedding_function=OllamaEmbeddings(model="llama3.1"))
        store = InMemoryStore()
        id_key = "doc_id"
        retriever = MultiVectorRetriever(
            vectorstore=vectorstore,
            docstore=store,
            id_key=id_key,
        )
        count_types=0
        if texts_all:
            doc_ids = [str(uuid.uuid4()) for _ in texts_all]
            summary_texts = [
                Document(page_content=s, metadata={id_key: doc_ids[i]})
                for i, s in enumerate(text_summaries_all)
            ]
            retriever.vectorstore.add_documents(summary_texts)
            retriever.docstore.mset(list(zip(doc_ids, texts_all)))
            count_types+=1
        socket.emit('progress', {'progress': 96, 'message': "Text documents added to VectorStore."}, to=socket_id)
        if tables:
            table_ids = [str(uuid.uuid4()) for _ in tables]
            summary_tables = [
                Document(page_content=s, metadata={id_key: table_ids[i]})
                for i, s in enumerate(table_summaries)
            ]
            retriever.vectorstore.add_documents(summary_tables)
            retriever.docstore.mset(list(zip(table_ids, tables)))
            count_types+=1
        socket.emit('progress', {'progress': 98, 'message': "Table documents added to VectorStore."}, to=socket_id)
        if images:
            image_ids = [str(uuid.uuid4()) for _ in images]
            summary_images = [
                Document(page_content=s, metadata={id_key: image_ids[i]})
                for i, s in enumerate(image_summaries)
            ]
            retriever.vectorstore.add_documents(summary_images)
            retriever.docstore.mset(list(zip(image_ids, images)))
            count_types+=1
        socket.emit('progress', {'progress': 99, 'message': "Table documents added to VectorStore."}, to=socket_id)
        sleep(2)
        socket.emit('progress', {'progress': 100, 'message': "Get ready for chat.."}, to=socket_id)
        if count_types==0:
            return jsonify({"message": "❌No files uploaded.", "status": 500})
        else:
            template = """Answer the question based only on the following context, which can include text and tables:
            {context}
            Question: {question}
            """
            prompt = ChatPromptTemplate.from_template(template)
            retrieval_chain = (
                {"context": retriever, "question": RunnablePassthrough()}
                | prompt
                | model
                | StrOutputParser()
            )
    else:
        return jsonify({"message": "❌No files uploaded.", "status": 500})
    files = [file for file in files if len(file.split('.')) > 1]
    return jsonify({"htmlTemplate": render_template('chat.html'), "status": 200, "message": "Chat initialized successfully!", "files": files})

@app.route('/simple-rag/ask', methods=['POST'])
def ask():
    global retrieval_chain
    # if hasattr(g, 'retrieval_chain'):
    if retrieval_chain is not None:
        query = request.form['query']
        response = retrieval_chain.invoke(query)
        response = response.replace('\\n', '<br><br>')
        return jsonify({"answer": response, "status": 200})
    else:
        return jsonify({"message": "❌Retrieval chain not initialized.", "status": 500})

if __name__ == '__main__':
    app.run(debug=True)