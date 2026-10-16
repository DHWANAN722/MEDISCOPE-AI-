"""MediScope: run with `streamlit run app.py`."""
from pathlib import Path
import base64,html,io,json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import streamlit as st
import plotly.graph_objects as go
from analytics import CATEGORIES,SEVERITIES,AGES,clean_data,filter_data,grouped,metrics,usd,csv_safe
import charts
ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='MediScope | Hospital Intelligence',page_icon='✚',layout='wide',initial_sidebar_state='auto')
st.markdown('<style>'+(ROOT/'assets/style.css').read_text()+'</style>',unsafe_allow_html=True)
E=lambda x:html.escape(str(x))
@st.cache_resource(show_spinner='Opening the hospital dataset…')
def load_bundle():
 files=sorted((ROOT/'data').glob('discharges_*.parquet'))
 if not files:raise ValueError('Upload the complete data folder from the ZIP, or run scripts/prepare_data.py.')
 df=pa.concat_tables([pq.read_table(f) for f in files],promote_options="permissive").to_pandas(categories=CATEGORIES)
 audit=json.loads((ROOT/'data/cleaning_audit.json').read_text());meta=json.loads((ROOT/'data/source_metadata.json').read_text())
 if len(df)!=audit['clean_rows']:raise ValueError('Incomplete dataset. Include every discharges_*.parquet file.')
 return df,audit,meta
@st.cache_data(max_entries=1)
def load_uploaded(content):return clean_data(pd.read_csv(io.BytesIO(content),dtype=str))
def header(title,sub):st.markdown(f'<div class="section-title">{E(title)}</div><p style="color:#a9bad0;font-size:13px;margin-bottom:18px">{E(sub)}</p>',unsafe_allow_html=True)
def panel(title,num,tag,sub):st.markdown(f'<div class="card-heading"><h3><span class="num">{num}</span>{E(title)}</h3><span class="chip">{E(tag)}</span></div><p class="chart-sub">{E(sub)}</p>',unsafe_allow_html=True)
def insight(text):st.markdown(f'<div class="insight">{E(text)}</div>',unsafe_allow_html=True)
def draw(fig,key):st.plotly_chart(fig,use_container_width=True,theme=None,key=key,config={'displaylogo':False,'scrollZoom':False,'responsive':True,'toImageButtonOptions':{'format':'png','scale':2,'filename':'mediscope_'+key}})
def note(tag,title,text):st.markdown(f'<div class="info-card"><div class="tag">{E(tag)}</div><h4>{E(title)}</h4><p>{E(text)}</p></div>',unsafe_allow_html=True)
def reset_filters():
 for k in ['region','county','facility','age','severity','payer']:st.session_state['f_'+k]=[]
 st.session_state['trim']=False;st.session_state['minimum']=30;st.session_state['long_threshold']=14
try:full,audit,meta=load_bundle()
except (OSError,ValueError) as err:st.error(str(err));st.stop()
with st.sidebar:
 st.markdown('<div class="brand"><b>+</b>MediScope</div><div class="brand-sub">HOSPITAL INTELLIGENCE</div><div class="sidebar-label">REFINE THE VIEW</div>',unsafe_allow_html=True)
 st.caption('Choose a cohort. Every chart follows. Empty filters include all records.')
 with st.expander('Use your own data'):
  upload=st.file_uploader('SPARCS CSV · up to 200 MB',type=['csv'])
  st.caption('For the large assessment CSV, use scripts/prepare_data.py locally. The complete bundled dataset needs no upload.')
 if upload is not None:
  try:full,audit=load_uploaded(upload.getvalue())
  except Exception as err:st.error('Unable to read CSV: '+str(err));st.stop()
 source_key=upload.file_id if upload else 'bundle'
 if st.session_state.get('_source')!=source_key:reset_filters();st.session_state['_source']=source_key
 with st.form('cohort_form',border=False):
  filters={}
  for col,label in [('region','Hospital region'),('county','Hospital county'),('facility','Hospital facility'),('age','Age group'),('severity','Illness severity'),('payer','Primary payer')]:
   opts=sorted(full[col].cat.categories.astype(str))
   order=SEVERITIES if col=='severity' else AGES if col=='age' else []
   opts=[x for x in order if x in opts]+[x for x in opts if x not in order]
   filters[col]=st.multiselect(label,opts,key='f_'+col,placeholder='All '+label.lower().replace('hospital ',''))
  st.markdown('<div class="sidebar-label">ANALYSIS SETTINGS</div>',unsafe_allow_html=True)
  minimum=st.select_slider('Minimum discharges per group',options=[1,10,30,50,100,250],key='minimum',help='Used for comparative diagnosis, facility and 3D charts. KPIs and distributions include all selected records.')
  threshold=st.number_input('Long stay: more than … days',min_value=1,max_value=120,step=1,key='long_threshold',help='An exploration threshold, not a clinical quality standard.')
  trim=st.checkbox('Exclude top 1% of charges',key='trim',help='Uses a fixed percentile from the full loaded dataset. Missing charges remain in stay analysis.')
  st.form_submit_button('Apply filters  →',type='primary',use_container_width=True)
 st.button('Reset filters',on_click=reset_filters,use_container_width=True)
 st.markdown('<div class="sidebar-label">THE DATA</div>',unsafe_allow_html=True)
 st.caption(f'{len(full):,} valid discharges · {full.facility.nunique():,} facilities. Currency: USD. Each row is a discharge, not a unique patient.')
 st.caption('De-identified public-use data. No live hospital feed.')
cohort=filter_data(full,filters,trim,audit.get('charge_p99'))
selection=' | '.join(f'{k}: '+', '.join(v) for k,v in filters.items() if v) or 'All regions · all facilities'
years=', '.join(map(str,sorted(full.year.dropna().astype(int).unique()))) or 'Not provided'
st.markdown(f'<div class="topline micro"><span>MEDISCOPE / HEALTH ANALYTICS</span><span>DISCHARGE YEAR {E(years)} · NEW YORK</span></div>',unsafe_allow_html=True)
svg=base64.b64encode((ROOT/'assets/hospital.svg').read_bytes()).decode()
st.markdown(f'<section class="hero"><div class="eyebrow">FROM DISCHARGE DATA TO BETTER QUESTIONS</div><h1>HOSPITAL<br>INTELLIGENCE.</h1><p>Explore length of stay, hospital charges and the patterns behind inpatient care. One connected view, built for curious decision-makers.</p><img src="data:image/svg+xml;base64,{svg}" alt="Isometric hospital illustration"/><div class="hero-footer">EXPLORE / COMPARE / UNDERSTAND</div></section>',unsafe_allow_html=True)
page=st.radio('Workspace',['Overview','3D explorer','Costs & mix','Facility lens','Data & methods'],horizontal=True,label_visibility='collapsed',key='workspace')
if cohort.empty:st.warning('No discharge records match these filters. Broaden the selection or reset filters.');st.stop()
m=metrics(cohort,threshold)
items=[('DISCHARGE RECORDS',f'{m["discharges"]:,}','',f'{m["facilities"]:,} facilities in this selection','#f7edb8'),('AVERAGE STAY',f'{m["mean_stay"]:.1f}','days',f'Median {m["median_stay"]:.0f} days · top codes retained','#c4eedb'),('MEDIAN CHARGES',usd(m['median_charges']),'',f'{m["charge_n"]:,} records with valid charges','#e2d6fa'),('LONG-STAY SHARE',f'{m["long_rate"]:.1f}','%',f'{m["long_count"]:,} stays longer than {threshold} days','#ffbfa7')]
for col,(label,value,unit,sub,color) in zip(st.columns(4),items):
 with col:st.markdown(f'<div class="kpi" style="background:{color}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}<small>{unit}</small></div><div class="kpi-note">{E(sub)}</div></div>',unsafe_allow_html=True)
st.markdown(f'<div class="selection"><span><i class="dot"></i><b>{len(cohort)/len(full):.1%}</b> of the loaded dataset · {E(selection)}</span><span>{"TOP 1% CHARGES EXCLUDED" if trim else "ALL VALID STAYS INCLUDED"}</span></div>',unsafe_allow_html=True)
if trim:st.caption(f'Sensitivity view: charges above {usd(audit["charge_p99"])} excluded from all metrics. Missing charges remain in stay analyses.')
if page=='Overview':
 a,b=st.columns([1.1,1])
 with a:
  with st.container(key='panel_mint_diagnosis'):
   panel('Where stays run longer','01','DIAGNOSIS','Eight highest mean stays among qualifying diagnosis groups.')
   fig,g=charts.diagnosis_bar(cohort,minimum);draw(fig,'diagnosis')
   if len(g):
    r=g.sort_values('mean_stay',ascending=False).iloc[0];insight(f'{r.diagnosis} averages {r.mean_stay:.1f} days across {r.discharges:,} discharges. Compare case mix before interpreting differences.')
   else:insight('No diagnosis meets the minimum group size. Lower the threshold.')
 with b:
  with st.container(key='panel_lilac_severity'):
   panel('The cost of complexity','02','SEVERITY','Hospital charge distributions by illness severity; USD.')
   fig,g=charts.severity_box(cohort);draw(fig,'severity');g=g.loc[g.severity!='Unknown'] if len(g) else g
   if len(g)>1:insight(f'Median charges: {usd(g.iloc[0].median_charges)} ({g.iloc[0].severity}) versus {usd(g.iloc[-1].median_charges)} ({g.iloc[-1].severity}). Whiskers follow 1.5 × IQR; all valid charges inform the boxes.')
   else:insight('Boxes summarize all valid charges. Charges are billed amounts, not payments or hospital costs.')
 a,b=st.columns([1.1,1])
 with a:
  with st.container(key='panel_ice_distribution'):
   panel('Most stays. The long tail.','03','LENGTH OF STAY',f'Every selected discharge included; 31+ is a combined tail bin.')
   draw(charts.stay_hist(cohort,threshold),'stays');insight(f'{m["long_rate"]:.1f}% stay longer than {threshold} days. Source values of 120+ use 120, so the mean is a lower bound where these occur.')
 with b:
  with st.container(key='panel_peach_payers'):
   panel('Who covers the care?','04','PAYMENT MIX','Primary payment type recorded for each discharge.')
   draw(charts.payer_donut(cohort),'payer');insight('One primary payer per discharge. Small categories are combined only in this donut; original labels remain in filters and exports.')
 with st.container(key='panel_lilac_heatmap'):
  panel('A closer look at facilities','05','FACILITY × COUNTY','Mean stay at the 12 busiest qualifying facility–county groups.')
  fig,g=charts.facility_heatmap(cohort,minimum);draw(fig,'facility_heatmap');insight('Blank cells mean no matching group, not zero days. County is hospital location. These are descriptive comparisons, not risk-adjusted rankings.')
 header('What this view suggests','Evidence-backed prompts for the next investigation.')
 a,b,c=st.columns(3)
 with a:note('01 / CAPACITY',f'{m["long_count"]:,} long stays',f'Review pathways for stays over {threshold} days. This adjustable threshold is an exploration choice, not a quality benchmark.')
 with b:
  sev=grouped(cohort,['severity'],minimum).dropna(subset=['mean_charges']).sort_values('mean_charges',ascending=False)
  if len(sev):r=sev.iloc[0];note('02 / FINANCE',f'{r.severity} severity',f'Mean charges are {usd(r.mean_charges)} in this group. Explore diagnoses and stay duration before attributing a cause.')
  else:note('02 / FINANCE','Broaden the cohort','No group meets the current comparison threshold.')
 with c:note('03 / EXPLORE','Add a third dimension','Rotate diagnosis–severity groups in the 3D explorer. Compare age, illness complexity and hospital stay.')
elif page=='3D explorer':
 header('Explore the third dimension','Drag to rotate. Use chart controls to zoom. Double-click to reset.')
 view=st.radio('3D view',['Clinical constellation','Age × severity towers'],horizontal=True,key='three_view')
 flat=st.toggle('Use accessible 2D view',help='Use when WebGL is unavailable or to compare without perspective.')
 if view=='Clinical constellation':
  with st.container(key='panel_ice_cloud'):
   panel('Clinical constellation','06','3D EXPLORER','Each point is a diagnosis × severity group. Larger points contain more discharges.')
   fig,g=charts.three_dimensional_cloud(cohort,minimum,flat);draw(fig,'clinical_cloud');insight(f'{len(g):,} groups shown, ordered by discharge volume (up to 500). Each has at least {minimum} discharges; group means use all member rows. Unknown severity is omitted.')
  st.download_button('Download plotted group statistics',csv_safe(g),'mediscope_3d_groups.csv','text/csv')
 else:
  with st.container(key='panel_lilac_towers'):
   panel('Age × severity towers','07','3D COMPARISON','Tower height shows average stay. Categories are discrete, not a continuous surface.')
   if flat:
    g=grouped(cohort,['age','severity'],minimum);p=g.pivot_table(index='age',columns='severity',values='mean_stay',observed=True).reindex(index=AGES[:5],columns=SEVERITIES[:4])
    fig=charts.base(go.Figure(go.Heatmap(z=p.to_numpy(),x=p.columns,y=p.index,colorscale='Viridis',text=p.round(1).astype(str).replace('nan',''),texttemplate='%{text}',hoverongaps=False,colorbar=dict(title='Days'))),500)
   else:fig,g=charts.three_dimensional_bars(cohort,minimum)
   draw(fig,'severity_towers');insight(f'Each group requires {minimum} discharges. Unknown age or severity is omitted. Hover for exact group size and mean.')
 st.caption('3D charts require WebGL. Both views include 2D alternatives; perspective can affect visual comparisons.')
elif page=='Costs & mix':
 header('Follow the financial picture','Hospital charges, recorded costs and demographic case mix. All amounts are USD.')
 a,b=st.columns(2)
 with a:
  with st.container(key='panel_yellow_age'):
   panel('Charges across life stages','08','AGE × GENDER','Mean billed charges per discharge with valid charges.')
   draw(charts.age_chart(cohort),'age_charges');insight('Age bands come from the source. Differences can reflect diagnoses, severity, services and facility prices.')
 with b:
  with st.container(key='panel_peach_billing'):
   panel('The primary-payer lens','09','BILLING','Median charges by payer, after the group-size threshold.')
   draw(charts.payer_charges(cohort,minimum),'payer_charges');insight('Coverage type does not measure reimbursement. These are billed charges, not patient out-of-pocket costs or negotiated rates.')
 with st.container(key='panel_yellow_region'):
  panel('Regional payment patterns','10','REGION × PAYER','Mean stay for each qualifying region–payer group.')
  draw(charts.region_payer(cohort,minimum),'region_payer');insight(f'Cells require {minimum} discharges. Blank cells are absent or below that threshold.')
 st.subheader('Charges and costs are different')
 summary=grouped(cohort,['severity'],1)
 st.dataframe(summary[['severity','discharges','charge_n','mean_charges','median_charges','mean_cost']],hide_index=True,use_container_width=True,column_config={'severity':'Illness severity','discharges':'Discharges','charge_n':'Valid charge records','mean_charges':st.column_config.NumberColumn('Mean charges',format='$%.0f'),'median_charges':st.column_config.NumberColumn('Median charges',format='$%.0f'),'mean_cost':st.column_config.NumberColumn('Mean recorded cost',format='$%.0f')})
 st.caption('Recorded costs are source cost estimates. This is not a profitability or reimbursement analysis.')
elif page=='Facility lens':
 header('Compare facilities with context','Frame differences using severity, age and diagnosis mix. Lower stay or charges alone does not establish better care.')
 a,b=st.columns([1.6,1])
 with a:
  with st.container(key='panel_mint_facilities'):
   panel('Hospital operating landscape','11','FACILITY VIEW','One point per qualifying facility–county group. Size represents volume.')
   fig,g=charts.facility_scatter(cohort,minimum);draw(fig,'facility_landscape');insight('Hover to identify a hospital. This view does not adjust for case mix or specialty.')
 with b:
  with st.container(key='panel_peach_counties'):
   panel('County comparison','12','MEAN STAY','Ten highest mean stays among qualifying hospital counties.')
   g=grouped(cohort,['county'],minimum).sort_values('mean_stay',ascending=False).head(10).sort_values('mean_stay')
   f=charts.base(go.Figure(go.Bar(x=g.mean_stay,y=g.county.astype(str),orientation='h',marker_color=charts.CORAL,customdata=g.discharges,hovertemplate='%{y}<br>Mean %{x:.2f} days<br>n=%{customdata:,}<extra></extra>')),430);f.update_xaxes(title='Mean stay · days');draw(f,'counties');insight('County refers to hospital location, not the patient’s home.')
 rank=grouped(cohort,['facility','county'],minimum)
 sort=st.selectbox('Order facility table by',['Discharge volume','Mean length of stay','Mean charges'])
 rank=rank.sort_values({'Discharge volume':'discharges','Mean length of stay':'mean_stay','Mean charges':'mean_charges'}[sort],ascending=False)
 st.dataframe(rank[['facility','county','discharges','mean_stay','median_stay','mean_charges','median_charges']],hide_index=True,use_container_width=True,column_config={'facility':'Hospital facility','county':'County','discharges':st.column_config.NumberColumn('Discharges',format='%d'),'mean_stay':st.column_config.NumberColumn('Mean stay',format='%.2f days'),'median_stay':st.column_config.NumberColumn('Median stay',format='%.0f days'),'mean_charges':st.column_config.NumberColumn('Mean charges',format='$%.0f'),'median_charges':st.column_config.NumberColumn('Median charges',format='$%.0f')})
 st.download_button('Download facility comparison',csv_safe(rank),'mediscope_facilities.csv','text/csv')
else:
 header('Understand what is behind the view','Source, research questions, cleaning and limitations are part of the analysis.')
 a,b,c=st.columns(3)
 with a:note('SOURCE',f'{audit["source_rows"]:,} original records','Uploaded CSV' if upload else '2021 SPARCS · full official dataset')
 with b:note('CLEAN',f'{audit["invalid_stay_removed"]:,} invalid stays removed','Non-numeric, non-finite or non-positive lengths of stay are excluded.')
 with c:note('READY',f'{audit["clean_rows"]:,} valid discharges',f'{audit["topcoded_stays"]:,} stays top-coded at 120+ days.')
 st.subheader('Five questions that guide this dashboard')
 st.markdown('1. Which diagnosis categories have the longest average stays?\n2. Which age groups have the highest mean hospital charges?\n3. How do charges vary across severity levels?\n4. Which hospital counties and facilities have longer average stays?\n5. How do primary payment types differ in discharge share and billing?')
 st.subheader('What the data can and cannot tell us')
 st.markdown('''- **Discharges, not unique patients.** Without a patient identifier, repeat encounters cannot be linked and readmission rates cannot be calculated.
- **Annual data.** Discharge year is available, but not admission/discharge dates. Monthly trends are unavailable.
- **Diagnoses, not departments.** The app uses the source’s CCSR codes and readable diagnosis descriptions; departments are not inferred.
- **Charges, costs and payments differ.** Billed charges are not actual reimbursement. Recorded costs are separately labelled.
- **120+ stays are top-coded.** They use 120 as a lower bound, remain flagged and are retained by default.
- **High values are retained.** The optional charge-tail filter is explicit sensitivity analysis, not silent outlier deletion.
- **No causal or quality claims.** Comparisons are descriptive and not risk-adjusted.''')
 st.subheader('Cleaning audit')
 rows=[['Source rows',audit['source_rows']],['Invalid stays removed',audit['invalid_stay_removed']],['Clean discharge rows',audit['clean_rows']],['Missing / invalid charges',audit['charges_missing_or_invalid']],['Missing / invalid costs',audit['costs_missing_or_invalid']],['Top-coded 120+ stays',audit['topcoded_stays']]]
 st.dataframe(pd.DataFrame(rows,columns=['Check','Records']),hide_index=True,use_container_width=True)
 st.caption('Currency strings are parsed. Negative/non-finite monetary values become missing, preserving rows for stay analysis. Categories are standardized. Identical-looking rows are retained because there is no encounter ID. Unnecessary columns, including birth weight, are omitted.')
 st.subheader('Inspect and export this cohort')
 st.caption(f'First {min(500,len(cohort)):,} of {len(cohort):,} selected rows shown. Row exports are capped at 50,000; summary exports use all selected records.')
 st.dataframe(cohort.head(500),hide_index=True,use_container_width=True) 
 a,b,c=st.columns(3)
 with a:st.download_button('Download row excerpt',csv_safe(cohort.head(50000)),'mediscope_rows_first_50000.csv','text/csv')
 with b:st.download_button('Download diagnosis summary',csv_safe(grouped(cohort,['diagnosis_code','diagnosis'],1)),'mediscope_diagnoses.csv','text/csv')
 with c:st.download_button('Download cleaning audit',json.dumps(audit,indent=2),'cleaning_audit.json','application/json')
 st.subheader('Data provenance')
 st.markdown('[Official 2021 SPARCS dataset](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/tg3i-cinn) · [Assessment dataset folder](https://drive.google.com/drive/folders/1bHdRvwN77O3F85pFzoqmzBY2wNOabXms)')
 if upload is None:st.write(meta['note']);st.caption('Portal extract retrieved: '+meta['retrieved_utc'])
 else:st.caption('This session uses your uploaded CSV; its source and completeness have not been independently verified.')
 st.subheader('How the app works')
 st.markdown('**Load → clean → filter → aggregate → visualize.** Pandas groups and pivots the data. Plotly renders interactive charts. Streamlit connects controls and pages. No external API is called during normal use. Minimum group size affects comparative charts only; KPIs and distributions use the whole selected cohort.')
st.markdown('<div class="footer"><span>MEDISCOPE HEALTH ANALYTICS<br>MATHEMATICS FOR AI-II / SUMMATIVE ASSESSMENT</span><span>SPARCS 2021 · USD · DE-IDENTIFIED DATA<br>PYTHON + STREAMLIT + PLOTLY</span></div>',unsafe_allow_html=True)
