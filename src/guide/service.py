import json
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from fastapi import HTTPException
from .schemas import InputData

# Global variables
embeddings = None
vectorstores = {}
llm = None
prompt = None

async def initialize_service():
    global embeddings, vectorstores, llm, prompt

    # Load API keys
    load_dotenv()

    # Load medical dictionary
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    medical_dic_path = os.path.join(project_root, 'data', 'medical_dic.json')
    with open(medical_dic_path, 'r', encoding='utf-8') as f:
        medical_info = json.load(f)

    # Initialize embeddings
    embeddings = OpenAIEmbeddings()

    # Initialize vector stores
    for disease_name, disease_info in medical_info.items():
        doc = Document(page_content=disease_info)
        vs = FAISS.from_documents([doc], embeddings)
        vectorstores[disease_name] = vs

    # Initialize LLM
    llm = ChatOpenAI(model_name='gpt-4o-mini-2024-07-18', temperature=0)

    # Define the prompt template
    prompt_template_str = """\
당신은 의료 전문가입니다. 다음 정보를 기반으로 정확한 의료적 설명을 제공하세요. 답변은 의료 지식이 부족한 일반인도 이해할 수 있도록 쉽고 간단하게 작성하고, 부드러운 말투로 작성하세요.

질환명: {disease_name}
발열 여부: {fever_status}
출혈 여부: {blooding_status}
나이: {age}
증상: {symptoms}

컨텍스트에 제공된 정보를 사용하여 답변을 작성하세요. 컨텍스트에 존재하지 않는 정보를 제공하면 처벌받을 수 있습니다. 신중히 답변하세요.

컨텍스트:
{context}

답변양식:
선택한 사진을 기반으로 예측한 피부질환은 {disease_name}입니다. 아래의 정보는 예측한 진단명과, 입력하신 증상과 정보를 토대로 작성한 답변입니다.

1. 위험성

2. 전염성

3. 응급 처치 방법

4. 가정내 조치 방법

5. 병원 방문 필요의 긴급성

작성된 답변은 예측한 질환에 대해 서울아산병원의 건강정보를 참조하여 작성된 답변입니다. 답변 내용은 참고하시되, 가능한 병원을 방문해주세요.

답변 작성시 주의사항:
답변의 각 항목에는 * 등의 기호를 사용하지 마세요.
"""
    prompt = PromptTemplate(
        template=prompt_template_str,
        input_variables=["disease_name", "fever_status", "blooding_status", "age", "symptoms", "context"]
    )

def get_vectorstore(disease_name: str):
    vectorstore = vectorstores.get(disease_name)
    if vectorstore is None:
        raise HTTPException(status_code=404, detail="Disease not found")
    return vectorstore

async def generate_response(input_data: InputData):
    # Extract input data
    disease_name = input_data.disease_name
    fever_status = input_data.fever_status
    blooding_status = input_data.blooding_status
    age = input_data.age
    symptoms = input_data.symptoms

    # Get vector store for the disease
    vectorstore = get_vectorstore(disease_name)

    # Initialize retriever
    retriever = vectorstore.as_retriever()

    # Retrieve context documents based on symptoms
    query = symptoms
    context_docs = retriever.get_relevant_documents(query)
    context = "\n".join([doc.page_content for doc in context_docs])

    inputs = {
        "disease_name": disease_name,
        "fever_status": fever_status,
        "blooding_status": blooding_status,
        "age": age,
        "symptoms": symptoms,
        "context": context
    }

    # Chain the prompt with the LLM
    chain = prompt | llm

    # Generate response
    response = chain.invoke(inputs)

    return response