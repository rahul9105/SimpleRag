from flask import Flask, render_template, request, make_response, jsonify
import os
from dotenv import load_dotenv
from time import sleep
from langchain_unstructured import UnstructuredLoader
from unstructured.cleaners.core import clean_extra_whitespace
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import OllamaLLM
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

FOLDER_PATH = os.path.join(os.path.dirname(__file__))+r'\data-pdf\temp'
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
embed=OllamaEmbeddings(model="llama3.1")
model=OllamaLLM(model='llama3.1')
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
prompt=ChatPromptTemplate.from_template(
"""
Based on the {context} provided answer the query asked by the user in a best possible way.
Do not include any extra information or context in the answer. Do not include the question in the answer.
Example: 
----------
Question:"What skill is necessary to become Data Scientist?"
Answer:"SQL, Python, Machine Learning and concepts which help in future values predictions."
----------
Query:
----------
{input}
----------
Answer:
"""
)
retrieval_chain=None
shared_data = None

app = Flask(__name__)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

@app.route('/simple-rag')
def home():
    for filename in os.listdir(FOLDER_PATH):
        file_path = os.path.join(FOLDER_PATH, filename)
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
    file.save(os.path.join(FOLDER_PATH, f'file_{file.filename}'))
    return res

@app.route('/simple-rag/delete-files', methods=['POST'])
def delete_files():
    for filename in os.listdir(FOLDER_PATH):
        file_path = os.path.join(FOLDER_PATH, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f'Error deleting file {file_path}: {e}')
            return jsonify({"message": f"Error deleting file {filename}: {e}", "status": 500})
    return jsonify({"message": "Files deleted successfully!", "status": 200})

@app.route('/simple-rag/commence-chat', methods=['POST'])
def commence_chat():
    global retrieval_chain
    files = os.listdir(FOLDER_PATH)
    if not files:
        return jsonify({"message": "No files found in the directory.", "status": 404})
    files = [os.path.join(FOLDER_PATH, file) for file in files]
    loader = UnstructuredLoader(files, post_processors=[clean_extra_whitespace],)
    docs = loader.load()
    texts = text_splitter.create_documents([docs[i].page_content for i in range(len(docs))])
    db = FAISS.from_documents(texts, embed)
    retriever = db.as_retriever()
    combine_docs_chain = create_stuff_documents_chain(model, prompt)
    retrieval_chain = create_retrieval_chain(retriever, combine_docs_chain)
    return jsonify({"htmlTemplate": render_template('chat.html'), "status": 200, "message": "Chat initialized successfully!", "files": files})

@app.route('/simple-rag/ask', methods=['POST'])
def ask():
    global retrieval_chain
    # if hasattr(g, 'retrieval_chain'):
    if retrieval_chain is not None:
        query = request.form['query']
        response = retrieval_chain.invoke({'input':query})
        answer = response['answer'].replace('\\n', '<br><br>')
        return jsonify({"answer": answer, "status": 200})
    else:
        return jsonify({"message": "❌Retrieval chain not initialized.", "status": 500})

if __name__ == '__main__':
    app.run(debug=True)