"""Transparent cleaning and aggregations for the 2021 SPARCS discharge dataset."""
from pathlib import Path
import re
import numpy as np
import pandas as pd

SEVERITIES = ['Minor', 'Moderate', 'Major', 'Extreme', 'Unknown']
AGES = ['0 to 17', '18 to 29', '30 to 49', '50 to 69', '70 or Older', 'Unknown']
ALIASES = {
 'hospital_service_area':'region', 'hospital_county':'county', 'facility_name':'facility',
 'age_group':'age', 'gender':'gender', 'race':'race', 'length_of_stay':'stay',
 'type_of_admission':'admission', 'patient_disposition':'disposition',
 'discharge_year':'year', 'ccsr_diagnosis_code':'diagnosis_code',
 'ccsr_diagnosis_description':'diagnosis', 'apr_severity_of_illness':'severity',
 'apr_severity_of_illness_description':'severity', 'payment_typology_1':'payer',
 'total_charges':'charges', 'total_costs':'costs',
}
CATEGORIES = ['region','county','facility','age','gender','race','admission','disposition','diagnosis_code','diagnosis','severity','payer']
REQUIRED = ['facility','county','age','stay','diagnosis_code','diagnosis','severity','payer','charges']

def normalize_column(col):
 return re.sub(r'[^a-z0-9]+','_',str(col).strip().lower()).strip('_')

def clean_data(raw):
 """Keep discharge rows; never deduplicate de-identified encounters without IDs."""
 raw=raw.rename(columns={c:ALIASES.get(normalize_column(c),normalize_column(c)) for c in raw})
 missing=[c for c in REQUIRED if c not in raw]
 if missing: raise ValueError('Missing required columns: '+', '.join(missing))
 keep=[c for c in dict.fromkeys(ALIASES.values()) if c in raw]
 df=raw.loc[:,keep].copy(); audit={'source_rows':len(df)}
 stay_text=df['stay'].astype('string').str.strip()
 df['stay_topcoded']=stay_text.str.endswith('+',na=False)
 df['stay']=pd.to_numeric(stay_text.str.replace('+','',regex=False),errors='coerce')
 invalid=df['stay'].isna()|~np.isfinite(df['stay'])|(df['stay']<=0)
 audit['invalid_stay_removed']=int(invalid.sum());df=df.loc[~invalid].copy()
 for col in ['charges','costs']:
  if col not in df: df[col]=np.nan
  text=df[col].astype('string').str.strip().str.replace(r'[\$,\s]','',regex=True)
  text=text.str.replace(r'^\((.*)\)$',r'-\1',regex=True)
  values=pd.to_numeric(text,errors='coerce').astype('float64')
  bad=~np.isfinite(values)|(values<0)
  audit[f'{col}_missing_or_invalid']=int(bad.sum())
  df[col]=values.mask(bad)
 for col in CATEGORIES:
  if col not in df: df[col]='Unknown'
  text=df[col].astype('string').str.strip().str.replace(r'\s+',' ',regex=True)
  text=text.mask(text.isna()|text.str.lower().isin(['','nan','none','null','not available','unknown']), 'Unknown')
  if col=='severity': text=text.str.title().replace({'1':'Minor','2':'Moderate','3':'Major','4':'Extreme','0':'Unknown'})
  if col=='age': text=text.replace({'70 or older':'70 or Older','70 Or Older':'70 or Older'})
  if col=='gender':text=text.replace({'M':'Male','F':'Female','U':'Unknown'})
  df[col]=text.astype('category')
 if 'year' not in df:df['year']=pd.NA
 df['year']=pd.to_numeric(df['year'],errors='coerce').astype('Int16')
 df['stay']=df['stay'].astype('float32')
 df['severity_score']=df['severity'].astype('string').map({'Minor':1,'Moderate':2,'Major':3,'Extreme':4}).astype('float32')
 audit['clean_rows']=len(df);audit['topcoded_stays']=int(df['stay_topcoded'].sum())
 audit['charge_p99']=float(df['charges'].quantile(.99)) if df.charges.notna().any() else None
 audit['preserved_duplicates']='No patient/encounter identifier is available; identical-looking rows are retained.'
 return df.reset_index(drop=True),audit

def filter_data(df, filters=None, trim=False, charge_cap=None):
 if not any((filters or {}).values()) and not trim:return df
 mask=pd.Series(True,index=df.index)
 for key,values in (filters or {}).items():
  if values:mask &= df[key].isin(values)
 if trim and charge_cap is not None:mask &= df.charges.isna() | (df.charges<=charge_cap)
 return df.loc[mask]

def grouped(df,by,min_n=1):
 out=df.groupby(by,observed=True).agg(discharges=('stay','size'),mean_stay=('stay','mean'),median_stay=('stay','median'),mean_charges=('charges','mean'),median_charges=('charges','median'),total_charges=('charges',lambda x:x.sum(min_count=1)),mean_cost=('costs','mean'),charge_n=('charges','count')).reset_index()
 return out.loc[out.discharges>=min_n].copy()

def metrics(df,threshold=14):
 return {'discharges':len(df),'mean_stay':float(df.stay.mean()),'median_stay':float(df.stay.median()),'median_charges':float(df.charges.median()),'mean_charges':float(df.charges.mean()),'long_rate':float(100*df.stay.gt(threshold).mean()),'long_count':int(df.stay.gt(threshold).sum()),'facilities':int(df.facility.nunique()),'charge_n':int(df.charges.count())}

def usd(v):
 if pd.isna(v):return 'Unavailable'
 return f'${v/1e9:.2f}B' if abs(v)>=1e9 else f'${v/1e6:.1f}M' if abs(v)>=1e6 else f'${v/1e3:.1f}k' if abs(v)>=1e3 else f'${v:,.0f}'

def csv_safe(df):
 """Prevent spreadsheet formula execution in downloadable categorical text."""
 out=df.copy()
 for col in out.select_dtypes(include=['object','string','category']).columns:
  s=out[col].astype('string')
  out[col]=s.mask(s.str.match(r'^[\s]*[=+@-]',na=False),"'"+s)
 return out.to_csv(index=False).encode('utf-8')
