"""Run offline T6 tests, save pytest output and JUnit report, reject skipped tests as incomplete.
python -m scripts.run_failure_drills
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def summarize(path):
    tree=ET.parse(path).getroot()
    cases=list(tree.iter('testcase'))
    counts={'tests':len(cases),'failed':0,'errors':0,'skipped':0,'passed':0}
    for case in cases:
        kind='failed' if case.find('failure') is not None else ('errors' if case.find('error') is not None else
              ('skipped' if case.find('skipped') is not None else 'passed'))
        counts[kind]+=1
    counts['complete']=bool(cases) and not(counts['failed'] or counts['errors'] or counts['skipped'])
    return counts


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='failure-drill-results');a=p.parse_args()
    dest=Path(a.out)/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');dest.mkdir(parents=True)
    report=dest/'junit.xml'
    env={**os.environ,'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'}
    result=subprocess.run([sys.executable,'-m','pytest','-q','-rA','tests/test_failure_drills.py',
                           '--junitxml='+str(report)],capture_output=True,text=True,env=env)
    text=result.stdout+'\n'+result.stderr
    for key in ('LANGSMITH_API_KEY','LLM_API_KEY','OPENROUTER_API_KEY','PINECONE_API_KEY',
                'UI_VIEWER_API_KEY','UI_ANALYST_API_KEY','UI_ADMIN_API_KEY'):
        value=env.get(key)
        if value: text=text.replace(value,'[REDACTED]')
    (dest/'pytest.log').write_text(text)
    print(text)
    summary=summarize(report) if report.exists() else {'complete':False,'error':'JUnit report missing'}
    summary['pytest_exit_code']=result.returncode
    (dest/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2));print('Reports:',dest)
    return 0 if result.returncode==0 and summary['complete'] else 1

if __name__=='__main__':sys.exit(main())
