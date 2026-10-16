from scripts.run_failure_drills import summarize

def test_complete_report(tmp_path):
    p=tmp_path/'x.xml';p.write_text('<testsuites><testsuite><testcase name="a"/><testcase name="b"/></testsuite></testsuites>')
    assert summarize(p)=={'tests':2,'failed':0,'errors':0,'skipped':0,'passed':2,'complete':True}

def test_skips_and_errors_are_incomplete(tmp_path):
    p=tmp_path/'x.xml';p.write_text('<testsuite><testcase><failure/></testcase><testcase><skipped/></testcase><testcase><error/></testcase></testsuite>')
    data=summarize(p)
    assert data['failed']==1 and data['errors']==1 and data['skipped']==1 and not data['complete']

def test_empty_is_not_success(tmp_path):
    p=tmp_path/'x.xml';p.write_text('<testsuite/>');assert not summarize(p)['complete']
