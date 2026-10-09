"""Rebuild the compact bundle from the original assessment CSV or the official API.
python scripts/prepare_data.py --csv /path/to/original.csv
python scripts/prepare_data.py --official
"""
import argparse,io,json,sys,tempfile,shutil
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from analytics import clean_data,CATEGORIES
API='https://health.data.ny.gov/resource/tg3i-cinn.csv'
FIELDS='hospital_service_area,hospital_county,facility_name,age_group,gender,race,length_of_stay,type_of_admission,patient_disposition,discharge_year,ccsr_diagnosis_code,ccsr_diagnosis_description,apr_severity_of_illness,payment_typology_1,total_charges,total_costs'
def official():
 count=requests.get(API,params={'$select':'count(*)'},timeout=120);count.raise_for_status()
 total=int(pd.read_csv(io.StringIO(count.text)).iloc[0,0])
 for offset in range(0,total,100000):
  res=requests.get(API,params={'$select':FIELDS,'$order':':id','$limit':100000,'$offset':offset},timeout=180);res.raise_for_status()
  yield pd.read_csv(io.StringIO(res.text),dtype=str)
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--csv',type=Path);g.add_argument('--official',action='store_true');args=p.parse_args()
 stage=Path(tempfile.mkdtemp(prefix='mediscope-data-'));audit={}
 try:
  chunks=pd.read_csv(args.csv,dtype=str,chunksize=100000) if args.csv else official()
  for i,chunk in enumerate(chunks):
   df,a=clean_data(chunk)
   for k,v in a.items():
    if isinstance(v,int):audit[k]=audit.get(k,0)+v
   df.to_parquet(stage/f'discharges_{i:02d}.parquet',index=False,compression='zstd');print(f'Processed {audit["source_rows"]:,} records',flush=True)
  paths=sorted(stage.glob('*.parquet'))
  if not paths:raise ValueError('The input contained no data rows.')
  df=pa.concat_tables([pq.read_table(f) for f in paths],promote_options='permissive').to_pandas(categories=CATEGORIES)
  audit['charge_p99']=float(df.charges.quantile(.99)) if df.charges.notna().any() else None
  audit['preserved_duplicates']='No patient/encounter identifier; identical-looking rows retained.'
  meta={'title':'Hospital Inpatient Discharges (SPARCS De-Identified): 2021','source_url':'https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/tg3i-cinn','source_rows':audit['source_rows'],'retrieved_utc':datetime.now(timezone.utc).isoformat(),'note':('Prepared from a user-provided CSV: '+args.csv.name) if args.csv else 'Official portal edition; may differ from the assessment Drive snapshot dated 2023. All source rows are included before cleaning.'}
  (stage/'cleaning_audit.json').write_text(json.dumps(audit,indent=2));(stage/'source_metadata.json').write_text(json.dumps(meta,indent=2))
  dest=ROOT/'data';dest.mkdir(exist_ok=True)
  # Replace the old bundle only after the full new bundle has validated.
  for old in dest.glob('discharges_*.parquet'):old.unlink()
  for f in stage.iterdir():shutil.copy2(f,dest/f.name)
  print(f'Ready: {len(df):,} valid discharges in {dest}')
 finally:shutil.rmtree(stage,ignore_errors=True)
if __name__=='__main__':main()
