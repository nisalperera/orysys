import json
import pytest
from ui.client import APIError, Turn, parse_sse

def event(kind, **data): return {'type':kind,'data':data,'node':'response'}
def test_parser_comments_and_multiline():
    ev=event('token',text='hello\nworld')
    lines=[': ping','','data: '+json.dumps(ev),'']
    assert list(parse_sse(lines))==[ev]

def test_parser_rejects_incomplete_and_invalid_events():
    with pytest.raises(APIError): list(parse_sse(['data: {}','']))
    with pytest.raises(APIError): list(parse_sse(['data: {"type":"token","data":{}}']))

def test_retry_clears_draft_final_replaces_tokens():
    t=Turn()
    t.accept(event('token',text='bad'))
    t.accept(event('generation_start',reset=True))
    assert t.draft==''
    t.accept(event('token',text='draft'))
    t.accept(event('final',answer='validated answer',citations=[]))
    assert t.draft=='validated answer' and t.label=='Complete'

def test_activity_sections_and_bounded_history():
    t=Turn()
    t.accept(event('retrieval',hits=8))
    t.accept(event('validation',ok=True))
    t.accept(event('memory_updated',turns=2))
    assert t.retrieval['hits']==8 and t.validation['ok'] and t.memory['turns']==2
    for _ in range(200): t.accept(event('state',label='working'))
    assert len(t.events)==150
