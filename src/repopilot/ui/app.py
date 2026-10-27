import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("REPOPILOT_API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="RepoPilot", page_icon="🧭", layout="wide")
st.markdown("""<style>.block-container{max-width:1100px;padding-top:2rem}h1{letter-spacing:-.04em}.stButton button{border-radius:10px}</style>""",unsafe_allow_html=True)
st.title("🧭 RepoPilot")
st.caption("Ask your repository a question. See the source lines behind every answer.")
with st.sidebar:
    st.header("Repository")
    st.caption(f"LLM provider: {os.getenv('REPOPILOT_PROVIDER', 'groq')}")
    root = st.text_input("Local path",placeholder="C:/Projects/my-repo")
    if st.button("Index repository",use_container_width=True) and root:
        try:
            r = requests.post(f"{API}/repositories/index",json={"repo_path":root},timeout=30)
            r.raise_for_status()
            st.session_state.rid = r.json()["repository_id"]
            st.session_state.pop("result",None)
            st.success("Indexing started")
        except requests.RequestException as exc: st.error(str(exc))
    rid = st.text_input("Repository ID",value=st.session_state.get("rid",""))
    if rid:
        try:
            r = requests.get(f"{API}/repositories/{rid}/status",timeout=10)
            if r.ok: st.info(f"Status: {r.json()['status']} · {r.json()['chunks']} chunks")
        except requests.RequestException: st.warning("API unavailable")
    mode = st.selectbox("Retrieval",["hybrid","bm25","dense"])
    budget = st.slider("Tool budget",1,10,5)

question = st.text_area("Question",placeholder="Where is authentication checked and how does it work?",height=110)
if st.button("Investigate",type="primary",disabled=not (rid and len(question)>=3)):
    with st.spinner("Reading code and checking evidence…"):
        try:
            r = requests.post(f"{API}/query",json={"repository_id":rid,"question":question,"retrieval_mode":mode,"max_tool_calls":budget},timeout=120)
            r.raise_for_status()
            result = r.json()
            st.session_state.result = result
        except requests.RequestException as exc: st.error(str(exc))

if result := st.session_state.get("result"):
    st.subheader("Answer")
    st.write(result["answer"])
    st.caption(f"Evidence: {result['evidence_status']} · {result['tool_calls_used']} tool calls · {result['latency_ms']} ms")
    if result.get("error"): st.error(result["error"])
    if result["citations"]:
        st.subheader("Verified citations")
        for c in result["citations"]:
            with st.expander(f"{c['path']}:{c['start_line']}-{c['end_line']}"):
                st.code(c["snippet"])
    with st.expander("Investigation trace"):
        for t in result["trace"]:
            st.write(f"{t['step']}. {t['tool']} — {t['summary']}")
