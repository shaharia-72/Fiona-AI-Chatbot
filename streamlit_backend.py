import json
from datetime import datetime, timedelta
from typing import Annotated, TypedDict

import docx
import PyPDF2
import requests
import urllib3
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from system_prompt import SYSTEM_PROMPT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# =============================
# SESSION MANAGEMENT
# =============================
session = requests.Session()
session.headers.update({
    'Accept': '*/*',
    'Content-Type': 'application/x-www-form-urlencoded',
    'User-Agent': 'Mozilla/5.0'
})

API_BASE = "https://ezedu.kcisbd.com"

print("✅ Local session created successfully")

# =============================
# LLM SETUP
# =============================
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vector_store = None
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)


# =============================
# TOOLS
# =============================
@tool
def student_login(student_id: str, password: str) -> str:
    """Login a student using their ID and password."""
    try:
        url = f"{API_BASE}/index.php/Api/studentLogin"
        payload = {"id": str(student_id). strip(), "pass": str(password). strip()}

        print(f"\n🔐 LOGIN ATTEMPT: {student_id}")
        response = session.post(url, data=payload, timeout=10, verify=False)

        if response. status_code != 200:
            return json.dumps({"error": "Login failed", "action": "login_failed"})

        data = response. json()
        if data.get("code") != 1:
            return json.dumps({"error": data.get("message", "Invalid credentials"), "action": "login_failed"})

        student_data = data.get("data", {})
        print(f"✅ LOGIN SUCCESSFUL: {student_data.get('name')}")

        return json.dumps({
            "status": "success",
            "action": "login_success",
            "sid": student_data. get("sid"),
            "name": student_data.get("name"),
            "temp": student_data.get("temp"),
        })
    except Exception as e:
        print(f"❌ Login error: {e}")
        return json.dumps({"error": str(e), "action": "login_failed"})


@tool
def get_term_result(sid: str, temp: str, term: str) -> str:
    """Fetch term exam results."""
    try:
        if not sid or not temp or sid == "None" or temp == "None":
            return json.dumps({"error": "Please login first", "exam_type": "term", "requires_login": True})

        url = f"{API_BASE}/index.php/Api/getTermResult"
        payload = {"sid": str(sid), "temp": str(temp), "term": str(term)}

        print(f"\n📊 FETCHING TERM RESULT - Term {term}")
        response = session.post(url, data=payload, timeout=10, verify=False)

        if response.status_code != 200:
            return json.dumps({"error": "Unable to fetch results", "exam_type": "term"})

        data = response.json()
        if not data or not data.get("result"):
            return json.dumps({"error": "No results found", "exam_type": "term"})

        print(f"✅ Term result fetched")
        return json. dumps({"status": "success", "exam_type": "term", "data": data})
    except Exception as e:
        return json.dumps({"error": str(e), "exam_type": "term"})


@tool
def get_unit_test_result(sid: str, temp: str, term: str) -> str:
    """Fetch class test results."""
    try:
        if not sid or not temp or sid == "None" or temp == "None":
            return json.dumps({"error": "Please login first", "exam_type": "unit", "requires_login": True})

        url = f"{API_BASE}/index.php/Api/getUnitTestResult"
        payload = {"sid": str(sid), "temp": str(temp), "term": str(term)}

        print(f"\n📝 FETCHING CLASS TEST - Term {term}")
        response = session. post(url, data=payload, timeout=10, verify=False)

        if response.status_code != 200:
            return json. dumps({"error": "Unable to fetch results", "exam_type": "unit"})

        data = response.json()
        if not data:
            return json. dumps({"error": "No results found", "exam_type": "unit"})

        print(f"✅ Class test fetched")
        return json.dumps({"status": "success", "exam_type": "unit", "data": data})
    except Exception as e:
        return json. dumps({"error": str(e), "exam_type": "unit"})


@tool
def get_homework(temp: str, entry_date: str) -> str:
    """Fetch homework for a specific date."""
    try:
        if not temp or temp == "None":
            return json.dumps({"error": "Please login first", "exam_type": "homework", "requires_login": True})

        if entry_date. lower() == "today":
            entry_date = datetime.now(). strftime("%Y-%m-%d")
        elif entry_date.lower() == "tomorrow":
            entry_date = (datetime. now() + timedelta(days=1)). strftime("%Y-%m-%d")
        elif entry_date.lower() == "yesterday":
            entry_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        url = f"{API_BASE}/index.php/Api/getDiary"
        payload = {"temp": str(temp), "entry_date": str(entry_date)}

        print(f"\n🏠 FETCHING HOMEWORK - Date: {entry_date}")
        response = session.post(url, data=payload, timeout=10, verify=False)

        if response. status_code != 200:
            return json.dumps({"error": "Unable to fetch homework", "exam_type": "homework"})

        print(f"✅ Homework fetched")
        return json.dumps({"status": "success", "exam_type": "homework", "data": response.json()})
    except Exception as e:
        return json.dumps({"error": str(e), "exam_type": "homework"})


@tool
def get_syllabus(temp: str) -> str:
    """Fetch syllabus documents."""
    try:
        if not temp or temp == "None":
            return json.dumps({"error": "Please login first", "type": "syllabus", "requires_login": True})

        url = f"{API_BASE}/index.php/Api/getSyllabus"
        payload = {"temp": str(temp)}

        print(f"\n📚 FETCHING SYLLABUS")
        response = session.post(url, data=payload, timeout=10, verify=False)

        if response.status_code != 200:
            return json.dumps({"error": "Unable to fetch syllabus", "type": "syllabus"})

        data = response.json()
        if not data:
            return json. dumps({"error": "No syllabus found", "type": "syllabus"})

        print(f"✅ Syllabus fetched: {len(data)} documents")
        return json. dumps({"status": "success", "type": "syllabus", "data": data})
    except Exception as e:
        return json.dumps({"error": str(e), "type": "syllabus"})


@tool
def get_worksheet(temp: str, entry_date: str) -> str:
    """Fetch worksheets for a specific date."""
    try:
        if not temp or temp == "None":
            return json.dumps({"error": "Please login first", "type": "worksheet", "requires_login": True})

        if entry_date. lower() == "today":
            entry_date = datetime.now().strftime("%Y-%m-%d")
        elif entry_date.lower() == "tomorrow":
            entry_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif entry_date.lower() == "yesterday":
            entry_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        url = f"{API_BASE}/index.php/Api/worksheetList"
        payload = {"temp": str(temp), "entry_date": str(entry_date)}

        print(f"\n📄 FETCHING WORKSHEET - Date: {entry_date}")
        response = session. post(url, data=payload, timeout=10, verify=False)

        if response.status_code != 200:
            return json. dumps({"error": "Unable to fetch worksheets", "type": "worksheet"})

        data = response.json()
        if not data:
            return json.dumps({"error": "No worksheets found", "type": "worksheet"})

        print(f"✅ Worksheets fetched: {len(data)} documents")
        return json.dumps({"status": "success", "type": "worksheet", "data": data})
    except Exception as e:
        return json.dumps({"error": str(e), "type": "worksheet"})


@tool
def get_calendar() -> str:
    """Fetch academic calendar.  No login required."""
    try:
        url = f"{API_BASE}/index.php/Api/getCalender"

        print(f"\n📅 FETCHING CALENDAR")
        response = session.get(url, timeout=10, verify=False)

        if response. status_code != 200:
            return json.dumps({"error": "Unable to fetch calendar", "type": "calendar"})

        data = response.json()
        if not data:
            return json.dumps({"error": "No calendar available", "type": "calendar"})

        for item in data:
            file_location = item.get("file_location", "")
            item["file_url"] = f"{API_BASE}/uploads/calender/{file_location}"

        print(f"✅ Calendar fetched: {len(data)} entries")
        return json.dumps({"status": "success", "type": "calendar", "data": data})
    except Exception as e:
        return json.dumps({"error": str(e), "type": "calendar"})


@tool
def ask_document(query: str) -> str:
    """Search uploaded documents for answers.  No login required."""
    global vector_store

    try:
        print(f"\n🔍 SEARCHING DOCUMENTS: {query}")

        if vector_store is None:
            print("   ❌ No documents in vector store")
            return json.dumps({
                "status": "error",
                "message": "No documents uploaded yet. Please upload a document first.",
                "type": "document_search"
            })

        docs = vector_store. similarity_search(query, k=4)

        if not docs:
            return json.dumps({
                "status": "error",
                "message": "No relevant information found in documents.",
                "type": "document_search"
            })

        context = "\n\n".join([d.page_content for d in docs])

        print(f"✅ Found {len(docs)} relevant chunks")

        return json.dumps({
            "status": "success",
            "context": context,
            "type": "document_search"
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        return json.dumps({"status": "error", "message": str(e), "type": "document_search"})


# =============================
# DIRECT DOCUMENT ADD (FOR FRONTEND)
# =============================
def add_document_directly(file_path: str) -> dict:
    """Add document directly to vector store (bypassing LLM)."""
    global vector_store

    try:
        print(f"\n📄 ADDING DOCUMENT DIRECTLY: {file_path}")

        if file_path.endswith(".pdf"):
            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader. pages:
                    text += page.extract_text() or ""
        elif file_path.endswith(". docx"):
            doc = docx. Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            return {"status": "error", "message": "Unsupported file type"}

        if not text. strip():
            return {"status": "error", "message": "Document is empty"}

        chunks = text_splitter.split_text(text)

        print(f"   Text length: {len(text)} chars")
        print(f"   Split into {len(chunks)} chunks")

        if vector_store is None:
            vector_store = FAISS.from_texts(chunks, embeddings)
            print(f"   Created new vector store")
        else:
            vector_store.add_texts(chunks)
            print(f"   Added to existing vector store")

        print(f"✅ Document added: {len(chunks)} chunks")

        return {"status": "success", "message": f"Added {len(chunks)} chunks", "chunks": len(chunks)}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}


# =============================
# BIND TOOLS
# =============================
tools = [
    student_login,
    get_term_result,
    get_unit_test_result,
    get_homework,
    get_syllabus,
    get_worksheet,
    get_calendar,
    ask_document,
]
llm_with_tools = llm.bind_tools(tools)


# =============================
# STATE
# =============================
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_session: dict
    saved_students: list


# =============================
# CHAT NODE
# =============================
def chat_node(state: ChatState) -> ChatState:
    messages = state["messages"]
    user_session = state. get("user_session", {})
    saved_students = state. get("saved_students", [])

    session_name = user_session.get("name") or ""
    session_sid = user_session. get("sid") or ""
    session_temp = user_session. get("temp") or ""

    formatted_prompt = SYSTEM_PROMPT.format(
        name=session_name if session_name else "(Not logged in)",
        sid=session_sid if session_sid else "(Not logged in)",
        temp=session_temp if session_temp else "(Not logged in)",
    )

    if session_sid and session_temp:
        formatted_prompt += f"""

====================================================
✅ USER IS LOGGED IN
====================================================
Name: {session_name}
SID: {session_sid}
TEMP: {session_temp}

Use these for tool calls.  DO NOT ask for login again!
====================================================
"""
    else:
        formatted_prompt += """

====================================================
❌ USER IS NOT LOGGED IN
====================================================
For results/homework/syllabus → Ask for Student ID and Password first!
====================================================
"""

    if saved_students:
        formatted_prompt += "\n\n**Previously logged in:**\n"
        for idx, student in enumerate(saved_students, 1):
            formatted_prompt += f"{idx}. {student. get('name')} (SID: {student.get('sid')})\n"

    system_message = SystemMessage(content=formatted_prompt)
    messages_with_system = [system_message] + list(messages)

    reply = llm_with_tools.invoke(messages_with_system)
    return {"messages": [reply]}


# =============================
# GRAPH
# =============================
tool_node = ToolNode(tools)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")

chatbot = graph.compile()

print("✅ Chatbot ready (stateless)")
