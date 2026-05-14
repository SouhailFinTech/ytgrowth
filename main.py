"""
AlgoQuant Studio v2.4 — Full Production SaaS
FIXES: 
- Fixed YouTube transcript extraction AttributeError (Library v0.6+ compatibility)
- Restored robust translation fallback
Single file. Deploy: streamlit run main.py
"""

import json, re, time, os, io, base64, textwrap, requests
from datetime import datetime, timedelta
from collections import Counter

import streamlit as st
import pandas as pd
import google.generativeai as genai

# ════════════════════════════════════════════════════════════
# SUPABASE CLIENT (Level 1 — Persistence)
# ════════════════════════════════════════════════════════════

def get_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def db_save(table: str, data: dict, user_id: str = None):
    sb = get_supabase()
    if not sb:
        if table not in st.session_state:
            st.session_state[table] = []
        if isinstance(st.session_state[table], list):
            st.session_state[table].append(data)
        return True
    try:
        if user_id:
            data['user_id'] = user_id
        data['created_at'] = datetime.utcnow().isoformat()
        sb.table(table).insert(data).execute()
        return True
    except Exception as e:
        st.warning(f"DB save failed: {e}")
        return False


def db_fetch(table: str, user_id: str = None, limit: int = 50):
    sb = get_supabase()
    if not sb:
        return st.session_state.get(table, [])
    try:
        q = sb.table(table).select("*").order("created_at", desc=True).limit(limit)
        if user_id:
            q = q.eq("user_id", user_id)
        return q.execute().data
    except Exception:
        return st.session_state.get(table, [])


def db_update(table: str, record_id: str, data: dict):
    sb = get_supabase()
    if not sb:
        return True
    try:
        sb.table(table).update(data).eq("id", record_id).execute()
        return True
    except Exception:
        return False


# ════════════════════════════════════════════════════════════
# GOOGLE OAUTH (Level 2 — Multi-user Auth)
# ════════════════════════════════════════════════════════════

def get_google_auth_url():
    client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")
    redirect  = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
    if not client_id:
        return None
    scopes = "openid email profile"
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect}"
        f"&response_type=code"
        f"&scope={scopes}"
        f"&access_type=offline"
    )


def exchange_code_for_token(code: str):
    try:
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "code"         : code,
            "client_id"    : st.secrets.get("GOOGLE_CLIENT_ID",""),
            "client_secret": st.secrets.get("GOOGLE_CLIENT_SECRET",""),
            "redirect_uri" : st.secrets.get("REDIRECT_URI","http://localhost:8501"),
            "grant_type"   : "authorization_code",
        })
        return resp.json()
    except Exception:
        return None


def get_user_info(access_token: str):
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        return resp.json()
    except Exception:
        return None


def is_logged_in():
    return bool(st.session_state.get('user'))

def get_user_id():
    user = st.session_state.get('user', {})
    return user.get('id', 'anonymous')


def login_page():
    st.markdown("""
    <div style='min-height:100vh;display:flex;align-items:center;justify-content:center;'>
    <div style='text-align:center;max-width:420px;padding:3rem;background:#111318;border:1px solid #1e2229;border-radius:20px;'>
        <div style='font-size:3rem;margin-bottom:0.5rem;'>⚡</div>
        <div style='font-size:1.8rem;font-weight:700;color:#00e5a0;margin-bottom:0.25rem;'>AlgoQuant Studio</div>
        <div style='font-size:0.82rem;color:#6b7280;margin-bottom:2rem;letter-spacing:0.08em;text-transform:uppercase;'>Content Intelligence for Algo Creators</div>
        <div style='font-size:0.9rem;color:#9ca3af;margin-bottom:2rem;line-height:1.6;'>
            The AI system that tells you exactly what video to make, writes the script,
            scores the title, and designs the thumbnail.
        </div>
    """, unsafe_allow_html=True)

    auth_url = get_google_auth_url()
    params = st.query_params
    if "code" in params:
        with st.spinner("Signing you in..."):
            token_data = exchange_code_for_token(params["code"])
            if token_data and "access_token" in token_data:
                user_info = get_user_info(token_data["access_token"])
                if user_info:
                    st.session_state['user'] = {
                        'id'           : user_info.get('id', 'anon'),
                        'email'        : user_info.get('email', ''),
                        'name'         : user_info.get('name', 'Creator'),
                        'picture'      : user_info.get('picture', ''),
                        'access_token' : token_data.get('access_token', ''),
                    }
                    rows = db_fetch('user_configs', get_user_id(), 1)
                    if rows:
                        st.session_state['config'] = rows[0].get('config_json', {})
                    st.query_params.clear()
                    st.rerun()

    if auth_url:
        st.markdown(f"""
        <a href="{auth_url}" style='
            display:inline-block;background:#00e5a0;color:#000;
            font-weight:700;padding:0.75rem 2rem;border-radius:10px;
            text-decoration:none;font-size:0.95rem;margin-bottom:1rem;
        '>🔐 Sign in with Google</a>
        """, unsafe_allow_html=True)
    else:
        if st.button("🚀  Continue as Demo User", use_container_width=True):
            st.session_state['user'] = {
                'id': 'demo', 'email': 'demo@algoquant.studio',
                'name': 'Demo Creator', 'picture': '', 'access_token': ''
            }
            st.rerun()
        st.markdown("<div style='font-size:0.72rem;color:#6b7280;margin-top:0.5rem;'>OAuth not configured — running in demo mode</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ════════════════════════════════════════════════════════════

def init_session():
    if 'config' not in st.session_state:
        st.session_state['config'] = {
            'channel_name'   : 'AlgoQuant Trading',
            'creator_bio'    : 'Financial engineer from Morocco, self-taught quant',
            'products'       : 'SaaS, MQL5 EAs, courses, freelance',
            'subscribers'    : 5,
            'watch_hours'    : 1.4,
            'avg_ctr'        : 2.5,
            'total_videos'   : 4,
            'gemini_api_key' : '',
            'youtube_api_key': '',
            'email'          : '',
        }
    try:
        if hasattr(st, 'secrets'):
            cfg = st.session_state['config']
            if 'GEMINI_API_KEY' in st.secrets and not cfg.get('gemini_api_key'):
                cfg['gemini_api_key']  = st.secrets['GEMINI_API_KEY']
            if 'YOUTUBE_API_KEY' in st.secrets and not cfg.get('youtube_api_key'):
                cfg['youtube_api_key'] = st.secrets['YOUTUBE_API_KEY']
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
# PAGE CONFIG & CSS
# ════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AlgoQuant Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
  --bg:#0a0c10;--surface:#111318;--border:#1e2229;
  --accent:#00e5a0;--accent2:#0066ff;--warn:#ff6b35;
  --text:#e8eaf0;--muted:#6b7280;
  --green:#00e5a0;--red:#ff4560;--yellow:#ffd700;
}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--text)!important;font-family:'Space Grotesk',sans-serif!important;}
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border)!important;}
[data-testid="stSidebar"] *{color:var(--text)!important;}
h1,h2,h3,h4{font-family:'Space Grotesk',sans-serif!important;color:var(--text)!important;font-weight:700!important;}
.stButton>button{background:var(--accent)!important;color:#000!important;border:none!important;border-radius:8px!important;font-weight:600!important;font-family:'Space Grotesk',sans-serif!important;padding:0.5rem 1.5rem!important;transition:all 0.2s!important;}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 4px 20px rgba(0,229,160,0.3)!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea,.stSelectbox>div>div{background:var(--surface)!important;border:1px solid var(--border)!important;color:var(--text)!important;border-radius:8px!important;}
.stTabs [data-baseweb="tab-list"]{background:var(--surface)!important;border-radius:8px;}
.stTabs [data-baseweb="tab"]{color:var(--muted)!important;}
.stTabs [aria-selected="true"]{color:var(--accent)!important;}
.metric-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.25rem 1.5rem;position:relative;overflow:hidden;}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent);}
.metric-val{font-size:2rem;font-weight:700;color:var(--accent);line-height:1;margin-bottom:0.25rem;}
.metric-lbl{font-size:0.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em;}
.video-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem 1.25rem;margin-bottom:0.75rem;transition:border-color 0.2s;}
.video-card:hover{border-color:var(--accent);}
.score-badge{display:inline-block;padding:0.2rem 0.6rem;border-radius:20px;font-size:0.75rem;font-weight:600;}
.score-green{background:rgba(0,229,160,0.15);color:var(--green);}
.score-yellow{background:rgba(255,215,0,0.15);color:var(--yellow);}
.score-red{background:rgba(255,69,96,0.15);color:var(--red);}
.section-header{font-size:0.7rem;text-transform:uppercase;letter-spacing:0.12em;color:var(--muted);margin-bottom:0.75rem;margin-top:1.5rem;}
.tag{display:inline-block;background:rgba(0,102,255,0.15);color:#60a5fa;border:1px solid rgba(0,102,255,0.3);border-radius:4px;padding:0.15rem 0.5rem;font-size:0.72rem;margin:0.15rem;}
.funnel-badge{display:inline-block;padding:0.2rem 0.7rem;border-radius:20px;font-size:0.72rem;font-weight:600;background:rgba(255,107,53,0.15);color:var(--warn);}
.step-box{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;padding:0.75rem 1rem;margin-bottom:0.5rem;}
.script-block{background:#0d1117;border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem;font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:#c9d1d9;line-height:1.7;white-space:pre-wrap;}
.divider{border:none;border-top:1px solid var(--border);margin:1.25rem 0;}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# INIT + AUTH GATE
# ════════════════════════════════════════════════════════════

init_session()
has_oauth = bool(st.secrets.get("GOOGLE_CLIENT_ID", "")) if hasattr(st, 'secrets') else False

if has_oauth and not is_logged_in():
    login_page()
    st.stop()
elif not is_logged_in():
    st.session_state['user'] = {'id': 'demo', 'email': '', 'name': 'Creator', 'picture': '', 'access_token': ''}

cfg     = st.session_state['config']
user    = st.session_state.get('user', {})
user_id = user.get('id', 'demo')

# ════════════════════════════════════════════════════════════
# ENGINE — AI + YOUTUBE LOGIC
# ════════════════════════════════════════════════════════════

FUNNEL_DESCRIPTIONS = {
    'saas'      : 'SaaS platform waitlist — mention you are building a tool that automates this for traders',
    'ea'        : 'MQL5 EA product — full working EA available on MQL5 market link in description',
    'course'    : 'Upcoming course — covered in full detail in the course link in description',
    'freelance' : 'Freelance service — you build custom EAs for traders link in description'
}
FORMAT_CONTEXT = {
    'short': 'SHORT video under 60 seconds. Script under 130 words. Result in first sentence. Never Hi or Welcome.',
    'long' : 'LONG FORM video 10-20 minutes. Include [minute] markers. Show concept not full code.'
}
DEFAULT_CHANNELS = {
    'Part Time Larry'   : 'UCY2ifv8iH1Dsgjrz-h3lWLQ',
    'The Quant Science' : 'UCnMn36GT_H0X-w5_ckLtlgQ',
    'Algovibes'         : 'UCF5Whbu7E7OAK0RUljUKS8w',
    'Quantra'           : 'UCbmNph6atAoGfqLoCL_duAg',
}


def get_model():
    key = cfg.get('gemini_api_key', '')
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel('gemini-2.0-flash') # Updated to current stable model


def call_gemini(model, prompt, max_tokens=2000):
    for attempt in range(2):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens, temperature=0.7),
                request_options={"timeout": 120}
            )
            raw = resp.text.strip()
            raw = re.sub(r'```json|```', '', raw).strip()
            o, c = raw.count('{'), raw.count('}')
            if o > c: raw += '}' * (o - c)
            return json.loads(raw)
        except Exception as e:
            if attempt == 0: time.sleep(3)
            else: raise e


def call_gemini_text(model, prompt, max_tokens=2000):
    for attempt in range(2):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens, temperature=0.7),
                request_options={"timeout": 120}
            )
            return resp.text.strip()
        except Exception as e:
            if attempt == 0: time.sleep(3)
            else: raise e


def build_context():
    return f"""
Channel: {cfg.get('channel_name','AlgoQuant Trading')}
Niche: Algorithmic trading, quantitative finance, automated trading systems
Target: Prop firm traders (FTMO/Funded Next), manual traders, crypto quants, algo investors
Creator: {cfg.get('creator_bio','Financial engineer, self-taught quant')}
Pipeline: idea → Python backtest → MQL5 → live MT5
Products: {cfg.get('products','SaaS, MQL5 EAs, courses, freelance')}

What works (competitor data):
- Titles starting with I: 100% success, 80k avg views
- Dollar sign: 100% success, 113k avg views
- Python/backtest/FTMO/algo/bot: 100% success
- Number in title: 88% success
- Warning/never/secret: very high
- Honest failure content: massive engagement

Stats: {cfg.get('subscribers',5)} subs · {cfg.get('avg_ctr',2.5)}% CTR · {cfg.get('watch_hours',1.4)}h

Hook rules (CRITICAL):
- First sentence MUST contain result or bold claim
- NEVER start with Hi, Welcome, Today we are
- Must match title promise exactly
- TTS-friendly: short sentences, natural pauses
"""


def fetch_competitor_videos(api_key, channels, n=20):
    from googleapiclient.discovery import build as yt_build
    yt  = yt_build('youtube', 'v3', developerKey=api_key)
    out = []
    for name, cid in channels.items():
        try:
            cr  = yt.channels().list(part='contentDetails,statistics', id=cid).execute()
            if not cr['items']: continue
            cd  = cr['items'][0]
            uid = cd['contentDetails']['relatedPlaylists']['uploads']
            subs= int(cd['statistics'].get('subscriberCount',0))
            vids= []
            npt = None
            while len(vids) < n:
                pr = yt.playlistItems().list(part='contentDetails',playlistId=uid,
                    maxResults=min(50,n-len(vids)),pageToken=npt).execute()
                for it in pr['items']: vids.append(it['contentDetails']['videoId'])
                npt = pr.get('nextPageToken')
                if not npt: break
            for i in range(0,len(vids),50):
                sr = yt.videos().list(part='snippet,statistics,contentDetails',
                    id=','.join(vids[i:i+50])).execute()
                for v in sr['items']:
                    sn   = v['snippet']; st2 = v.get('statistics',{})
                    dur  = v['contentDetails']['duration']
                    m    = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',dur)
                    tsec = int(m.group(1) or 0)*3600+int(m.group(2) or 0)*60+int(m.group(3) or 0)
                    pub  = datetime.strptime(sn['publishedAt'],'%Y-%m-%dT%H:%M:%SZ')
                    dold = max((datetime.utcnow()-pub).days,1)
                    views= int(st2.get('viewCount',0))
                    out.append({'channel':name,'channel_subs':subs,'title':sn['title'],
                        'video_id':v['id'],'url':f"https://youtube.com/watch?v={v['id']}",
                        'published':pub.strftime('%Y-%m-%d'),'days_old':dold,'views':views,
                        'likes':int(st2.get('likeCount',0)),'comments':int(st2.get('commentCount',0)),
                        'views_per_day':round(views/dold,1),'duration_sec':tsec,'is_short':tsec<=60})
        except Exception: continue
    return out


def analyze_patterns(videos, threshold=5000):
    STOP = {'a','an','the','and','or','but','in','on','at','to','for','of','with','by',
            'from','is','it','my','i','your','how','what','why','when','this','that',
            'you','we','are','was','be','have','has','do','did','will','can','get',
            'as','its','not','into','using','vs','if','so'}
    lf   = [v for v in videos if not v['is_short']]
    sh   = [v for v in videos if v['is_short']]
    succ = [v for v in lf if v['views']>=threshold]
    def words(titles):
        w=[]
        for t in titles:
            c=re.sub(r'[^a-zA-Z0-9\s]','',t.lower())
            for x in c.split():
                if x not in STOP and len(x)>2: w.append(x)
        return w
    top_words = Counter(words([v['title'] for v in succ])).most_common(20)
    trending  = sorted([v for v in lf if v['days_old']<=30],key=lambda x:x['views_per_day'],reverse=True)[:5]
    evergreen = sorted([v for v in lf if v['days_old']>180],key=lambda x:x['views_per_day'],reverse=True)[:5]
    top20     = sorted(lf,key=lambda x:x['views'],reverse=True)[:20]
    return {'total':len(videos),'long_count':len(lf),'short_count':len(sh),
            'success_count':len(succ),'top_words':top_words,
            'trending':trending,'evergreen':evergreen,'top20':top20}


def ai_virality(model,idea,fmt,funnel,ctx):
    return call_gemini(model,f"""
You are a YouTube growth expert for algorithmic trading.
{ctx}
Idea: {idea}
Format: {FORMAT_CONTEXT[fmt]}
Funnel: {funnel}
Score 0-100 across audience_demand,trend_alignment,differentiation,creator_fit,monetization_fit (each 20).
If below 60 suggest better angle. If 60+ approve.
Return ONLY valid JSON no markdown:
{{"idea_summary":"","virality_score":78,"breakdown":{{"audience_demand":16,"trend_alignment":15,"differentiation":14,"creator_fit":18,"monetization_fit":15}},"verdict":"approved","verdict_reason":"","better_angle":null}}
""",800)


def ai_title_hook(model,idea,fmt,funnel,ctx):
    return call_gemini(model,f"""
You are a YouTube growth expert for algorithmic trading.
{ctx}
Idea: {idea}
Format: {FORMAT_CONTEXT[fmt]}
Funnel: {FUNNEL_DESCRIPTIONS[funnel]}
Best title above 75 score and hook. Hook: result first sentence TTS-ready never Hi.
Short under 130 words. Long 60-90 words.
Return ONLY valid JSON no markdown:
{{"title":"","title_score":82,"title_reasoning":"","hook_script":"","hook_score":85,"hook_reasoning":"","alternative_titles":[{{"title":"","score":78}},{{"title":"","score":75}},{{"title":"","score":76}}]}}
""",1200)


def ai_script_part(model, idea, title, hook, funnel, ctx, fmt, part, prev=''):
    cont = f'\nContinue from: "{prev[-300:]}"' if part == 2 else ''
    if fmt == 'short':
        inst = 'Write the COMPLETE SHORT script. STRICTLY 100-130 words total. Under 55 seconds when spoken. Fast pace. Result first. Zero fluff. End with direct CTA.'
    else:
        inst = 'Write FIRST HALF ~1000 words. End at natural transition.' if part == 1 else 'Write SECOND HALF ~1000 words. End with subscribe CTA then funnel CTA.'
        
    return call_gemini_text(model, f"""
You are a YouTube scriptwriter for algorithmic trading.
{ctx}
Format: {FORMAT_CONTEXT[fmt]}
Title: {title}
Idea: {idea}
Funnel: {FUNNEL_DESCRIPTIONS[funnel]}
{cont}
Rules: TTS-friendly short sentences. Show concept not code. {'Include [minute] markers.' if fmt=='long' else 'Keep it tight, one continuous flow. No [minute] markers.'} Never Hi Welcome.
{inst}
{'Start with: '+hook if part==1 else ''}
Return ONLY raw script text. No JSON. No markdown.
""", 800 if fmt=='short' else 2000)


def ai_packaging(model,idea,title,fmt,funnel,ctx):
    return call_gemini(model,f"""
You are a YouTube packaging expert for algorithmic trading.
{ctx}
Title: {title}
Idea: {idea}
Format: {fmt}
Funnel: {FUNNEL_DESCRIPTIONS[funnel]}
Generate thumbnail 2 options SEO 3 shorts CTA.
Return ONLY valid JSON no markdown:
{{"thumbnail":{{"option_1":{{"concept":"","background":"","main_text":"","sub_text":"","visual":"","colors":["#hex"],"canva_steps":"","predicted_ctr":""}},"option_2":{{"concept":"","background":"","main_text":"","sub_text":"","visual":"","colors":["#hex"],"canva_steps":"","predicted_ctr":""}},"recommended":"1","recommended_reason":""}},"seo":{{"tags":["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10"],"description_line1":"","description_line2":"","chapters":[{{"time":"0:00","title":""}},{{"time":"2:00","title":""}},{{"time":"5:00","title":""}},{{"time":"10:00","title":""}},{{"time":"14:00","title":""}}]}},"shorts":[{{"title":"","hook":"","clip":""}},{{"title":"","hook":"","clip":""}},{{"title":"","hook":"","clip":""}}],"cta_script":""}}
""",2500)


def ai_suggestions(model,trending,existing,ctx):
    tt='\n'.join([f"- {v['title']} ({v.get('views_per_day',0):,.0f}/day,{v.get('days_old',0)}d)" for v in trending[:5]])
    et='\n'.join([f"- {t}" for t in existing[:10]])
    return call_gemini(model,f"""
YouTube content strategist for algorithmic trading.
{ctx}
Trending:\n{tt}
Posted (do not repeat):\n{et}
Suggest 3 ideas: 1 Short+2 Long. Titles above 75. Hooks result-first no Hi.
Return ONLY valid JSON no markdown:
{{"date":"{datetime.now().strftime('%Y-%m-%d')}","suggestions":[
{{"id":1,"format":"short","topic":"","why_now":"","title":"","title_score":80,"hook":"","show":"","hide":"","funnel":"ea","cta":"","thumb_text":"","tags":["t1","t2","t3","t4","t5"]}},
{{"id":2,"format":"long_form","topic":"","why_now":"","title":"","title_score":85,"hook":"","show":"","hide":"","funnel":"ea","cta":"","thumb_text":"","tags":["t1","t2","t3","t4","t5"]}},
{{"id":3,"format":"long_form","topic":"","why_now":"","title":"","title_score":82,"hook":"","show":"","hide":"","funnel":"ea","cta":"","thumb_text":"","tags":["t1","t2","t3","t4","t5"]}}
]}}
""",3000)


def ai_score(model,title,hook,ctx,real_ctr=None,real_ret=None):
    is_short=len(hook.split())<130 if hook else False
    fmt_note='SHORT — emotional hook most critical.' if is_short else 'LONG FORM — all dimensions equal.'
    cal=f'Real CTR:{real_ctr}%. Retention:{real_ret}%. Calibrate.' if real_ctr else ''
    hs_=f'Score this hook:\n{hook}' if hook else 'No hook.'
    return call_gemini(model,f"""
YouTube growth expert for algorithmic trading.
{ctx}
Format:{fmt_note}
Title:{title}
{hs_}
{cal}
Score title 0-100: ctr_potential keyword_strength emotional_hook niche_fit pattern_match (each 20).
Score hook 0-100: speed_to_value result_first pattern_interrupt audience_targeting curiosity_gap (each 20).
5 title variations. 3 hook rewrites TTS-ready result-first never Hi.
Return ONLY valid JSON no markdown:
{{"title":"{title}","detected_format":"short or long_form","title_score":72,"title_breakdown":{{"ctr_potential":15,"keyword_strength":18,"emotional_hook":12,"niche_fit":17,"pattern_match":10}},"title_diagnosis":"","hook_score":45,"hook_breakdown":{{"speed_to_value":7,"result_first":5,"pattern_interrupt":8,"audience_targeting":12,"curiosity_gap":13}},"hook_diagnosis":"","calibration_note":null,"title_variations":[{{"type":"Personal story","title":"","why":""}},{{"type":"Number result","title":"","why":""}},{{"type":"Urgency fear","title":"","why":""}},{{"type":"Search optimized","title":"","why":""}},{{"type":"Controversy","title":"","why":""}}],"best_title":"","best_title_reason":"","hook_rewrites":[{{"version":"A","type":"Ultra-fast","script":"","why":""}},{{"version":"B","type":"Story-driven","script":"","why":""}},{{"version":"C","type":"Controversy","script":"","why":""}}],"best_hook_version":"A","best_hook_reason":"","thumbnail_concept":""}}
""",3000)


def ai_thumbnail_prompt(model, title, key_result, style='dark'):
    return call_gemini(model, f"""
You are a thumbnail designer for algorithmic trading YouTube.
Video title: {title}
Key result: {key_result}
Style: {style}
Current channel CTR: 2.5% — need to reach 4%+
Return ONLY valid JSON no markdown:
{{"image_prompt":"detailed prompt for image generation","main_text":"max 3 words","sub_text":"2-3 words or null","color_scheme":"hex colors","layout":"description","predicted_ctr":"range","canva_steps":"numbered steps to build in Canva"}}
""", 800)


def generate_thumbnail_image(prompt_text):
    try:
        encoded = requests.utils.quote(prompt_text[:500])
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200: return resp.content
    except Exception: pass
    return None


def ai_extract_shorts_from_long(model, long_script, ctx, funnel='ea'):
    return call_gemini(model, f"""
You are a YouTube Shorts strategist for algorithmic trading.
{ctx}
Original Long Script:
{long_script[:4000]}

Extract 3 completely different Shorts from this long script. Each Short must focus on a distinct concept, trap, or result from the original.
Rules:
- Format: UNDER 60 seconds (100-130 words each)
- Hook: First sentence MUST be the result/bold claim. Never Hi/Welcome.
- Structure: Hook (0-3s) -> Value/Proof (3-40s) -> CTA (40-55s)
- Include visual cues for each segment
- Funnel: {funnel}

Return ONLY valid JSON no markdown:
{{"shorts":[
  {{"title":"", "title_score":85, "hook":"", "script":"", "description":"", "tags":["t1","t2","t3"], "visual_plan":{{"hook_visual":"","value_visual":"","cta_visual":""}}, "why_it_works":""}},
  {{"title":"", "title_score":82, "hook":"", "script":"", "description":"", "tags":["t1","t2","t3"], "visual_plan":{{"hook_visual":"","value_visual":"","cta_visual":""}}, "why_it_works":""}},
  {{"title":"", "title_score":80, "hook":"", "script":"", "description":"", "tags":["t1","t2","t3"], "visual_plan":{{"hook_visual":"","value_visual":"","cta_visual":""}}, "why_it_works":""}}
]}}
""", 3500)


# ════════════════════════════════════════════════════════════
# YOUTUBE TRANSCRIPT (FIXED)
# ════════════════════════════════════════════════════════════

def extract_youtube_transcript(video_url: str):
    """
    Robust YouTube transcript extractor using Object-Oriented API (v0.6+ compatible).
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        video_id = None
        if "youtube.com/watch?v=" in video_url:
            video_id = video_url.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in video_url:
            video_id = video_url.split("/shorts/")[-1].split("?")[0]

        if not video_id:
            return None, "Could not extract video ID from URL"

        # Get list of all transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        try:
            # Step 1: Try to find English
            transcript = transcript_list.find_transcript(['en', 'en-US'])
            data = transcript.fetch()
        except Exception:
            # Step 2: If no English, take the first available and translate to English
            first_transcript = next(iter(transcript_list), None)
            if not first_transcript:
                return None, "No captions available for this video."
            
            try:
                translated = first_transcript.translate('en')
                data = translated.fetch()
            except Exception:
                return None, "Found captions but translation failed."

        full_text = " ".join([entry['text'] for entry in data])
        full_text = re.sub(r'\s+', ' ', full_text).strip()

        if len(full_text) < 50:
            return None, "Transcript too short."

        video_title = "YouTube Video"
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            resp = requests.get(oembed_url, timeout=5)
            if resp.status_code == 200:
                video_title = resp.json().get('title', 'YouTube Video')
        except:
            pass

        return full_text, video_title

    except Exception as e:
        return None, f"Error: {str(e)}"


def ai_extract_shorts_from_youtube_url(model, youtube_url, ctx, funnel='ea'):
    transcript, title_or_error = extract_youtube_transcript(youtube_url)
    if not transcript:
        return None, title_or_error
    result = ai_extract_shorts_from_long(model, transcript, ctx, funnel)
    return result, title_or_error


# ════════════════════════════════════════════════════════════
# REPORTS & UI
# ════════════════════════════════════════════════════════════

def generate_weekly_report(model, competitor_data, channel_config):
    trending = competitor_data.get('trending', [])
    ctx = build_context()
    tt = '\n'.join([f"- {v['title']} ({v.get('views_per_day',0):,.0f}/day)" for v in trending[:5]])
    return call_gemini(model, f"""
YouTube content strategist for algorithmic trading.
{ctx}
Trending this week:\n{tt}
Channel stats: {channel_config.get('subscribers',5)} subs, {channel_config.get('avg_ctr',2.5)}% CTR, {channel_config.get('watch_hours',1.4)}h watch time.
Generate a complete Monday morning content report.
Return ONLY valid JSON no markdown:
{{"report_date":"{datetime.now().strftime('%Y-%m-%d')}","weekly_summary":"2 sentences on channel status","top_3_video_ideas":[{{"rank":1,"title":"","hook":"","why_this_week":"","funnel":"ea","estimated_virality":85}},{{"rank":2,"title":"","hook":"","why_this_week":"","funnel":"saas","estimated_virality":80}},{{"rank":3,"title":"","hook":"","why_this_week":"","funnel":"course","estimated_virality":78}}],"this_week_priorities":["priority 1","priority 2","priority 3","priority 4"],"thumbnail_fix":"which existing thumbnail to fix and why","ctr_diagnosis":"current CTR analysis and fix","retention_diagnosis":"current retention analysis and fix"}}
""", 1500)


def send_email_report(report_data, email):
    try:
        resend_key = st.secrets.get("RESEND_API_KEY", "")
        if not resend_key or not email: return False
        html = f"""
        <div style='font-family:sans-serif;max-width:600px;margin:0 auto;background:#111318;color:#e8eaf0;padding:2rem;border-radius:12px;'>
            <h1 style='color:#00e5a0;'>⚡ AlgoQuant Weekly Report</h1>
            <p style='color:#6b7280;'>{report_data.get('report_date','')}</p>
            <h2 style='color:#e8eaf0;'>Channel Status</h2><p>{report_data.get('weekly_summary','')}</p>
            <h2 style='color:#e8eaf0;'>Top 3 Video Ideas This Week</h2>
            {''.join([f"<div style='background:#1e2229;border-radius:8px;padding:1rem;margin-bottom:0.75rem;'><div style='font-weight:700;color:#00e5a0;'>#{idea['rank']} — {idea['title']}</div><div style='color:#9ca3af;font-size:0.85rem;margin-top:4px;'>{idea['hook']}</div></div>" for idea in report_data.get('top_3_video_ideas',[])])}
            <hr style='border-color:#1e2229;'><p style='color:#6b7280;font-size:0.75rem;'>AlgoQuant Studio</p>
        </div>
        """
        resp = requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": "AlgoQuant Studio <report@algoquant.studio>",
                  "to": [email], "subject": f"⚡ Weekly Content Report — {report_data.get('report_date','')}", "html": html})
        return resp.status_code == 200
    except Exception: return False

def score_badge(score):
    cls = 'score-green' if score>=75 else 'score-yellow' if score>=50 else 'score-red'
    em  = '🟢' if score>=75 else '🟡' if score>=50 else '🔴'
    return f"<span class='score-badge {cls}'>{em} {score}/100</span>"

def section(title):
    st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)

def step_box(title, body, border_color='var(--accent)'):
    st.markdown(f"<div class='step-box' style='border-left-color:{border_color};'><div style='font-size:0.82rem;font-weight:600;margin-bottom:3px;'>{title}</div><div style='font-size:0.78rem;color:#9ca3af;'>{body}</div></div>", unsafe_allow_html=True)

def video_card_html(v):
    ret_c = '#00e5a0' if v.get('retention',0)>=40 else '#ffd700' if v.get('retention',0)>=20 else '#ff4560'
    ctr_c = '#00e5a0' if v.get('ctr',0)>=4 else '#ffd700' if v.get('ctr',0)>=2 else '#ff4560'
    fmt_c = '#0066ff' if v.get('format','')=='Long' else '#00e5a0'
    ret_d = f"{v.get('retention',0)}%" if v.get('retention',0)>0 else '—'
    ctr_d = f"{v.get('ctr',0)}%" if v.get('ctr',0)>0 else '—'
    st.markdown(f"""
    <div class='video-card'>
        <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
            <div style='flex:1;'>
                <div style='font-size:0.85rem;font-weight:600;margin-bottom:6px;'>{v['title']}</div>
                <div style='display:flex;gap:1.2rem;flex-wrap:wrap;'>
                    <span style='font-size:0.75rem;color:#6b7280;'>👁 <b style='color:#e8eaf0;'>{v.get('views',0)}</b></span>
                    <span style='font-size:0.75rem;'>CTR <b style='color:{ctr_c};'>{ctr_d}</b></span>
                    <span style='font-size:0.75rem;'>Ret <b style='color:{ret_c};'>{ret_d}</b></span>
                </div>
            </div>
            <span style='font-size:0.65rem;font-weight:700;color:{fmt_c};border:1px solid {fmt_c};border-radius:4px;padding:2px 8px;margin-left:8px;'>{v.get('format','').upper()}</span>
        </div>
    </div>""", unsafe_allow_html=True)

DEFAULT_VIDEOS = [
    {'title':'Why Your Python Backtesting Is Lying to You','format':'Short','views':76,'ctr':2.5,'retention':37.5,'subs':2,'p3_score':None},
    {'title':'Bitcoin Strategy Backtesting Python','format':'Short','views':41,'ctr':0.0,'retention':47.5,'subs':0,'p3_score':None},
    {'title':'How to Validate Bitcoin Trading in 8 Minutes','format':'Long','views':75,'ctr':2.5,'retention':8.1,'subs':2,'p3_score':None},
    {'title':'3 Traps That Make Crypto Backtest Look Profitable','format':'Long','views':11,'ctr':2.8,'retention':0.0,'subs':1,'p3_score':None},
]

# ════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════

subs  = cfg.get('subscribers',5)
hours = cfg.get('watch_hours',1.4)
sp    = min(subs/1000*100,100)
hp    = min(hours/4000*100,100)

with st.sidebar:
    pic = user.get('picture','')
    name= user.get('name','Creator')
    if pic:
        st.markdown(f"<div style='display:flex;align-items:center;gap:0.75rem;padding:0.75rem 0 1.25rem;'><img src='{pic}' style='width:36px;height:36px;border-radius:50%;border:2px solid #00e5a0;'><div><div style='font-size:0.85rem;font-weight:600;'>{name}</div><div style='font-size:0.7rem;color:#6b7280;'>{user.get('email','')}</div></div></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='padding:0.75rem 0 1.25rem;'><div style='font-size:1.4rem;font-weight:700;color:#00e5a0;'>⚡ AlgoQuant</div><div style='font-size:0.72rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;'>Content Intelligence Studio</div></div>", unsafe_allow_html=True)

    page = st.radio("", ["🏠  Dashboard","🔍  Competitor Intel","📊  My Channel",
         "🏭  Video Factory","📁  History","📧  Weekly Report","⚙️  Settings"], label_visibility="collapsed")

    st.markdown("<hr style='border-color:#1e2229;margin:1rem 0;'>", unsafe_allow_html=True)
    section("Channel Status")
    c1,c2 = st.columns(2)
    with c1: st.markdown(f"<div style='text-align:center;'><div style='font-size:1.3rem;font-weight:700;color:#00e5a0;'>{subs}</div><div style='font-size:0.65rem;color:#6b7280;'>SUBS</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div style='text-align:center;'><div style='font-size:1.3rem;font-weight:700;color:#0066ff;'>{hours:.1f}h</div><div style='font-size:0.65rem;color:#6b7280;'>WATCH HRS</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-top:0.75rem;'><div style='font-size:0.7rem;color:#6b7280;margin-bottom:3px;'>Subs {sp:.1f}% to monetization</div><div style='background:#1e2229;border-radius:4px;height:4px;margin-bottom:8px;'><div style='background:#00e5a0;width:{sp}%;height:4px;border-radius:4px;'></div></div><div style='font-size:0.7rem;color:#6b7280;margin-bottom:3px;'>Watch hrs {hp:.3f}%</div><div style='background:#1e2229;border-radius:4px;height:4px;'><div style='background:#0066ff;width:{min(hp*50,100)}%;height:4px;border-radius:4px;'></div></div></div>", unsafe_allow_html=True)

    if is_logged_in() and has_oauth:
        st.markdown("<hr style='border-color:#1e2229;margin:1rem 0;'>", unsafe_allow_html=True)
        if st.button("🚪  Sign Out", use_container_width=True):
            for k in ['user','config','competitor_data','competitor_trending']:
                if k in st.session_state: del st.session_state[k]
            st.rerun()

# ════════════════════════════════════════════════════════════
# PAGES
# ════════════════════════════════════════════════════════════

def page_dashboard():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>Good morning, Creator ⚡</h1>", unsafe_allow_html=True)
    section("Monetization Progress")
    c1,c2,c3,c4 = st.columns(4)
    items = [(str(subs),"Subscribers",f"{sp:.1f}% of 1,000",'#00e5a0'),
             (f"{hours:.1f}h","Watch Hours",f"{hp:.3f}% of 4,000h",'#0066ff'),
             (f"{cfg.get('avg_ctr',2.5)}%","Avg CTR","Target: 4%+",'#ffd700' if cfg.get('avg_ctr',2.5)<4 else '#00e5a0'),
             (str(cfg.get('total_videos',4)),"Videos Posted","Keep posting",'#00e5a0')]
    for col,(val,lbl,sub,col_) in zip([c1,c2,c3,c4],items):
        with col: st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:{col_};'>{val}</div><div class='metric-lbl'>{lbl}</div><div style='font-size:0.7rem;color:#6b7280;margin-top:6px;'>{sub}</div></div>", unsafe_allow_html=True)

def page_competitor():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>🔍 Competitor Intelligence</h1>", unsafe_allow_html=True)
    yt_key = cfg.get('youtube_api_key','')
    with st.expander("⚙️  Channel list",expanded=False):
        channels_text=st.text_area("Channels (Name,ID per line)",value='\n'.join([f"{k},{v}" for k,v in DEFAULT_CHANNELS.items()]),height=100)
        vids_n=st.slider("Videos per channel",5,50,20)
    run_btn=st.button("🔍  Fetch Competitor Data",use_container_width=True)
    if 'competitor_data' in st.session_state and not run_btn:
        _show_competitor_results(st.session_state['competitor_data'])
        return
    if run_btn:
        if not yt_key: st.error("⚠️  Add YouTube API key in Settings."); return
        channels={}
        for line in channels_text.strip().split('\n'):
            parts=[p.strip() for p in line.split(',')]
            if len(parts)==2: channels[parts[0]]=parts[1]
        with st.spinner("Fetching..."):
            try:
                videos=fetch_competitor_videos(yt_key,channels,vids_n)
                results=analyze_patterns(videos)
                st.session_state['competitor_data']=results
                st.session_state['competitor_trending']=results.get('trending',[])
                st.success(f"✅  {results['total']} videos from {len(channels)} channels")
                _show_competitor_results(results)
            except Exception as e: st.error(f"Error: {e}")

def _show_competitor_results(results):
    st.markdown("<hr class='divider'>",unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    for col,(val,lbl) in zip([c1,c2,c3,c4],[(str(results['total']),"Total"),(str(results['long_count']),"Long"),(str(results['short_count']),"Shorts"),(str(results['success_count']),"Above 5k")]):
        with col: st.markdown(f"<div class='metric-card'><div class='metric-val'>{val}</div><div class='metric-lbl'>{lbl}</div></div>",unsafe_allow_html=True)
    st.markdown("<div style='margin:1.5rem 0;'></div>",unsafe_allow_html=True)
    left,right=st.columns(2)
    with left:
        section("🔥 Trending Now")
        for v in results.get('trending',[]):
            st.markdown(f"<div class='video-card'><div style='font-size:0.82rem;font-weight:600;margin-bottom:4px;'>{v['title'][:55]}</div><div style='font-size:0.72rem;color:#6b7280;'>{v['channel']} · {v['views']:,} · <span style='color:#00e5a0;'>{v['views_per_day']:,.0f}/day</span></div></div>",unsafe_allow_html=True)
    with right:
        section("🌲 Evergreen")
        for v in results.get('evergreen',[]):
            st.markdown(f"<div class='video-card'><div style='font-size:0.82rem;font-weight:600;margin-bottom:4px;'>{v['title'][:55]}</div><div style='font-size:0.72rem;color:#6b7280;'>{v['channel']} · {v['views']:,} · <span style='color:#ffd700;'>{v['views_per_day']:,.0f}/day</span></div></div>",unsafe_allow_html=True)

def page_analytics():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>📊 My Channel Analytics</h1>",unsafe_allow_html=True)
    section("Update Channel Stats")
    with st.form("channel_stats"):
        c1,c2,c3,c4=st.columns(4)
        with c1: new_s=st.number_input("Subscribers",min_value=0,value=cfg.get('subscribers',5))
        with c2: new_h=st.number_input("Watch Hours",min_value=0.0,value=float(cfg.get('watch_hours',1.4)),format="%.1f")
        with c3: new_c=st.number_input("Avg CTR %",min_value=0.0,value=float(cfg.get('avg_ctr',2.5)),format="%.1f")
        with c4: new_v=st.number_input("Total Videos",min_value=0,value=cfg.get('total_videos',4))
        if st.form_submit_button("💾  Save Stats",use_container_width=True):
            st.session_state['config'].update({'subscribers':new_s,'watch_hours':new_h,'avg_ctr':new_c,'total_videos':new_v})
            st.success("✅  Stats saved")

def page_factory():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>🏭 Video Factory</h1>",unsafe_allow_html=True)
    gemini_key=cfg.get('gemini_api_key','')
    if not gemini_key: st.warning("⚠️  Add Gemini API key in Settings."); return
    
    tab1,tab2,tab3,tab4,tab5=st.tabs(["🏭  Full Factory","💡  Auto Suggest","📊  Title Scorer","🖼️  Thumbnail Generator", "📐  Long → Shorts"])

    with tab1:
        section("Describe your video idea")
        col1,col2,col3=st.columns([3,1,1])
        with col1: idea=st.text_area("Idea",placeholder="e.g. Build a prop firm EA...",height=80,label_visibility='collapsed')
        with col2: fmt=st.selectbox("Format",["long","short"])
        with col3: funnel=st.selectbox("Funnel",list(FUNNEL_DESCRIPTIONS.keys()))
        if st.button("⚡  Run Video Factory",use_container_width=True) and idea.strip():
            model=get_model(); ctx=build_context()
            section("Step 1 — Virality Check")
            with st.spinner("Checking virality..."):
                try: vr=ai_virality(model,idea,fmt,funnel,ctx)
                except Exception as e: st.error(str(e)); return
            vs=vr['virality_score']
            st.markdown(f"<div class='metric-card'><div class='metric-val'>{vs}</div><div class='metric-lbl'>Virality Score</div></div>",unsafe_allow_html=True)
            
            section("Step 2 — Title & Hook")
            with st.spinner("Generating title and hook..."):
                try: th=ai_title_hook(model,idea,fmt,funnel,ctx)
                except Exception as e: st.error(str(e)); return
            st.markdown(f"<div class='metric-card'><div class='metric-lbl'>TITLE</div><div style='font-size:1.1rem;font-weight:700;margin:0.5rem 0;'>\"{th['title']}\"</div><div style='font-size:0.8rem;color:#6b7280;'>{score_badge(th['title_score'])}</div></div>",unsafe_allow_html=True)
            st.markdown(f"<div class='script-block'>{th['hook_script']}</div>",unsafe_allow_html=True)

            section("Step 3 — Full Script")
            if fmt == 'short':
                with st.spinner("Writing Short script..."):
                    script = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, fmt, 1)
            else:
                with st.spinner("Writing Part 1..."): p1 = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, fmt, 1)
                with st.spinner("Writing Part 2..."): p2 = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, fmt, 2, p1)
                script = p1 + "\n\n" + p2

            wc=len(script.split())
            st.markdown(f"<div class='script-block'>{script}</div>",unsafe_allow_html=True)
            st.download_button("⬇️  Download Script",script,file_name=f"script_{datetime.now().strftime('%Y%m%d')}.txt")

            section("Step 4 — Packaging")
            with st.spinner("Generating packaging..."): pk=ai_packaging(model,idea,th['title'],fmt,funnel,ctx)
            seo=pk.get('seo',{})
            tags_html=''.join([f"<span class='tag'>{t}</span>" for t in seo.get('tags',[])])
            st.markdown(f"<div class='step-box'>Tags: {tags_html}</div>",unsafe_allow_html=True)
            st.success("✅ Complete")

    with tab2:
        section("Auto Suggest")
        existing=[v['title'] for v in DEFAULT_VIDEOS]
        if st.button("💡  Generate 3 Ideas"):
            model=get_model(); ctx=build_context()
            with st.spinner("Generating..."): result=ai_suggestions(model,[],existing,ctx)
            for s in result.get('suggestions',[]):
                st.markdown(f"<div class='video-card'><b>{s['title']}</b><br>{s['hook']}</div>",unsafe_allow_html=True)

    with tab3:
        section("Title Scorer")
        score_title=st.text_input("Title")
        score_hook=st.text_area("Hook")
        if st.button("Score"):
            model=get_model(); ctx=build_context()
            with st.spinner("Scoring..."): result=ai_score(model,score_title,score_hook,ctx)
            st.markdown(f"<div class='metric-card'><b>Title:</b> {result['title_score']}/100<br><b>Hook:</b> {result['hook_score']}/100</div>",unsafe_allow_html=True)

    with tab4:
        section("Thumbnail Generator")
        th_title=st.text_input("Title",key="th_title")
        if st.button("Generate Brief"):
            model=get_model()
            with st.spinner("..."): brief=ai_thumbnail_prompt(model,th_title,"")
            st.json(brief)

    # ──  LONG → SHORTS EXTRACTOR ──
    with tab5:
        section("📐 Long Script → 3 Shorts Extractor")
        extract_mode = st.tabs(["🔗 YouTube URL", "📝 Paste Script"])
        
        with extract_mode[0]:
            st.markdown("Paste any YouTube video URL. We'll extract the transcript and generate 3 Shorts automatically.")
            youtube_url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...")
            col_f, col_b = st.columns([1, 3])
            with col_f: url_funnel = st.selectbox("Target Funnel", list(FUNNEL_DESCRIPTIONS.keys()), key="url_funnel")
            with col_b: extract_btn = st.button("⚡  Extract from YouTube", use_container_width=True)
            
            if extract_btn and youtube_url.strip():
                model = get_model()
                ctx = build_context()
                with st.spinner("🔍 Fetching transcript & analyzing..."):
                    result, title_or_error = ai_extract_shorts_from_youtube_url(model, youtube_url, ctx, url_funnel)
                
                if result and 'shorts' in result:
                    st.success(f"✅ Extracted from: {title_or_error}")
                    for i, s in enumerate(result['shorts'], 1):
                        st.markdown(f"**Short #{i}: {s.get('title','')}** ({s.get('title_score',0)}/100)")
                        st.markdown(f"**Hook:** {s.get('hook','')}")
                        st.markdown(f"**Script:** {s.get('script','')}")
                        st.divider()
                else:
                    st.error(f"❌ {title_or_error}")
        
        with extract_mode[1]:
            long_script_input = st.text_area("Paste Script", height=200)
            if st.button("Extract"):
                model=get_model(); ctx=build_context()
                with st.spinner("Analyzing..."): result=ai_extract_shorts_from_long(model, long_script_input, ctx)
                if result: st.json(result)

def page_history():
    st.markdown("<h1 style='font-size:1.8rem;'>📁 Video History</h1>",unsafe_allow_html=True)
    st.info("History view coming in next update.")

def page_weekly_report():
    st.markdown("<h1 style='font-size:1.8rem;'>📧 Weekly Report</h1>",unsafe_allow_html=True)
    if st.button("Generate"):
        model=get_model()
        with st.spinner("..."): report=generate_weekly_report(model,{'trending':[]},cfg)
        st.json(report)

def page_settings():
    st.markdown("<h1 style='font-size:1.8rem;'>⚙️ Settings</h1>",unsafe_allow_html=True)
    with st.form("settings"):
        gem_key=st.text_input("Gemini API Key",value=cfg.get('gemini_api_key',''),type="password")
        yt_key=st.text_input("YouTube API Key",value=cfg.get('youtube_api_key',''),type="password")
        if st.form_submit_button("💾  Save"):
            st.session_state['config'].update({'gemini_api_key':gem_key,'youtube_api_key':yt_key})
            st.success("✅ Saved")

# ════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════

if   "🏠" in page:  page_dashboard()
elif "🔍" in page:  page_competitor()
elif "📊" in page:  page_analytics()
elif "🏭" in page:  page_factory()
elif "📁" in page:  page_history()
elif "📧" in page:  page_weekly_report()
elif "⚙️" in page:  page_settings()


