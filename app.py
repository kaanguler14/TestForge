
import streamlit as st
from graph import app
from dataclasses import asdict
from agents.context import TestContext

st.set_page_config(page_title="AutoTestLoop", page_icon="🤖", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #0E1117;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stRadio label span {
    color: #FFFFFF !important;
}
.stTextArea textarea {
    background-color: #0E1117 !important;
    color: #FFFFFF !important;
}
.stTextArea textarea::placeholder {
    color: #888888 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 AutoTestLoop")
st.caption("Self-healing multi-agent test system")

# --- Sidebar: Ayarlar ---
with st.sidebar:
    st.header("Settings")
    source_type = st.radio("Code type:", ["function", "api"])
    max_iter = st.slider("Max iterations:", 1, 5, 3)
    cov_threshold = st.slider("Coverage threshold (%):", 50, 100, 80)

    st.divider()
    st.subheader("Model Settings")
    writer_model = st.text_input("Writer model:", value="qwen2.5-coder:7b")
    analyzer_model = st.text_input("Analyzer model:", value="qwen3:8b")
    suggester_model = st.text_input("Suggester model:", value="qwen3:8b")

    st.divider()
    st.markdown(
        "**How it works:**\n"
        "1. Writer generates pytest tests\n"
        "2. Runner executes them in sandbox\n"
        "3. Analyzer reviews failures\n"
        "4. Loop retries until pass or max iter\n"
        "5. Suggester recommends source code improvements"
    )

# --- Örnek kodlar ---
examples = {
    "function": '''def process_order(items, discount_percent, tax_rate):
    subtotal = 0
    for item in items:
        subtotal += item['price'] * item['quantity']
    discount = subtotal * discount_percent / 100
    total = subtotal - discount
    tax = total * tax_rate / 100
    return total + tax''',
    "api": '''from flask import Flask, request, jsonify

app = Flask(__name__)

users = []

@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(users), 200

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "name is required"}), 400
    user = {"id": len(users) + 1, "name": data["name"]}
    users.append(user)
    return jsonify(user), 201

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    for user in users:
        if user["id"] == user_id:
            return jsonify(user), 200
    return jsonify({"error": "not found"}), 404''',
}

# --- Ana alan: Kod girişi ---
if "code_input" not in st.session_state:
    st.session_state.code_input = ""

if st.button("Load example code"):
    st.session_state.code_input = examples[source_type]

code = st.text_area(
    "Paste your Python code:",
    height=250,
    value=st.session_state.code_input,
    placeholder="Paste your code here or click 'Load example code' above...",
)

run_clicked = st.button("Run AutoTestLoop", type="primary", use_container_width=True)

# --- Çalıştırma ---
if run_clicked and code:
    initial_state = asdict(TestContext(
        source_code=code,
        source_type=source_type,
        max_iterations=max_iter,
        coverage_threshold=cov_threshold,
        writer_model=writer_model,
        analyzer_model=analyzer_model,
        suggester_model=suggester_model,
    ))

    status = st.status("Starting AutoTestLoop...", expanded=True)
    result_placeholder = st.empty()

    node_labels = {
        "writer": "✍️ Writing tests...",
        "runner": "🏃 Running tests...",
        "analyzer": "🔍 Analyzing results...",
        "suggester": "💡 Generating suggestions...",
    }

    final_state = initial_state

    with status:
        for event in app.stream(initial_state):
            node_name = list(event.keys())[0]
            final_state = event[node_name]
            st.write(node_labels.get(node_name, node_name))

            if node_name == "runner":
                with result_placeholder.container():
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Passed", final_state["passed"])
                    c2.metric("Failed", final_state["failed"])
                    c3.metric("Coverage", f"{final_state['coverage']}%")

        status.update(label="Done!", state="complete")

    # --- Sonuç banner'ı ---
    st.divider()
    if final_state["failed"] == 0:
        st.success(f"All {final_state['passed']} tests passed with {final_state['coverage']}% coverage.")
    elif final_state.get("failure_type") == "source_bug":
        st.warning(f"Tests found real bugs in your source code. {final_state['failed']} test(s) caught source code issues.")
    else:
        st.error(f"{final_state['failed']} test(s) failed after {final_state['iteration']} iteration(s).")

    # --- Metrikler ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Passed", final_state["passed"])
    col2.metric("Failed", final_state["failed"])
    col3.metric("Coverage", f"{final_state['coverage']}%")

    # --- Tab'lı sonuçlar ---
    tab_tests, tab_suggestions, tab_history, tab_output = st.tabs(["Generated Tests", "Suggestions", "Iteration History", "Raw Output"])

    with tab_tests:
        st.code(final_state["generated_tests"], language="python")

    with tab_suggestions:
        if final_state.get("suggestions"):
            st.text(final_state["suggestions"])
        else:
            st.info("No suggestions — code looks solid.")

    with tab_history:
        if final_state["history"]:
            for h in final_state["history"]:
                icon = "✅" if h["failed"] == 0 else "❌"
                st.info(
                    f"{icon} Iteration {h['iteration']}: "
                    f"{h['passed']} passed, {h['failed']} failed, "
                    f"coverage: {h.get('coverage', '?')}%"
                )
        else:
            st.info("No retries needed — tests passed on the first attempt.")

    with tab_output:
        if final_state["analysis"]:
            with st.expander("Last Analysis", expanded=True):
                st.text(final_state["analysis"])
        st.code(final_state["test_output"], language="text")

elif run_clicked and not code:
    st.warning("Please paste your code before running.")