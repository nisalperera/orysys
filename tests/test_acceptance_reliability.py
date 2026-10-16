from app.reliability import (placeholder_task,collection_comparison,citations_in_answer,
                             task_for_user,render_extreme,scope_context)

def test_placeholders_rejected():
    assert placeholder_task('what each batch must extract')
    assert placeholder_task('How to combine the findings.')
    assert not placeholder_task('Extract root causes for all payment incidents')

def test_collection_routing_not_single_product_limit():
    assert collection_comparison('Which of those incidents had the longest downtime?')
    assert collection_comparison('Was incident INC-2025-044 also the incident with the most failed transactions?')
    assert not collection_comparison('What is the maximum transaction limit in this product specification?')

def test_scope_survives_followup():
    assert scope_context({'research_scope':{'question':'payment outages last year'}})=='payment outages last year'
    assert scope_context({'episodes':[{'q':'all payment incidents last year'}]})=='all payment incidents last year'

def test_only_real_bracketed_sources():
    assert citations_in_answer('INC-2025-044 [DOC_ID]')==set()
    assert citations_in_answer('[INC-2025-044, INC-2026-029]')=={'INC-2025-044','INC-2026-029'}
    assert citations_in_answer('[RB-001#1]')=={'RB-001#1'}

def test_original_task_is_in_subagent_instruction():
    assert 'payment failures last year' in task_for_user('payment failures last year')
    assert 'not only likely winners' in task_for_user('x')

RECORDS=[{'doc_id':'INC-2025-044','duration_minutes':95,'failed_transactions':2860},
         {'doc_id':'INC-2026-029','duration_minutes':44,'failed_transactions':8670}]

def test_deterministic_maximum_from_all_records():
    text=render_extreme('Was INC-2025-044 the incident with the most failed transactions?',{'incidents':RECORDS})
    assert '[INC-2026-029]' in text and '8,670' in text and '[INC-2025-044]' in text
    assert '95 minutes' in render_extreme('Which incident had the longest downtime?',{'incidents':RECORDS})

def test_comparison_missing_metric_abstains():
    assert render_extreme('Which incident had the longest downtime?',{'incidents':[{'doc_id':'A'}]}) is None
    assert render_extreme('Summarize root causes',{'incidents':RECORDS}) is None

def test_tied_extrema_preserved():
    text=render_extreme('Which incident had the longest downtime?',{'incidents':[
        {'doc_id':'A','duration_minutes':95},{'doc_id':'B','duration_minutes':95}]})
    assert '[A]' in text and '[B]' in text
