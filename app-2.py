import streamlit as st
import streamlit.components.v1 as components
import folium
import json, math, base64, os, pandas as pd

st.set_page_config(page_title="Unide Store Analysis", layout="wide", initial_sidebar_state="expanded")

BASE = "./"

@st.cache_data
def load_data():
    with open(BASE + "unide_app_data.json") as f:
        data = json.load(f)
    geojson = None
    if os.path.exists(BASE + "census_boundaries.geojson"):
        with open(BASE + "census_boundaries.geojson") as f:
            geojson = json.load(f)
    return data, geojson

APP_DATA, GEOJSON = load_data()
STORES     = APP_DATA["stores"]
COMPS      = APP_DATA["competitors"]
SPOILAGE   = APP_DATA["spoilage"]
SHELF_LIFE = APP_DATA["shelf_life"]
LOOKUP     = {s["store_id"]: s for s in STORES}
RC         = {0:"#1A7A4A", 1:"#D4AC0D", 2:"#E67E22", 3:"#C0392B"}
RL         = {0:"Well Matched", 1:"Low Risk", 2:"Medium Risk", 3:"High Risk"}
SNAMES     = {s["store_id"]: s["brand"]+" - "+s["city"]+" ("+s["province"]+")" for s in STORES}
SOPTS      = [SNAMES[s["store_id"]] for s in sorted(STORES, key=lambda x: int(x["store_id"]))]
NID        = {v: k for k, v in SNAMES.items()}

def gs(name):
    sid = NID.get(name)
    return LOOKUP.get(sid)

def card(label, value, sub=""):
    sub_h = '<div style="font-size:11px;color:rgba(255,255,255,0.4);margin-top:4px;">'+str(sub)+"</div>" if sub else ""
    return ('<div style="background:#0D1B2A;border:1px solid rgba(255,255,255,0.08);'
            'border-radius:8px;padding:14px;text-align:center;margin-bottom:8px;">'
            '<div style="font-size:10px;color:#E67E22;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;">'+str(label)+"</div>"
            '<div style="font-size:22px;font-weight:700;color:white;">'+str(value)+"</div>"+sub_h+"</div>")

def in_bbox(geom, a, b, c, d):
    try:
        coords = []
        def ex(obj):
            if isinstance(obj, list):
                if obj and isinstance(obj[0], (int,float)): coords.append(obj)
                else:
                    for i in obj: ex(i)
        ex(geom.get("coordinates",[]))
        return any(a<=p[1]<=c and b<=p[0]<=d for p in coords)
    except: return False

def make_map(store, ss, sc, scen, sb):
    slat, slng = store["lat"], store["lng"]
    m = folium.Map(location=[slat,slng], zoom_start=13, tiles="OpenStreetMap")
    if sb and GEOJSON:
        bbox=0.06
        feats=[f for f in GEOJSON["features"] if f.get("geometry") and in_bbox(f["geometry"],slat-bbox,slng-bbox,slat+bbox,slng+bbox)]
        if feats:
            folium.GeoJson(
                {"type":"FeatureCollection","features":feats},
                style_function=lambda f:{"fillColor":f["properties"].get("color","#888"),"color":"#FFFFFF","weight":1.0,"fillOpacity":0.35},
                highlight_function=lambda f:{"fillColor":f["properties"].get("color","#888"),"color":"#E67E22","weight":2.5,"fillOpacity":0.6},
                tooltip=folium.GeoJsonTooltip(fields=["Census Section","avg_demand"],aliases=["Section:","Demand:"],
                    style="background:rgba(13,27,42,0.95);color:white;font-size:11px;padding:6px;border:1px solid #E67E22;")
            ).add_to(m)
    folium.Circle(location=[slat,slng],radius=2000,color="#E67E22",weight=2,fill=True,fill_opacity=0.04,dash_array="8 4").add_to(m)
    if ss:
        for s in STORES:
            try:
                lat,lng=float(s["lat"]),float(s["lng"])
                if math.isnan(lat) or math.isnan(lng): continue
                sel=s["store_id"]==store["store_id"]
                col="#E67E22" if sel else RC.get(s["mismatch_score"],"#1B4F72")
                sz=16 if sel else 10
                bdr="3px solid #FFF" if sel else "2px solid rgba(255,255,255,0.5)"
                folium.Marker(location=[lat,lng],
                    icon=folium.DivIcon(html="<div style=\"width:"+str(sz)+"px;height:"+str(sz)+"px;background:"+col+";border:"+bdr+";border-radius:3px;transform:rotate(45deg);box-shadow:0 2px 6px rgba(0,0,0,0.5);\"></div>",icon_size=(sz,sz),icon_anchor=(sz//2,sz//2)),
                    tooltip=folium.Tooltip(s["brand"]+" - "+s["city"]+" | "+s["mismatch_flag"],sticky=True)
                ).add_to(m)
            except: continue
    if scen:
        secs=store.get("census_sections",[])
        mw=max((s["weight"] for s in secs),default=1) if secs else 1
        for sec in secs:
            try:
                sl,sln=float(sec["lat"]),float(sec["lng"])
                if math.isnan(sl) or math.isnan(sln): continue
                norm=sec["weight"]/max(mw,0.001)
                sz=max(6,int(norm*12))
                folium.PolyLine(locations=[[sl,sln],[slat,slng]],color="#E67E22",weight=max(1,norm*4),opacity=0.5,dash_array="4 2").add_to(m)
                folium.Marker(location=[sl,sln],
                    icon=folium.DivIcon(html="<div style=\"width:"+str(sz)+"px;height:"+str(sz)+"px;background:#85C1E9;border:1.5px solid #FFF;border-radius:50%;opacity:0.85;\"></div>",icon_size=(sz,sz),icon_anchor=(sz//2,sz//2)),
                    tooltip=folium.Tooltip("Section: "+sec["section_id"]+" | "+str(sec["distance_km"])+"km",sticky=True)
                ).add_to(m)
            except: continue
    if sc:
        bbox=0.06
        nk=set()
        for comp in store.get("competitors_nearby",[]):
            try:
                clat,clng=float(comp["comp_lat"]),float(comp["comp_lng"])
                if math.isnan(clat) or math.isnan(clng): continue
                nk.add(str(round(clat,4))+"_"+str(round(clng,4)))
                folium.Marker(location=[clat,clng],
                    icon=folium.DivIcon(html="<div style=\"width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:12px solid #F39C12;\"></div>",icon_size=(14,12),icon_anchor=(7,6)),
                    tooltip=folium.Tooltip(comp["comp_name"]+" | "+str(comp["distance_km"])+"km | "+str(int(comp["floor_size"]))+" m2",sticky=True)
                ).add_to(m)
            except: continue
        for comp in COMPS:
            try:
                clat,clng=float(comp["lat"]),float(comp["lng"])
                if math.isnan(clat) or math.isnan(clng): continue
                if not (slat-bbox<=clat<=slat+bbox and slng-bbox<=clng<=slng+bbox): continue
                if str(round(clat,4))+"_"+str(round(clng,4)) in nk: continue
                folium.Marker(location=[clat,clng],
                    icon=folium.DivIcon(html="<div style=\"width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:9px solid #C0392B;\"></div>",icon_size=(10,9),icon_anchor=(5,5)),
                    tooltip=folium.Tooltip(comp["comp_name"]+" | "+str(int(comp["floor_size"]))+" m2",sticky=True)
                ).add_to(m)
            except: continue
    legend="""<div style='position:fixed;bottom:20px;left:20px;background:rgba(13,27,42,0.96);padding:14px 18px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);font-family:Arial;font-size:11px;color:white;z-index:9999;'>
<div style='font-size:10px;font-weight:700;color:#E67E22;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:6px;'>Legend</div>
<div style='font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:4px;'>Stores (Diamond)</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:10px;height:10px;background:#E67E22;border:2px solid white;border-radius:2px;transform:rotate(45deg);'></div>Selected</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:9px;height:9px;background:#1A7A4A;border:1px solid white;border-radius:2px;transform:rotate(45deg);'></div>Well Matched</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:9px;height:9px;background:#D4AC0D;border:1px solid white;border-radius:2px;transform:rotate(45deg);'></div>Low Risk</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:9px;height:9px;background:#E67E22;border:1px solid white;border-radius:2px;transform:rotate(45deg);'></div>Medium Risk</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:8px;'><div style='width:9px;height:9px;background:#C0392B;border:1px solid white;border-radius:2px;transform:rotate(45deg);'></div>High Risk</div>
<div style='font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:4px;border-top:1px solid rgba(255,255,255,0.1);padding-top:6px;'>Competitors (Triangle)</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:10px solid #F39C12;'></div>Nearby</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:8px;'><div style='width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:8px solid #C0392B;'></div>Other</div>
<div style='font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:4px;border-top:1px solid rgba(255,255,255,0.1);padding-top:6px;'>Census (Circle)</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:9px;height:9px;background:#85C1E9;border:1px solid white;border-radius:50%;'></div>Census Point</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:12px;height:7px;background:#1A7A4A;opacity:0.5;border:1px solid white;'></div>High Demand</div>
<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'><div style='width:12px;height:7px;background:#D4AC0D;opacity:0.5;border:1px solid white;'></div>Medium Demand</div>
<div style='display:flex;align-items:center;gap:6px;'><div style='width:12px;height:7px;background:#C0392B;opacity:0.5;border:1px solid white;'></div>Low Demand</div>
</div>"""
    m.get_root().html.add_child(folium.Element(legend))
    map_html = m._repr_html_()
    return "<div style=\"width:100%;height:520px;border-radius:8px;overflow:hidden;\">" + map_html + "</div>"

with st.sidebar:
    st.title("Unide Store Analysis")
    st.caption("Neighbourhood Demand and Spoilage Analysis")
    st.divider()
    sel=st.selectbox("SELECT STORE",SOPTS,index=0)
    store=gs(sel)
    st.divider()
    st.caption("MAP OPTIONS")
    ss=st.checkbox("All Stores",value=True)
    sc=st.checkbox("Competitors",value=True)
    scen=st.checkbox("Census Points",value=True)
    sb=st.checkbox("Census Boundaries",value=True)
    st.divider()
    if store:
        mc=store["mismatch_score"]
        mc_col=RC.get(mc,"#888")
        st.caption("CURRENT STATUS")
        st.write(store["mismatch_flag"])
        st.caption("Score: "+str(mc)+"/3")

if not store:
    st.info("Select a store from the sidebar")
    st.stop()

st.title(store["brand"]+" - "+store["city"]+", "+store["province"])

t1,t2,t3,t4,t5,t6=st.tabs(["Map and Overview","What-If Analysis","Competitor Threat","Category Risk","Spoilage Overview","Store Comparison"])

with t1:
    col_map,col_ov=st.columns([3,2])
    with col_map:
        with st.spinner("Loading map..."):
            components.html(make_map(store,ss,sc,scen,sb),height=540)
    with col_ov:
        st.subheader("Store Profile")
        a,b=st.columns(2)
        with a:
            components.html(card("Potential Demand",store["potential_demand"],"out of 100"),height=90)
            components.html(card("Floor Size",str(int(store["floor_size"]))+" m2",store["x_group"]),height=90)
        with b:
            components.html(card("Market Share",str(store["market_share"])+"%","Huff Model"),height=90)
            components.html(card("Replenishment",str(store["replenishment"])+"x/week",store["y_group"]),height=90)
        st.divider()
        st.subheader("Mismatch Assessment")
        mc=store["mismatch_score"]
        mc_col=RC.get(mc,"#888")
        components.html(
            "<div style=\"background:"+mc_col+"18;border:1px solid "+mc_col+"44;border-left:4px solid "+mc_col+";border-radius:8px;padding:12px;font-family:Arial;\">"
            "<div style=\"display:flex;justify-content:space-between;align-items:center;\">"
            "<div style=\"font-size:14px;font-weight:600;color:white;\">"+store["mismatch_flag"]+"</div>"
            "<div style=\"background:"+mc_col+";padding:3px 12px;border-radius:4px;font-size:11px;font-weight:700;color:white;\">Score "+str(mc)+"/3</div>"
            "</div>"
            "<div style=\"font-size:11px;color:rgba(255,255,255,0.5);margin-top:6px;\">Demand Band: "+store["pd_band"]+" | Spending Power: "+str(store["spending_power"])+"</div>"
            "</div>",height=90)
        st.divider()
        st.subheader("Competitor Summary")
        a,b,c=st.columns(3)
        with a: components.html(card("Competitors",store["num_competitors_2km"],"within 2km"),height=90)
        with b: components.html(card("Threat Level",store["threat_level"]),height=90)
        with c: components.html(card("Combined m2",str(int(store.get("combined_comp_floor",0)))),height=90)

with t2:
    st.subheader("What-If Replenishment Analysis")
    st.caption("Current: "+str(store["replenishment"])+"x per week")
    sel_y=st.selectbox("SIMULATE REPLENISHMENT",[str(i)+"x per week" for i in range(1,8)],index=store["replenishment"]-1)
    y=int(sel_y.split("x")[0])
    w=store["whatif"].get(str(y),{})
    if w:
        if y==store["replenishment"]: st.info("This is the current replenishment frequency")
        a,b,c,d=st.columns(4)
        with a: components.html(card("Coverage",str(w.get("coverage",0))+"%","Demand served"),height=90)
        with b: components.html(card("Waste Rate",str(w.get("waste_rate",0))+"%","Est. spoilage"),height=90)
        with c: components.html(card("Days Between",str(w.get("gap_days",0))+"d","Deliveries"),height=90)
        with d: components.html(card("Risk Score",str(w.get("score",0))+"/3",RL.get(w.get("score",0),"")),height=90)
        st.divider()
        c1,c2=st.columns([2,1])
        with c1:
            sup=w.get("supply_level",0)
            dem=w.get("demand_level",0)
            st.caption("Supply Level - "+str(sup)+"%")
            st.progress(min(sup/100,1.0))
            st.caption("Demand Level - "+str(dem)+"%")
            st.progress(min(dem/100,1.0))
        with c2:
            mc_col2=RC.get(w.get("score",0),"#888")
            components.html(
                "<div style=\"background:"+mc_col2+"18;border:1px solid "+mc_col2+"44;border-left:4px solid "+mc_col2+";border-radius:8px;padding:12px;font-family:Arial;\">"
                "<div style=\"font-size:13px;font-weight:600;color:white;margin-bottom:6px;\">"+w.get("flag","")+"</div>"
                "<div style=\"font-size:11px;color:rgba(255,255,255,0.6);\">"+w.get("recommendation","")+"</div>"
                "</div>",height=100)
        ar=w.get("at_risk_categories",[])
        if ar:
            st.divider()
            st.subheader("Categories at Risk")
            cols=st.columns(min(len(ar),4))
            for i,cat in enumerate(ar[:8]):
                with cols[i%min(len(ar),4)]:
                    sl=SHELF_LIFE.get(cat,0)
                    components.html("<div style=\"background:rgba(192,57,43,0.1);border:1px solid rgba(192,57,43,0.3);border-radius:6px;padding:8px;text-align:center;font-family:Arial;\">"
                        "<div style=\"font-size:11px;font-weight:600;color:white;\">"+cat+"</div>"
                        "<div style=\"font-size:10px;color:#C0392B;margin-top:2px;\">"+str(sl)+"d shelf life</div></div>",height=60)

with t3:
    st.subheader("Competitor Threat - Within 2km")
    a,b,c,d=st.columns(4)
    with a: components.html(card("Threat Level",store["threat_level"]),height=90)
    with b: components.html(card("Competitors",store["num_competitors_2km"],"within 2km"),height=90)
    with c: components.html(card("Combined Floor",str(int(store.get("combined_comp_floor",0)))+" m2"),height=90)
    with d: components.html(card("Threat Ratio",str(store.get("threat_ratio",0))+"x"),height=90)
    st.divider()
    st.subheader("Nearby Competitors")
    nearby=store.get("competitors_nearby",[])
    if nearby:
        for comp in nearby:
            components.html(
                "<div style=\"background:rgba(255,255,255,0.05);border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #C0392B;font-family:Arial;\">"
                "<div style=\"display:flex;justify-content:space-between;align-items:center;\">"
                "<div><div style=\"font-size:14px;font-weight:600;color:white;\">"+comp["comp_name"]+"</div>"
                "<div style=\"font-size:11px;color:rgba(255,255,255,0.4);margin-top:3px;\">"+comp["comp_city"]+" - "+str(comp["distance_km"])+" km away</div></div>"
                "<div style=\"text-align:right;\">"
                "<div style=\"font-size:14px;color:#E67E22;font-weight:600;\">"+str(int(comp["floor_size"]))+" m2</div>"
                "<div style=\"font-size:11px;color:rgba(255,255,255,0.4);\">Eff: "+str(int(comp["effective_floor_size"]))+" m2</div>"
                "</div></div></div>",height=80)
    else:
        st.success("No competitors within 2km")

with t4:
    st.subheader("Category Spoilage Risk")
    risks=store.get("category_risk",[])
    if risks:
        for r in risks:
            risk=r.get("risk","Low")
            cat=r.get("category","")
            reason=r.get("reason","")
            sl=r.get("shelf_life_days",0)
            yoy=r.get("yoy_change",0)
            rate=r.get("rate_2025",0)
            trend="Getting Worse" if yoy>0.5 else "Getting Better" if yoy<-0.5 else "Stable"
            col={"High":"#C0392B","Medium":"#D4AC0D","Low":"#1A7A4A","Opportunity":"#1B4F72"}.get(risk,"#888")
            sl_txt="<div style=\"font-size:10px;color:rgba(255,255,255,0.3);margin-top:2px;\">Shelf life: "+str(sl)+" days</div>" if sl>0 else ""
            yc="#C0392B" if yoy>0.5 else "#1A7A4A" if yoy<-0.5 else "#D4AC0D"
            rate_txt="<div style=\"margin-top:8px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.08);font-size:11px;color:rgba(255,255,255,0.6);\">Rate 2025: <b style=\"color:white;\">"+str(rate)+"%</b> - YoY: <b style=\"color:"+yc+";\">"+("+' if yoy>0 else "")+str(yoy)+"% - "+trend+"</b></div>" if rate else ""
            components.html(
                "<div style=\"background:rgba(255,255,255,0.05);border-radius:8px;padding:12px;margin-bottom:8px;border-left:4px solid "+col+";font-family:Arial;\">"
                "<div style=\"display:flex;justify-content:space-between;align-items:flex-start;\">"
                "<div style=\"flex:1;\">"
                "<div style=\"font-size:14px;font-weight:600;color:white;\">"+cat+"</div>"
                "<div style=\"font-size:11px;color:rgba(255,255,255,0.5);margin-top:3px;\">"+reason+"</div>"
                +sl_txt+
                "</div>"
                "<div style=\"background:"+col+";padding:3px 12px;border-radius:4px;font-size:11px;font-weight:700;color:white;margin-left:12px;\">"+risk+"</div>"
                "</div>"+rate_txt+"</div>",height=100)
    else:
        st.info("No category risk data available")

with t5:
    st.subheader("Warehouse Spoilage Overview")
    df=pd.DataFrame(SPOILAGE).sort_values("rate_2025",ascending=False)
    t24=df["spoilage_2024"].sum(); s24=df["sales_2024"].sum()
    t25=df["spoilage_2025"].sum(); s25=df["sales_2025"].sum()
    r24=t24/s24*100 if s24>0 else 0
    r25=t25/s25*100 if s25>0 else 0
    yoy=r25-r24
    a,b,c=st.columns(3)
    with a: components.html(card("Overall Rate 2024",str(round(r24,2))+"%"),height=90)
    with b: components.html(card("Overall Rate 2025",str(round(r25,2))+"%"),height=90)
    with c: components.html(card("YoY Change",("+' if yoy>0 else "")+str(round(yoy,2))+"%"),height=90)
    st.divider()
    rows=[]
    for _,row in df.iterrows():
        y2=row.get("yoy_change",0)
        sl=SHELF_LIFE.get(row["Category"],0)
        t="Getting Worse" if y2>0.5 else "Getting Better" if y2<-0.5 else "Stable"
        rows.append({"Category":row["Category"],"Shelf Life":str(sl)+"d","Rate 2024":str(round(row.get("rate_2024",0),2))+"%","Rate 2025":str(round(row.get("rate_2025",0),2))+"%","YoY":("+' if y2>0 else "")+str(round(y2,2))+"%","Trend":t})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True,height=500)

with t6:
    st.subheader("Store Comparison")
    ca,cb=st.columns(2)
    with ca: na=st.selectbox("STORE A",SOPTS,index=0,key="sa")
    with cb: nb=st.selectbox("STORE B",SOPTS,index=1,key="sb")
    a=gs(na); b=gs(nb)
    if a and b and na!=nb:
        st.divider()
        mc_a=RC.get(a["mismatch_score"],"#888")
        mc_b=RC.get(b["mismatch_score"],"#888")
        c1,c2=st.columns(2)
        with c1:
            components.html("<div style=\"background:"+mc_a+"18;border:1px solid "+mc_a+"44;border-radius:8px;padding:14px;text-align:center;font-family:Arial;\">"
                "<div style=\"font-size:10px;color:#E67E22;margin-bottom:4px;\">STORE A</div>"
                "<div style=\"font-size:16px;font-weight:700;color:white;\">"+a["brand"]+"</div>"
                "<div style=\"font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px;\">"+a["city"]+", "+a["province"]+"</div></div>",height=90)
        with c2:
            components.html("<div style=\"background:"+mc_b+"18;border:1px solid "+mc_b+"44;border-radius:8px;padding:14px;text-align:center;font-family:Arial;\">"
                "<div style=\"font-size:10px;color:#E67E22;margin-bottom:4px;\">STORE B</div>"
                "<div style=\"font-size:16px;font-weight:700;color:white;\">"+b["brand"]+"</div>"
                "<div style=\"font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px;\">"+b["city"]+", "+b["province"]+"</div></div>",height=90)
        st.divider()
        metrics=[("Floor Size (m2)",a["floor_size"],b["floor_size"],True),("Spending Power",a["spending_power"],b["spending_power"],True),("Market Share (%)",a["market_share"],b["market_share"],True),("Potential Demand",a["potential_demand"],b["potential_demand"],True),("Competitors (2km)",a["num_competitors_2km"],b["num_competitors_2km"],False),("Mismatch Score",a["mismatch_score"],b["mismatch_score"],False)]
        h1,h2,h3,h4=st.columns([2,1,1,1])
        h1.write("**Metric**"); h2.write("**Store A**"); h3.write("**Store B**"); h4.write("**Better**")
        for label,va,vb,higher in metrics:
            better="A" if isinstance(va,(int,float)) and isinstance(vb,(int,float)) and (va>vb)==higher else "B"
            c1,c2,c3,c4=st.columns([2,1,1,1])
            c1.caption(label)
            c2.write(str(round(va,1)) if isinstance(va,float) else str(va))
            c3.write(str(round(vb,1)) if isinstance(vb,float) else str(vb))
            c4.write("**"+better+"**")
        st.divider()
        better="A" if a["potential_demand"]>b["potential_demand"] else "B"
        riskier="A" if a["mismatch_score"]>b["mismatch_score"] else "B" if b["mismatch_score"]>a["mismatch_score"] else "neither"
        st.info("Store "+better+" has higher potential demand. "+("Store "+riskier+" carries higher mismatch risk." if riskier!="neither" else "Both stores carry equal mismatch risk."))
    elif na==nb:
        st.warning("Please select two different stores to compare")
