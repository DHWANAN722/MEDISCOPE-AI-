"""Plotly charts. Aggregation happens before rendering; no million-row browser payloads."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from analytics import grouped,SEVERITIES,AGES
INK='#102039'; MINT='#258b73'; CORAL='#ef7659'; PURPLE='#8665ca'; BLUE='#447ab7'
COLORS=[MINT,BLUE,PURPLE,CORAL,'#b89425','#557a74','#8b6384','#52606d']
SEV_COLORS=dict(zip(SEVERITIES,[MINT,BLUE,PURPLE,CORAL,'#8b96a8']))

def base(fig,height=330):
 fig.update_layout(height=height,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Arial, sans-serif',size=11,color=INK),margin=dict(l=12,r=20,t=25,b=25),hoverlabel=dict(bgcolor=INK,font_color='white'),legend=dict(orientation='h',y=-.2,x=0,font_size=10),modebar=dict(bgcolor='rgba(0,0,0,0)',color='#526079',activecolor=CORAL))
 fig.update_xaxes(gridcolor='rgba(16,32,57,0.08)',zeroline=False,title_font_size=11,automargin=True)
 fig.update_yaxes(gridcolor='rgba(16,32,57,0.08)',zeroline=False,title_font_size=11,automargin=True)
 return fig

def diagnosis_bar(df,min_n=30,top=8):
 g=grouped(df,['diagnosis_code','diagnosis'],min_n).sort_values('mean_stay',ascending=False).head(top).sort_values('mean_stay')
 if g.empty:return base(go.Figure()),g
 labels=g.diagnosis.astype(str).apply(lambda x:x if len(x)<31 else x[:28]+'…')
 fig=go.Figure(go.Bar(x=g.mean_stay,y=labels,orientation='h',marker=dict(color=g.mean_stay,colorscale=[[0,'#7fc4a9'],[1,'#235c53']]),text=[f"{v:.1f}" for v in g.mean_stay],textposition='outside',cliponaxis=False,customdata=g[['diagnosis','diagnosis_code','discharges']],hovertemplate='<b>%{customdata[0]}</b><br>CCSR %{customdata[1]}<br>Mean stay %{x:.2f} days<br>Discharges %{customdata[2]:,}<extra></extra>'))
 fig.update_xaxes(title='Mean length of stay · days',range=[0,float(g.mean_stay.max())*1.23]);return base(fig,350),g

def severity_box(df):
 fig=go.Figure();stats=[]
 for sev in SEVERITIES:
  v=df.loc[df.severity==sev,'charges'].dropna()
  if v.empty:continue
  q1,med,q3=v.quantile([.25,.5,.75]);iqr=q3-q1
  low=float(v[v>=q1-1.5*iqr].min());high=float(v[v<=q3+1.5*iqr].max())
  fig.add_trace(go.Box(name=sev,x=[sev],q1=[q1],median=[med],q3=[q3],lowerfence=[low],upperfence=[high],marker_color=SEV_COLORS[sev],fillcolor=SEV_COLORS[sev],opacity=.85,boxpoints=False,showlegend=False,hovertemplate=f'<b>{sev}</b><br>n={len(v):,}<br>Median ${med:,.0f}<br>IQR ${q1:,.0f}–${q3:,.0f}<extra></extra>'))
  stats.append({'severity':sev,'n':len(v),'median_charges':med})
 fig.update_yaxes(title='Hospital charges · USD',tickprefix='$',tickformat='~s');return base(fig,350),pd.DataFrame(stats)

def stay_hist(df,threshold=14):
 # Preserve all observations, with the capped tail explicitly named.
 edges=np.arange(.5,31.5,1);counts,_=np.histogram(df.stay,bins=edges)
 labels=[str(i) for i in range(1,31)]+['31+'];values=counts.tolist()+[int(df.stay.gt(30.5).sum())]
 fig=go.Figure(go.Bar(x=labels,y=values,marker_color=[MINT if i<=threshold else CORAL for i in range(1,31)]+[CORAL if threshold<=30 else '#8a94a5'],hovertemplate='%{x} days<br>%{y:,} discharges<extra></extra>'))
 fig.update_xaxes(type='category',title='Length of stay · days',tickvals=['1','5','10','15','20','25','31+'])
 fig.update_yaxes(title='Discharges',tickformat='~s');fig.update_layout(bargap=.12)
 return base(fig,310)

def payer_donut(df):
 counts=df.payer.value_counts().loc[lambda x:x>0];labels=list(counts.index.astype(str));values=list(counts.values)
 if len(values)>6:labels=labels[:5]+['Other payers (combined)'];values=values[:5]+[sum(values[5:])]
 fig=go.Figure(go.Pie(labels=labels,values=values,hole=.7,sort=False,marker=dict(colors=COLORS,line=dict(color='#ffe0ce',width=3)),textinfo='percent',textfont_size=11,textposition='outside',hovertemplate='<b>%{label}</b><br>%{value:,} discharges · %{percent}<extra></extra>'))
 fig.update_layout(annotations=[dict(text=f'<b>{len(df)/1000:,.1f}k</b><br>discharges',x=.5,y=.5,showarrow=False,font_size=19)],legend=dict(orientation='v',x=1.02,y=.9),margin=dict(l=25,r=25,t=25,b=25))
 return base(fig,310).update_layout(legend=dict(orientation='h',x=0,y=-.12))

def facility_heatmap(df,min_n=30,limit=12):
 top=grouped(df,['facility','county'],min_n).sort_values('discharges',ascending=False).head(limit).sort_values(['county','facility'])
 if top.empty:return base(go.Figure()),top
 pivot=top.pivot_table(index='facility',columns='county',values='mean_stay',observed=True).reindex(top.facility.tolist())
 ns=top.pivot_table(index='facility',columns='county',values='discharges',observed=True).reindex(index=pivot.index,columns=pivot.columns)
 names=[str(s) if len(str(s))<48 else str(s)[:45]+'…' for s in pivot.index]
 fig=go.Figure(go.Heatmap(z=pivot.to_numpy(),x=pivot.columns.astype(str),y=names,customdata=ns.to_numpy(),colorscale=[[0,'#f6f0cc'],[.5,'#ae91dd'],[1,'#503a91']],text=np.where(pivot.notna(),pivot.round(1).astype(str),''),texttemplate='%{text}',textfont_size=11,hoverongaps=False,colorbar=dict(title='Days',thickness=9,len=.8),hovertemplate='<b>%{y}</b><br>%{x}<br>Mean stay %{z:.2f} days<br>n=%{customdata:,.0f}<extra></extra>',xgap=4,ygap=4))
 fig.update_xaxes(side='top',showgrid=False);fig.update_yaxes(autorange='reversed',showgrid=False)
 return base(fig,420),top

def age_chart(df):
 g=grouped(df,['age','gender']);fig=go.Figure()
 for i,gender in enumerate(sorted(g.gender.astype(str).unique())):
  part=g.loc[g.gender==gender].set_index('age').reindex(AGES).dropna(subset=['discharges'])
  fig.add_trace(go.Bar(name=gender,x=part.index,y=part.mean_charges,marker_color=COLORS[i%len(COLORS)],customdata=part[['charge_n','discharges']],hovertemplate='<b>%{x}</b><br>Mean charges $%{y:,.0f}<br>Valid charges %{customdata[0]:,}<br>Discharges %{customdata[1]:,}<extra></extra>'))
 fig.update_layout(barmode='group');fig.update_yaxes(title='Mean charges · USD',tickprefix='$',tickformat='~s');return base(fig,380)

def payer_charges(df,min_n=30):
 g=grouped(df,['payer'],min_n).sort_values('median_charges');fig=go.Figure(go.Bar(x=g.median_charges,y=g.payer.astype(str),orientation='h',marker_color=CORAL,customdata=g[['discharges','charge_n']],hovertemplate='%{y}<br>Median charges $%{x:,.0f}<br>n=%{customdata[0]:,}<extra></extra>'))
 fig.update_xaxes(title='Median hospital charges · USD',tickprefix='$',tickformat='~s');return base(fig,380)

def region_payer(df,min_n=30):
 g=grouped(df,['region','payer'],min_n);p=g.pivot_table(index='region',columns='payer',values='mean_stay',observed=True)
 fig=go.Figure(go.Heatmap(x=p.columns.astype(str),y=p.index.astype(str),z=p.to_numpy(),colorscale=[[0,'#f7edb8'],[.5,'#f5a77a'],[1,'#a74743']],text=p.round(1).astype(str).replace('nan',''),texttemplate='%{text}',hoverongaps=False,colorbar=dict(title='Days'),hovertemplate='%{y} / %{x}<br>Mean stay %{z:.2f} days<extra></extra>',xgap=3,ygap=3))
 return base(fig,380)

def three_dimensional_cloud(df,min_n=30,two_d=False):
 g=grouped(df.loc[df.severity_score.notna()],['diagnosis','severity','severity_score'],min_n).dropna(subset=['mean_charges'])
 # Most numerous groups displayed; aggregation is exact within each displayed group.
 g=g.sort_values('discharges',ascending=False).head(500)
 fig=go.Figure()
 for sev in SEVERITIES[:4]:
  p=g[g.severity==sev];size=np.clip(np.sqrt(p.discharges)/3,4,24)
  common=dict(name=sev,mode='markers',marker=dict(size=size,color=SEV_COLORS[sev],opacity=.8),customdata=p[['diagnosis','discharges','severity']],hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[2]} · n=%{customdata[1]:,}<br>Mean stay %{x:.2f} days<br>Mean charges $%{y:,.0f}<extra></extra>')
  if two_d:fig.add_trace(go.Scatter(x=p.mean_stay,y=p.mean_charges,**common))
  else:fig.add_trace(go.Scatter3d(x=p.mean_stay,y=p.mean_charges,z=p.severity_score,**common))
 fig=base(fig,600)
 if two_d:fig.update_xaxes(title='Mean stay · days');fig.update_yaxes(title='Mean charges · USD',tickprefix='$',tickformat='~s')
 else:
  axis=dict(backgroundcolor='#ebf1f4',gridcolor='#becdd8',showbackground=True,zeroline=False,color=INK)
  fig.update_layout(scene=dict(xaxis=dict(title='Mean stay · days',**axis),yaxis=dict(title='Mean charges · USD',tickprefix='$',tickformat='~s',**axis),zaxis=dict(title='Severity',tickvals=[1,2,3,4],ticktext=SEVERITIES[:4],**axis),camera=dict(eye=dict(x=1.7,y=-1.7,z=1.1)),aspectmode='cube'),margin=dict(l=0,r=0,t=5,b=5),legend=dict(x=0,y=0,orientation='h'),uirevision='cloud')
 return fig,g

def three_dimensional_bars(df,min_n=30):
 g=grouped(df,['age','severity'],min_n);fig=go.Figure()
 for _,r in g.iterrows():
  if r.age not in AGES[:5] or r.severity not in SEVERITIES[:4]:continue
  x=AGES.index(r.age);y=SEVERITIES.index(r.severity);z=float(r.mean_stay);w=.34
  xx=[x-w,x+w,x+w,x-w]*2; yy=[y-w,y-w,y+w,y+w]*2;zz=[0]*4+[z]*4
  fig.add_trace(go.Mesh3d(x=xx,y=yy,z=zz,i=[0,0,0,0,1,1,2,2,3,3,4,4],j=[1,2,1,5,2,6,3,7,0,4,5,6],k=[2,3,5,4,6,5,7,6,4,7,6,7],color=SEV_COLORS[r.severity],flatshading=True,lighting=dict(ambient=.7,diffuse=.85,specular=.2),hovertemplate=f'<b>{r.age} · {r.severity}</b><br>Mean stay {z:.2f} days<br>n={r.discharges:,}<extra></extra>',showlegend=False))
 axis=dict(backgroundcolor='#eae5f6',gridcolor='#c2b7d9',showbackground=True,color=INK)
 fig=base(fig,600);fig.update_layout(scene=dict(xaxis=dict(title='Age group',tickvals=list(range(5)),ticktext=AGES[:5],**axis),yaxis=dict(title='Severity',tickvals=list(range(4)),ticktext=SEVERITIES[:4],**axis),zaxis=dict(title='Mean stay · days',**axis),camera=dict(eye=dict(x=1.7,y=-1.9,z=1.3)),aspectratio=dict(x=1.3,y=1,z=.85)),margin=dict(l=0,r=0,t=0,b=0),uirevision='bars')
 return fig,g

def facility_scatter(df,min_n=30):
 g=grouped(df,['facility','county'],min_n).dropna(subset=['mean_charges'])
 fig=go.Figure(go.Scatter(x=g.mean_stay,y=g.mean_charges,mode='markers',marker=dict(size=np.clip(np.sqrt(g.discharges)/8,6,35),color=g.discharges,colorscale=[[0,'#82c9b1'],[1,'#254960']],opacity=.8,line=dict(color='white',width=1)),customdata=g[['facility','county','discharges']],hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]} · n=%{customdata[2]:,}<br>Mean stay %{x:.2f} days<br>Mean charges $%{y:,.0f}<extra></extra>'))
 fig.update_xaxes(title='Mean stay · days');fig.update_yaxes(title='Mean charges · USD',tickprefix='$',tickformat='~s');return base(fig,430),g
