"""Pure guards for task instructions, collection-wide comparisons and evidence attribution."""
import re
PLACEHOLDER=re.compile(r'\[(?:DOC[_ ]?ID|DOCUMENT[_ ]?ID|CHUNK[_ ]?ID|SOURCE[_ ]?ID)\]',re.I)
ID=re.compile(r'\b[A-Z]{2,5}-(?:\d{4}-)?\d{3}(?:#\d+)?\b')
GENERIC={'what each batch must extract','how to combine the findings','what to extract','how to aggregate','question','...'}
def placeholder_task(text):
    return text.strip().lower().rstrip('.?!') in {x.rstrip('.') for x in GENERIC}
def collection_comparison(text):
    return bool(re.search(r'\b(most|fewest|highest|lowest|longest|shortest|maximum|minimum|average|total|ranking)\b',text,re.I)
                and re.search(r'\b(incidents?|outages?|reports?|those|these|across|among)\b',text,re.I))
def scope_context(state):
    scope=(state.get('research_scope') or {}).get('question','')
    if scope: return scope
    for ep in reversed(state.get('episodes') or []):
        q=ep.get('q','')
        if re.search(r'last year|past year|recurring|all.*(?:incidents|outages)',q,re.I): return q
    return ''
def research_scope_query(query,scope):
    return query+'\nCollection scope from prior research: '+scope if scope else query

def citations_in_answer(text):
    return {i for block in re.findall(r'\[([^\]\n]+)\]',text) for i in ID.findall(block)}
def task_for_user(question):
    return ('Original user request: '+question+'\nFor each document, determine relevance to this request; '
            'extract root cause, affected service, summary and evidence chunk IDs. For comparisons retain every '
            'incident in the requested collection, not only likely winners.')
def render_extreme(question,analysis):
    q=question.lower()
    txn=bool(re.search(r'(most|highest|maximum|largest).*?(failed transactions|transaction (?:count|impact))',q))
    longest=bool(re.search(r'(longest|maximum|highest).*?(downtime|duration)',q))
    shortest=bool(re.search(r'(shortest|minimum|lowest).*?(downtime|duration)',q))
    if not(txn or longest or shortest): return None
    records=analysis.get('incidents') or []
    key='failed_transactions' if txn else 'duration_minutes'
    if not records or any(not isinstance(x.get(key),(int,float)) for x in records): return None
    value=(min if shortest else max)(x[key] for x in records)
    winners=[x for x in records if x[key]==value]
    label='highest failed-transaction count' if txn else ('shortest downtime' if shortest else 'longest downtime')
    unit='failed transactions' if txn else 'minutes'
    ids=', '.join('['+x['doc_id']+']' for x in winners)
    text=f'Across the {len(records)} analysed incidents, {ids} had the {label}: {value:,} {unit}.'
    mentioned={i.split('#')[0] for i in ID.findall(question)}
    prior=[x for x in records if x['doc_id'] in mentioned and x not in winners]
    if txn and prior:
        text+=' For comparison, '+'; '.join(f'[{x["doc_id"]}] had {x[key]:,} failed transactions' for x in prior)+'.'
    return text
