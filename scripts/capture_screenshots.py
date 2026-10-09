"""Capture the real app; requires requirements-dev.txt and `playwright install chromium`."""
from pathlib import Path
import os,sys,time,subprocess
import requests
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'screenshots';OUT.mkdir(exist_ok=True)
server=subprocess.Popen([sys.executable,'-m','streamlit','run','app.py','--server.port','8510','--server.headless','true'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(90):
  try:
   if requests.get('http://127.0.0.1:8510/_stcore/health',timeout=1).ok:break
  except requests.RequestException:pass
  time.sleep(.5)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
  page=browser.new_page(viewport={'width':1512,'height':1200},device_scale_factor=1)
  page.goto('http://127.0.0.1:8510',wait_until='domcontentloaded')
  page.get_by_text('What this view suggests',exact=True).wait_for(timeout=120000)
  page.wait_for_timeout(1200)
  page.screenshot(path=str(OUT/'01_overview.png'))
  def full(name):
   page.set_viewport_size({'width':1512,'height':3600});page.wait_for_timeout(500)
   b=page.locator('.block-container').bounding_box();height=min(3600,int(b['y']+b['height']+20))
   page.screenshot(path=str(OUT/name),clip={'x':0,'y':0,'width':1512,'height':height})
   page.set_viewport_size({'width':1512,'height':1200})
  full('02_overview_full.png')
  page.get_by_text('3D explorer',exact=True).click();page.get_by_text('Clinical constellation',exact=True).last.wait_for(timeout=120000)
  page.get_by_test_id('stPlotlyChart').wait_for(timeout=60000);page.wait_for_timeout(2200)
  full('03_3d_clinical.png')
  print('WebGL canvas count',page.locator('canvas').count(),flush=True)
  page.get_by_text('Age × severity towers',exact=True).first.click();page.wait_for_timeout(5000);full('04_3d_towers.png')
  page.get_by_text('Costs & mix',exact=True).click();page.get_by_text('Charges and costs are different',exact=True).wait_for(timeout=120000);page.wait_for_timeout(1000);full('05_costs_and_mix.png')
  page.get_by_text('Facility lens',exact=True).click();page.get_by_text('Download facility comparison',exact=True).wait_for(timeout=120000);page.wait_for_timeout(1000);full('06_facility_lens.png')
  page.get_by_text('Data & methods',exact=True).click();page.get_by_text('Data provenance',exact=True).wait_for(timeout=120000);page.wait_for_timeout(1000);full('07_data_and_methods.png')
  assert page.get_by_test_id('stException').count()==0
  # Exercise a real CSV download from the active page.
  with page.expect_download() as dl:page.get_by_text('Download diagnosis summary',exact=True).click()
  download=dl.value;assert download.suggested_filename=='mediscope_diagnoses.csv'
  print('CSV download verified',flush=True)
  page.get_by_text('Overview',exact=True).click();page.get_by_text('What this view suggests',exact=True).wait_for(timeout=120000)
  page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(1200)
  # Mobile opens with a collapsed sidebar in a fresh session.
  mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True)
  mobile.goto('http://127.0.0.1:8510');mobile.get_by_text('What this view suggests',exact=True).wait_for(timeout=120000);mobile.wait_for_timeout(800)
  mobile.screenshot(path=str(OUT/'08_mobile.png'))
  print('Screenshots captured',flush=True)
  browser.close()
finally:server.terminate()
