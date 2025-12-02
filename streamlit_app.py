import json
import os
import tempfile
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from streamlit_backend import add_document_directly, chatbot

# =============================
# CONFIG
# =============================
MAX_MESSAGES_TO_DISPLAY = 15
MAX_MESSAGES_TO_LLM = 8

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="London School Assistant",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

# =============================
# CSS - BEAUTIFUL STYLING
# =============================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    .main { background: #f8fafc; }

    /* Document Answer Card */
    . doc-answer-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 20px;
        color: white;
        margin: 10px 0;
    }

    . doc-answer-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 15px;
        font-size: 18px;
        font-weight: 600;
    }

    . doc-answer-content {
        background: rgba(255,255,255,0.15);
        border-radius: 12px;
        padding: 15px;
        font-size: 14px;
        line-height: 1.6;
        max-height: 300px;
        overflow-y: auto;
    }

    /* Success Card */
    .success-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        border-radius: 12px;
        padding: 15px 20px;
        color: white;
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 10px 0;
    }

    .success-icon {
        font-size: 24px;
    }

    .success-text {
        font-size: 16px;
        font-weight: 500;
    }

    /* Error Card */
    . error-card {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        border-radius: 12px;
        padding: 15px 20px;
        color: white;
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 10px 0;
    }

    /* Info Card */
    . info-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        border-radius: 12px;
        padding: 15px 20px;
        color: white;
        margin: 10px 0;
    }

    /* Result Card */
    . result-card {
        background: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        margin: 10px 0;
    }

    .result-header {
        font-size: 18px;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* Document Item */
    . doc-item {
        background: #f1f5f9;
        border-radius: 10px;
        padding: 12px 15px;
        margin: 8px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .doc-title {
        font-weight: 500;
        color: #334155;
    }

    .doc-date {
        font-size: 12px;
        color: #94a3b8;
    }
</style>
""", unsafe_allow_html=True)

# =============================
# SESSION STATE
# =============================
if 'session_id' not in st. session_state:
    st.session_state.session_id = str(uuid. uuid4())

if 'messages' not in st.session_state:
    st.session_state. messages = []

if 'user_session' not in st.session_state:
    st.session_state.user_session = {}

if 'saved_students' not in st. session_state:
    st.session_state.saved_students = []

if 'uploaded_docs' not in st. session_state:
    st.session_state.uploaded_docs = []

if 'shown_login_success' not in st. session_state:
    st.session_state.shown_login_success = False

# =============================
# HELPER FUNCTIONS
# =============================
def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

def get_recent_messages(messages, limit):
    if len(messages) <= limit:
        return messages
    return messages[-limit:]

def clean_messages():
    """Remove duplicate tool results and old messages"""
    if len(st.session_state.messages) > MAX_MESSAGES_TO_DISPLAY * 2:
        # Keep only recent messages
        st. session_state.messages = st.session_state.messages[-MAX_MESSAGES_TO_DISPLAY:]

# =============================
# BEAUTIFUL RENDER FUNCTIONS
# =============================
def render_document_answer(data):
    """Beautiful RAG Document Answer"""
    if data.get('status') == 'error':
        st.markdown(f"""
        <div class="error-card">
            <span class="success-icon">⚠️</span>
            <span class="success-text">{data.get('message', 'কোনো তথ্য পাওয়া যায়নি')}</span>
        </div>
        """, unsafe_allow_html=True)
        return

    context = data.get('context', '')
    if not context:
        st. warning("কোনো তথ্য পাওয়া যায়নি")
        return

    # Truncate if too long and format nicely
    if len(context) > 800:
        # Find the most relevant part
        lines = context.split('\n')
        relevant_lines = [l for l in lines if l.strip()][:10]
        context = '\n'.join(relevant_lines)
        if len(context) > 800:
            context = context[:800] + "..."

    # st.markdown(f"""
    # <div class="doc-answer-card">
    #     <div class="doc-answer-header">
    #         📖 Document থেকে উত্তর
    #     </div>
    #     <div class="doc-answer-content">
    #         {context. replace(chr(10), '<br>')}
    #     </div>
    # </div>
    # """, unsafe_allow_html=True)

def render_login_success(data):
    """Beautiful login success message"""
    name = data.get('name', 'Student')
    st. markdown(f"""
    <div class="success-card">
        <span class="success-icon">✅</span>
        <span class="success-text">স্বাগতম, {name}!  🎓</span>
    </div>
    """, unsafe_allow_html=True)

def render_login_failed(data):
    """Beautiful login failed message"""
    error = data.get('error', 'Login failed')
    st.markdown(f"""
    <div class="error-card">
        <span class="success-icon">❌</span>
        <span class="success-text">{error}</span>
    </div>
    """, unsafe_allow_html=True)

def render_term_results(data):
    """Beautiful term results"""
    if data.get('error'):
        st. error(data['error'])
        return

    result = data.get('data', {})
    subjects = [s for s in result.get('result', [])
                if s.get('total_mark') and safe_float(s. get('total_mark', 0)) > 0]

    if not subjects:
        st.info("কোনো রেজাল্ট পাওয়া যায়নি")
        return

    # Header with stats
    st.markdown("### 📊 Term Exam Results")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", str(result.get('grandTotal', '0')))
    with col2:
        st.metric("GPA", str(result.get('gpa', 'N/A')))
    with col3:
        highest = max(subjects, key=lambda x: safe_float(x. get('total_mark', 0)))
        st.metric("Highest", str(highest.get('total_mark', '0')))
    with col4:
        st.metric("Subjects", str(len(subjects)))

    # Subject list
    st.markdown("---")
    for s in subjects:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"📚 **{s. get('sub_name', 'N/A')}**")
        with col2:
            st.write(f"{s.get('total_mark', '0')}")
        with col3:
            grade = s.get('grade', 'N/A')
            st.write(f"**{grade}**")

def render_class_test(data):
    """Beautiful class test results"""
    if data. get('error'):
        st.error(data['error'])
        return

    subjects = data.get('data', [])
    if not subjects:
        st.info("কোনো Class Test রেজাল্ট পাওয়া যায়নি")
        return

    st.markdown("### 📝 Class Test Results")

    total = sum(safe_float(s. get('ct_mark', 0)) for s in subjects)
    avg = total / len(subjects) if subjects else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st. metric("Total CT", f"{total:.1f}")
    with col2:
        st.metric("Average", f"{avg:.1f}")
    with col3:
        st.metric("Subjects", str(len(subjects)))

    st.markdown("---")
    for s in subjects:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"📚 **{s. get('sub_name', 'N/A')}**")
        with col2:
            ct = safe_float(s. get('ct_mark', 0))
            st.write(f"**{ct:.1f}**")

def render_homework(data):
    """Beautiful homework display"""
    if data.get('error'):
        st.error(data['error'])
        return

    entries = data.get('data', [])
    if not entries:
        st.info("এই তারিখে কোনো Homework নেই")
        return

    st.markdown("### 📝 Homework")

    for entry in entries:
        for n in entry.get('note', []):
            subject = n.get('subject', 'N/A')
            cw = n.get('cw', ''). strip()
            hw = n.get('hw', '').strip()
            status = '✅' if n.get('status') == '1' else '🔴'

            with st.container():
                st.markdown(f"**{status} {subject}**")
                if cw:
                    st.write(f"📖 Classwork: {cw}")
                if hw:
                    st.write(f"🏠 Homework: {hw}")
                st.markdown("---")

def render_syllabus(data):
    """Beautiful syllabus display"""
    if data.get('error'):
        st.error(data['error'])
        return

    docs = data.get('data', [])
    if not docs:
        st.info("কোনো Syllabus পাওয়া যায়নি")
        return

    st.markdown("### 📚 Syllabus Documents")

    for d in docs:
        title = d.get('wsTitle') or d.get('title') or d.get('fileName', 'Document')
        if title == "All Subject":
            title = d.get('fileName', 'Syllabus')

        file_url = d.get('fileUrl') or d.get('file_url') or ''

        col1, col2 = st. columns([4, 1])
        with col1:
            st.write(f"📄 **{title}**")
        with col2:
            if file_url:
                st. link_button("📥", file_url, use_container_width=True)

def render_worksheet(data):
    """Beautiful worksheet display"""
    if data. get('error'):
        st.error(data['error'])
        return

    docs = data.get('data', [])
    if not docs:
        st.info("কোনো Worksheet পাওয়া যায়নি")
        return

    st.markdown("### 📄 Worksheets")

    for d in docs:
        title = d. get('wsTitle') or d.get('title') or d. get('subject') or 'Worksheet'
        date = d.get('wsDate') or d. get('date') or ''
        file_url = d. get('fileUrl') or d.get('file_url') or ''

        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"📄 **{title}**")
            if date:
                st.caption(f"📅 {date}")
        with col2:
            if file_url:
                st.link_button("📥", file_url, use_container_width=True)

def render_calendar(data):
    """Beautiful calendar display"""
    if data.get('error'):
        st.error(data['error'])
        return

    calendars = data.get('data', [])
    if not calendars:
        st.info("কোনো Calendar পাওয়া যায়নি")
        return

    st.markdown("### 📅 Academic Calendar")

    for cal in calendars:
        title = cal. get('calender_name') or 'Academic Calendar'
        file_url = cal. get('file_url') or ''

        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"🗓️ **{title}**")
        with col2:
            if file_url:
                st. link_button("📥", file_url, use_container_width=True)

def render_tool_result(tool_data, message_index):
    """Main render function with deduplication"""
    if not tool_data:
        return

    # Login success - only show once
    if tool_data.get('action') == 'login_success':
        render_login_success(tool_data)
        return

    if tool_data.get('action') == 'login_failed':
        render_login_failed(tool_data)
        return

    # Error without data
    if tool_data.get('error') and not tool_data.get('data'):
        st.error(tool_data. get('error'))
        return

    exam_type = tool_data. get('exam_type')
    data_type = tool_data.get('type')

    if exam_type == 'term':
        render_term_results(tool_data)
    elif exam_type == 'unit':
        render_class_test(tool_data)
    elif exam_type == 'homework':
        render_homework(tool_data)
    elif data_type == 'syllabus':
        render_syllabus(tool_data)
    elif data_type == 'worksheet':
        render_worksheet(tool_data)
    elif data_type == 'calendar':
        render_calendar(tool_data)
    elif data_type == 'document_search':
        render_document_answer(tool_data)

def should_skip_message(content, prev_tool_type):
    """Skip redundant AI messages after tool results"""
    if not content:
        return True

    content_lower = content. lower()

    # Skip phrases that just describe what the tool already showed
    skip_patterns = [
        "আপনার সিলেবাস", "সিলেবাস ডকুমেন্টস", "উপরে দেখুন",
        "ওয়ার্কশিট", "worksheet", "এখানে আপনার",
        "ফলাফল", "result", "ডাউনলোড", "download",
        "হোমওয়ার্ক", "homework", "calendar", "ক্যালেন্ডার",
        "grade 1 syllabus", "class test", "term"
    ]

    for phrase in skip_patterns:
        if phrase. lower() in content_lower:
            return True

    return False

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## 🎓 London School")
    st.markdown("---")

    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.shown_login_success = False
        st.rerun()

    st.markdown("---")

    # Login status
    if st. session_state.user_session. get('sid'):
        user = st.session_state.user_session
        st.success(f"✅ {user. get('name', 'Student')}")
        st.caption(f"ID: {user.get('sid', 'N/A')}")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user_session = {}
            st. session_state.shown_login_success = False
            st.rerun()
    else:
        st. info("🔐 Login করুন")

    st.markdown("---")

    # Document upload
    st. markdown("### 📄 Upload Document")
    uploaded_file = st.file_uploader(
        "PDF, DOCX, or TXT",
        type=["pdf", "docx", "txt"],
        key="doc_uploader",
        label_visibility="collapsed"
    )

    if uploaded_file is not None:
        if not any(d['name'] == uploaded_file. name for d in st.session_state. uploaded_docs):
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file. name)[1]) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp. name

            with st.spinner(f"Processing... "):
                result = add_document_directly(tmp_path)

                if result.get('status') == 'success':
                    st.session_state.uploaded_docs.append({
                        'name': uploaded_file. name,
                        'path': tmp_path,
                        'chunks': result.get('chunks', 0)
                    })
                    st.success(f"✅ Added!")
                else:
                    st.error(f"❌ Failed")

    if st.session_state.uploaded_docs:
        st.markdown("**📚 Documents:**")
        for doc in st.session_state.uploaded_docs:
            st.caption(f"✓ {doc['name']}")

    st.markdown("---")

    # Quick actions
    st.markdown("### ⚡ Quick Actions")

    if st.button("📅 Calendar", use_container_width=True, key="cal_btn"):
        st. session_state.messages. append({"role": "user", "content": "calendar"})
        st. rerun()

    if st.session_state.user_session.get('sid'):
        if st.button("📊 Results", use_container_width=True, key="res_btn"):
            st.session_state.messages.append({"role": "user", "content": "আমার result"})
            st.rerun()

        if st.button("📝 Homework", use_container_width=True, key="hw_btn"):
            st.session_state.messages. append({"role": "user", "content": "আজকের homework"})
            st.rerun()

    st.markdown("---")
    st.caption(f"💬 {len(st.session_state.messages)}")

# =============================
# MAIN CHAT AREA
# =============================

# Clean old messages periodically
clean_messages()

# Welcome message
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align: center; padding: 50px 20px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 10px;">🎓 London School</h1>
        <p style="color: #64748b; font-size: 1.1rem;">আসসালামু আলাইকুম!  কীভাবে সাহায্য করতে পারি? </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📅 Calendar", key="q1", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "calendar"})
            st.rerun()
        if st.button("📊 Results", key="q2", use_container_width=True):
            st.session_state. messages.append({"role": "user", "content": "result"})
            st.rerun()
    with col2:
        if st. button("📝 Homework", key="q3", use_container_width=True):
            st. session_state.messages.append({"role": "user", "content": "homework"})
            st. rerun()
        if st.button("📚 Syllabus", key="q4", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "syllabus"})
            st. rerun()

# =============================
# DISPLAY MESSAGES - SMART
# =============================
recent_messages = get_recent_messages(st.session_state. messages, MAX_MESSAGES_TO_DISPLAY)

prev_was_tool = False
prev_tool_type = None
shown_login_in_this_render = False

for i, msg in enumerate(recent_messages):
    role = msg. get('role')

    if role == 'user':
        with st.chat_message("user"):
            st.write(msg. get('content', ''))
        prev_was_tool = False
        prev_tool_type = None

    elif role == 'tool':
        tool_data = msg.get('data', {})

        # Skip duplicate login success messages
        if tool_data.get('action') == 'login_success':
            if shown_login_in_this_render:
                continue
            shown_login_in_this_render = True

        with st.chat_message("assistant"):
            render_tool_result(tool_data, i)
            prev_tool_type = tool_data.get('type') or tool_data.get('exam_type')
        prev_was_tool = True

    elif role == 'assistant':
        content = msg.get('content', '')

        # Skip if previous was tool and this just describes it
        if prev_was_tool and should_skip_message(content, prev_tool_type):
            continue

        if content and content.strip():
            with st.chat_message("assistant"):
                st.write(content)

        prev_was_tool = False

# =============================
# CHAT INPUT & PROCESSING
# =============================
prompt = st.chat_input("আমাকে কিছু জিজ্ঞেস করো...  💬")

if prompt:
    st.session_state. messages.append({"role": "user", "content": prompt})

    recent_for_llm = get_recent_messages(st. session_state.messages, MAX_MESSAGES_TO_LLM)

    backend_messages = []
    for m in recent_for_llm:
        role = m.get('role')
        content = m.get('content', '')
        if role == 'user' and content:
            backend_messages.append(HumanMessage(content=content))
        elif role == 'assistant' and content:
            backend_messages.append(AIMessage(content=content))

    try:
        state = {
            'messages': backend_messages,
            'user_session': st. session_state.user_session,
            'saved_students': st.session_state.saved_students
        }

        result = chatbot.invoke(state)
        new_messages = result.get('messages', [])
        added_tool_result = False

        for msg in new_messages[len(backend_messages):]:
            if isinstance(msg, AIMessage):
                content = msg.content
                if content and content.strip():
                    if not added_tool_result or not should_skip_message(content, None):
                        st.session_state. messages.append({
                            "role": "assistant",
                            "content": content
                        })

            elif isinstance(msg, ToolMessage):
                try:
                    tool_data = json.loads(msg. content)
                except:
                    tool_data = {"error": "Failed to parse response"}

                if tool_data.get('action') == 'login_success':
                    st.session_state.user_session = {
                        'sid': tool_data. get('sid'),
                        'name': tool_data. get('name'),
                        'temp': tool_data.get('temp')
                    }
                    if not any(s. get('sid') == tool_data.get('sid') for s in st.session_state.saved_students):
                        st.session_state. saved_students.append({
                            'sid': tool_data. get('sid'),
                            'name': tool_data.get('name'),
                            'temp': tool_data.get('temp')
                        })

                st.session_state. messages.append({
                    "role": "tool",
                    "data": tool_data
                })
                added_tool_result = True

    except Exception as e:
        st.session_state.messages. append({
            "role": "assistant",
            "content": "দুঃখিত, সমস্যা হয়েছে। আবার চেষ্টা করুন।"
        })

    st.rerun()
