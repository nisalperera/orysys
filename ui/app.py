"""Streamlit client for the existing FastAPI SSE API. Run from repository root.
Demo user switching is NOT production authentication. API keys stay in the Streamlit server process.
"""
import os
import uuid
from pathlib import Path
import sys
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.client import APIError, Turn, stream_chat

load_dotenv()
st.set_page_config(page_title='Lanka Meridian Bank Assistant', layout='wide')

USERS={'Viewer':('viewer1','UI_VIEWER_API_KEY','dev-viewer-key'),
       'Analyst':('analyst1','UI_ANALYST_API_KEY','dev-analyst-key'),
       'Administrator':('admin1','UI_ADMIN_API_KEY','dev-admin-key')}
base=os.getenv('UI_API_BASE_URL','http://127.0.0.1:8000')

def reset():
    st.session_state.session_id=uuid.uuid4().hex
    st.session_state.messages=[]
    st.session_state.last_turn=None

if 'messages' not in st.session_state: reset()
with st.sidebar:
    st.header('Session')
    role=st.selectbox('Demo identity',list(USERS),key='role')
    identity, key_env, default_key=USERS[role]
    if st.session_state.get('identity') != identity:
        reset()
        st.session_state.identity=identity
    if st.button('New conversation'):
        reset()
        st.rerun()
    st.caption('Role changes start a new session to prevent cross-user memory reuse.')
    st.code(st.session_state.session_id,language=None)
    st.caption('Demo authentication only. Do not expose this identity selector publicly.')
    st.checkbox('Show provisional response tokens',value=False,key='preview',
                help='Tokens have not passed final validation. Keep off for safer demos.')

st.title('Lanka Meridian Bank Assistant')
st.caption('Answers from accessible documents, with observable agent activity.')
chat, activity=st.columns([3,2])

def sources(citations):
    if citations:
        with st.expander('Sources',expanded=False):
            for c in citations:
                st.write(c.get('doc_id','Source')+' | '+c.get('title','Research evidence'))
                if c.get('chunks'): st.caption(', '.join(c['chunks']))
                if c.get('created_date'): st.caption('Document date: '+c['created_date'])

def panel(turn):
    st.write('State: '+turn.label)
    st.caption('Active node: '+(turn.node or 'waiting'))
    if turn.retrieval:
        with st.expander('Retrieval',expanded=True): st.json(turn.retrieval)
    if turn.validation:
        with st.expander('Validation',expanded=True): st.json(turn.validation)
    if turn.memory:
        with st.expander('Memory',expanded=False): st.json(turn.memory)
    with st.expander('Activity events',expanded=True):
        # A new container is rendered per update; do not append unbounded widgets.
        for ev in reversed(turn.events[-30:]):
            st.caption(ev['type']+' / '+str(ev.get('node') or 'service'))
            st.json(ev['data'],expanded=False)

with chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
            sources(msg.get('citations',[]))
with activity:
    st.subheader('Agent Activity')
    panel_slot=st.empty()
    if st.session_state.last_turn:
        with panel_slot.container(): panel(st.session_state.last_turn)

prompt=st.chat_input('Ask about policies, incidents, runbooks or architecture',max_chars=2000)
if prompt:
    st.session_state.messages.append({'role':'user','content':prompt})
    with chat:
        with st.chat_message('user'): st.markdown(prompt)
        with st.chat_message('assistant'):
            answer_slot=st.empty()
            answer_slot.info('Working. Watch the Agent Activity panel.')
            turn=Turn()
            try:
                key=os.getenv(key_env,default_key)
                for event in stream_chat(base,key,st.session_state.session_id,prompt):
                    turn.accept(event)
                    if event['type']!='token':
                        with panel_slot.container(): panel(turn)
                    if st.session_state.preview and event['type'] in ('token','generation_start'):
                        answer_slot.markdown(turn.draft+' ▌')
                    if event['type']=='final':
                        answer_slot.markdown(turn.draft)
                if turn.final is None:
                    raise APIError('Connection ended before a final answer. Start a new conversation before retrying if context looks inconsistent.')
                final=turn.final
                if final.get('degraded'): st.warning('Partial or degraded result. Review validation and activity events.')
                if final.get('blocked'): st.info('Request blocked by a guardrail.')
                st.caption(f"Intent: {final.get('intent') or 'blocked'} | {final.get('latency_ms',0)} ms")
                sources(final.get('citations',[]))
                st.session_state.messages.append({'role':'assistant','content':turn.draft,'citations':final.get('citations',[])})
            except Exception as exc:
                # Never show raw HTTP errors or credentials in the UI.
                text=str(exc) if isinstance(exc,APIError) else 'Connection to the backend failed. Check the API server logs.'
                answer_slot.error(text)
                turn.label='Failed'
                turn.error=text
                st.session_state.messages.append({'role':'assistant','content':text})
            st.session_state.last_turn=turn
            with panel_slot.container(): panel(turn)
