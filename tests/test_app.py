"""Full-data integration check. Run `python -m pytest tests/test_app.py -q`."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_workspaces_filters_and_empty_state():
 app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=90).run()
 assert not app.exception and not app.error
 for page in ['3D explorer','Costs & mix','Facility lens','Data & methods','Overview']:
  app.radio(key='workspace').set_value(page).run();assert not app.exception
  if page=='3D explorer':
   app.radio(key='three_view').set_value('Age × severity towers').run();assert not app.exception
   app.toggle[0].set_value(True).run();assert not app.exception
 app.multiselect(key='f_county').set_value(['Bronx']).run();assert not app.exception
 assert 'Bronx' in app.multiselect(key='f_county').value
 # Mutually incompatible region/county selections exercise the empty state.
 app.multiselect(key='f_region').set_value(['Western NY']).run()
 assert not app.exception and any('No discharge records match' in w.value for w in app.warning)
