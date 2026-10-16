"""Append hardening docs and report exclusions. No external state changes."""
from pathlib import Path
for name in ('README.md','config_guide.md'):
    p=Path(name);text=p.read_text() if p.exists() else '# Configuration guide\n'
    marker='## T6 offline failure drills'
    if marker not in text:
        p.write_text(text+'\n\n'+marker+'\nRun `python -m scripts.run_failure_drills` with T0-T5 installed. '
                     'See docs/T6_failure_drills.md for coverage, report handling and limitations. No new settings.\n')
p=Path('.gitignore');text=p.read_text() if p.exists() else ''
for entry in ('failure-drill-results/','acceptance-results/','*.py.t4.bak','*.reliability.bak','*.py.bak'):
    if entry not in text.splitlines():text+='\n'+entry
p.write_text(text.rstrip()+'\n')
