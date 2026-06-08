"""
AlgoQuant Studio v2.1 — Full Production SaaS
Levels: Persistence (Supabase) + Auth (Google OAuth) + Auto Reports + Thumbnail Generator
+ SHORT FIX: Format-aware script generation
+ NEW FEATURE: Long Script → 3 Shorts Extractor with Visual Plans
Single file. Deploy: streamlit run algoquant_studio_v2.py
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
    return genai.GenerativeModel('gemini-3.1-flash-lite')


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
    """✅ FIXED: Now respects 'short' vs 'long' format."""
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
    result = call_gemini(model, f"""
You are a thumbnail designer for algorithmic trading YouTube.
Video title: {title}
Key result: {key_result}
Style: {style}
Current channel CTR: 2.5% — need to reach 4%+
Generate a detailed image generation prompt for this thumbnail.
It must work at small sizes (mobile), have high contrast, max 4 words of text visible.
Return ONLY valid JSON no markdown:
{{"image_prompt":"detailed prompt for image generation","main_text":"max 3 words","sub_text":"2-3 words or null","color_scheme":"hex colors","layout":"description","predicted_ctr":"range","canva_steps":"numbered steps to build in Canva"}}
""", 800)
    return result


def generate_thumbnail_image(prompt_text):
    try:
        encoded = requests.utils.quote(prompt_text[:500])
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200: return resp.content
    except Exception: pass
    return None


def ai_extract_shorts_from_long(model, long_script, ctx, funnel='ea'):
    """✅ NEW: Extract 3 distinct Shorts from a long script."""
    return call_gemini(model, f"""
You are a YouTube Shorts strategist for algorithmic trading.
{ctx}
Original Long Script:
{long_script[:4000]}  # Truncate for token limit if huge

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
# AUTOMATED REPORT & EMAIL
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
            <h2 style='color:#e8eaf0;'>Diagnostics</h2>
            <p><b>CTR:</b> {report_data.get('ctr_diagnosis','')}</p><p><b>Retention:</b> {report_data.get('retention_diagnosis','')}</p>
            <hr style='border-color:#1e2229;'><p style='color:#6b7280;font-size:0.75rem;'>AlgoQuant Studio</p>
        </div>
        """
        resp = requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": "AlgoQuant Studio <report@algoquant.studio>",
                  "to": [email], "subject": f"⚡ Weekly Content Report — {report_data.get('report_date','')}", "html": html})
        return resp.status_code == 200
    except Exception: return False


# ════════════════════════════════════════════════════════════
# UI HELPERS
# ════════════════════════════════════════════════════════════

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
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Your content intelligence dashboard.</p>", unsafe_allow_html=True)
    section("Monetization Progress")
    c1,c2,c3,c4 = st.columns(4)
    items = [(str(subs),"Subscribers",f"{sp:.1f}% of 1,000",'#00e5a0'),
             (f"{hours:.1f}h","Watch Hours",f"{hp:.3f}% of 4,000h",'#0066ff'),
             (f"{cfg.get('avg_ctr',2.5)}%","Avg CTR","Target: 4%+",'#ffd700' if cfg.get('avg_ctr',2.5)<4 else '#00e5a0'),
             (str(cfg.get('total_videos',4)),"Videos Posted","Keep posting",'#00e5a0')]
    for col,(val,lbl,sub,col_) in zip([c1,c2,c3,c4],items):
        with col: st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:{col_};'>{val}</div><div class='metric-lbl'>{lbl}</div><div style='font-size:0.7rem;color:#6b7280;margin-top:6px;'>{sub}</div></div>", unsafe_allow_html=True)
    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    left,right = st.columns([3,2])
    with left:
        section("This Week's Priority Actions")
        actions = [
            ("🔴","Fix thumbnail on 'How to Validate Bitcoin' video","CTR 2.5% — thumbnail says wrong topic. Redesign in Canva now."),
            ("🟡","Post 6 Shorts this week","Shorts retention 37-47% is healthy. Volume is the fix."),
            ("🟢","Run Video Factory — Prop Firm EA kill-switch","Virality 78, Title 92, Hook 94 — record this week."),
            ("🟡","Reply to every comment within 24h","Algorithm rewards engagement. Critical for new channels."),
            ("🟢","Run Competitor Intel Monday","Update trending topics for fresh auto-suggestions."),
        ]
        for em,t,d in actions:
            st.markdown(f"<div class='step-box'><div style='display:flex;align-items:center;gap:0.5rem;'><span>{em}</span><span style='font-size:0.85rem;font-weight:600;'>{t}</span></div><div style='font-size:0.75rem;color:#6b7280;margin-top:2px;padding-left:1.3rem;'>{d}</div></div>", unsafe_allow_html=True)
    with right:
        section("Your Videos")
        for v in DEFAULT_VIDEOS: video_card_html(v)
    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    section("Monday Morning Routine (30 min)")
    steps=[("1","Competitor Intel","Run Phase 1 — see what is trending"),("2","Update Analytics","Paste stats into My Channel"),("3","Auto Suggest","Get 3 video ideas from trends"),("4","Video Factory","Generate full package for best idea"),("5","Record & Post","OBS + Chatterbox + Shotcut + Upload")]
    cols=st.columns(5)
    for col,(num,t,d) in zip(cols,steps):
        with col: st.markdown(f"<div style='background:#111318;border:1px solid #1e2229;border-radius:12px;padding:1rem;text-align:center;'><div style='width:28px;height:28px;background:rgba(0,229,160,0.15);border:1px solid #00e5a0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 8px;font-size:0.75rem;font-weight:700;color:#00e5a0;'>{num}</div><div style='font-size:0.78rem;font-weight:600;margin-bottom:4px;'>{t}</div><div style='font-size:0.68rem;color:#6b7280;line-height:1.4;'>{d}</div></div>", unsafe_allow_html=True)


def page_competitor():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>🔍 Competitor Intelligence</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Track what works in your niche. Run every Monday.</p>", unsafe_allow_html=True)
    yt_key = cfg.get('youtube_api_key','')
    with st.expander("⚙️  Channel list",expanded=False):
        channels_text=st.text_area("Channels (Name,ID per line)",value='\n'.join([f"{k},{v}" for k,v in DEFAULT_CHANNELS.items()]),height=100)
        vids_n=st.slider("Videos per channel",5,50,20)
    col_btn,col_info=st.columns([1,3])
    with col_btn: run_btn=st.button("🔍  Fetch Competitor Data",use_container_width=True)
    with col_info: st.markdown("<div style='padding-top:0.5rem;font-size:0.8rem;color:#6b7280;'>Public data only. ~30 seconds.</div>",unsafe_allow_html=True)
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
                db_save('competitor_reports',{'user_id':user_id,'data':json.dumps(results),'channel_count':len(channels)},user_id)
                st.success(f"✅  {results['total']} videos from {len(channels)} channels — saved to history")
                _show_competitor_results(results)
            except Exception as e: st.error(f"Error: {e}")
    else:
        st.markdown("<div style='background:#111318;border:1px solid #1e2229;border-radius:12px;padding:2rem;text-align:center;margin-top:2rem;'><div style='font-size:2rem;margin-bottom:0.5rem;'>🔍</div><div style='font-size:1rem;font-weight:600;margin-bottom:0.5rem;'>Ready to fetch competitor data</div><div style='font-size:0.82rem;color:#6b7280;'>Add YouTube API key in Settings then click above.</div></div>",unsafe_allow_html=True)

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
            st.markdown(f"<div class='video-card'><div style='font-size:0.82rem;font-weight:600;margin-bottom:4px;'>{v['title'][:55]}</div><div style='font-size:0.72rem;color:#6b7280;'>{v['channel']} · {v['views']:,} · <span style='color:#00e5a0;'>{v['views_per_day']:,.0f}/day</span></div><a href='{v['url']}' target='_blank' style='font-size:0.68rem;color:#0066ff;text-decoration:none;'>Watch ↗</a></div>",unsafe_allow_html=True)
    with right:
        section("🌲 Evergreen")
        for v in results.get('evergreen',[]):
            st.markdown(f"<div class='video-card'><div style='font-size:0.82rem;font-weight:600;margin-bottom:4px;'>{v['title'][:55]}</div><div style='font-size:0.72rem;color:#6b7280;'>{v['channel']} · {v['views']:,} · <span style='color:#ffd700;'>{v['views_per_day']:,.0f}/day</span></div><a href='{v['url']}' target='_blank' style='font-size:0.68rem;color:#0066ff;text-decoration:none;'>Watch ↗</a></div>",unsafe_allow_html=True)
    section("🔑 Top Keywords")
    kw=''.join([f"<span class='tag'>{w}({c})</span>" for w,c in results.get('top_words',[])[:15]])
    st.markdown(f"<div style='line-height:2;'>{kw}</div>",unsafe_allow_html=True)
    section("🏆 Top 20 Videos")
    if results.get('top20'):
        df=pd.DataFrame(results['top20'])[['channel','title','views','views_per_day','days_old']]
        df.columns=['Channel','Title','Views','Views/Day','Age(days)']
        df['Views']=df['Views'].apply(lambda x:f"{x:,}")
        df['Views/Day']=df['Views/Day'].apply(lambda x:f"{x:,.0f}")
        st.dataframe(df,use_container_width=True,hide_index=True)


def page_analytics():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>📊 My Channel Analytics</h1>",unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Update every Monday from YouTube Studio.</p>",unsafe_allow_html=True)
    section("Update Channel Stats")
    with st.form("channel_stats"):
        c1,c2,c3,c4=st.columns(4)
        with c1: new_s=st.number_input("Subscribers",min_value=0,value=cfg.get('subscribers',5))
        with c2: new_h=st.number_input("Watch Hours",min_value=0.0,value=float(cfg.get('watch_hours',1.4)),format="%.1f")
        with c3: new_c=st.number_input("Avg CTR %",min_value=0.0,value=float(cfg.get('avg_ctr',2.5)),format="%.1f")
        with c4: new_v=st.number_input("Total Videos",min_value=0,value=cfg.get('total_videos',4))
        if st.form_submit_button("💾  Save Stats",use_container_width=True):
            st.session_state['config'].update({'subscribers':new_s,'watch_hours':new_h,'avg_ctr':new_c,'total_videos':new_v})
            db_save('channel_snapshots',{'subscribers':new_s,'watch_hours':new_h,'avg_ctr':new_c,'total_videos':new_v},user_id)
            st.success("✅  Stats saved and logged to history")
    st.markdown("<div style='margin:1.5rem 0;'></div>",unsafe_allow_html=True)
    section("Monetization Progress")
    sp2=min(cfg.get('subscribers',5)/1000*100,100)
    hp2=min(cfg.get('watch_hours',1.4)/4000*100,100)
    c1,c2=st.columns(2)
    with c1: st.markdown(f"<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span style='font-weight:600;'>Subscribers</span><span style='color:#00e5a0;font-weight:700;'>{cfg.get('subscribers',5):,}/1,000</span></div><div style='background:#1e2229;border-radius:6px;height:8px;'><div style='background:linear-gradient(90deg,#00e5a0,#00b377);width:{sp2}%;height:8px;border-radius:6px;'></div></div><div style='font-size:0.72rem;color:#6b7280;margin-top:6px;'>{sp2:.1f}% · Need {max(1000-cfg.get('subscribers',5),0):,} more</div></div>",unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span style='font-weight:600;'>Watch Hours</span><span style='color:#0066ff;font-weight:700;'>{cfg.get('watch_hours',1.4):.1f}/4,000h</span></div><div style='background:#1e2229;border-radius:6px;height:8px;'><div style='background:linear-gradient(90deg,#0066ff,#0044cc);width:{min(hp2*50,100):.2f}%;height:8px;border-radius:6px;'></div></div><div style='font-size:0.72rem;color:#6b7280;margin-top:6px;'>{hp2:.3f}% · Need {max(4000-cfg.get('watch_hours',1.4),0):.1f}h more</div></div>",unsafe_allow_html=True)
    st.markdown("<div style='margin:1.5rem 0;'></div>",unsafe_allow_html=True)
    section("Video Performance Tracker")
    for v in DEFAULT_VIDEOS: video_card_html(v)
    st.markdown("<div style='margin:1.5rem 0;'></div>",unsafe_allow_html=True)
    section("Automated Diagnosis")
    avg_ctr=cfg.get('avg_ctr',2.5)
    diags=[
        ("📈 CTR","🔴 Below 2% — thumbnail is #1 priority." if avg_ctr<2 else "🟡 2-4% — test stronger hooks and thumbnails." if avg_ctr<4 else "🟢 Above 4% — strong. Keep the formula."),
        ("⏱️ Long Form Retention","🔴 8.1% — CRITICAL. First sentence must deliver the result. Cut all setup. People leave in 45 seconds."),
        ("📡 Traffic Sources","45% from channel pages — organic not kicking in. Post more Shorts to reach the feed algorithm."),
        ("🔑 Root Cause","Hook mismatch. Title promises one thing, hook delivers a generic welcome. First sentence must be the result."),
    ]
    for t,d in diags: step_box(t,d)


def page_factory():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>🏭 Video Factory</h1>",unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>One idea in. Full video package out. Title · Hook · Script · Thumbnail · SEO · Shorts.</p>",unsafe_allow_html=True)
    gemini_key=cfg.get('gemini_api_key','')
    if not gemini_key:
        st.warning("⚠️  Add your Gemini API key in Settings.")
        return
    
    # ✅ UPDATED: Added 5th tab for Long → Shorts Extractor
    tab1,tab2,tab3,tab4,tab5=st.tabs(["🏭  Full Factory","💡  Auto Suggest","📊  Title Scorer","🖼️  Thumbnail Generator", "📐  Long → Shorts"])

    # ── FULL FACTORY ──
    with tab1:
        section("Describe your video idea")
        col1,col2,col3=st.columns([3,1,1])
        with col1: idea=st.text_area("Idea",placeholder="e.g. Build a prop firm EA in MQL5 that monitors daily drawdown and shuts down when FTMO limit is hit",height=80,label_visibility='collapsed')
        with col2: fmt=st.selectbox("Format",["long","short"])
        with col3: funnel=st.selectbox("Funnel",list(FUNNEL_DESCRIPTIONS.keys()))
        if st.button("⚡  Run Video Factory",use_container_width=True) and idea.strip():
            model=get_model()
            ctx=build_context()
            st.markdown("<hr class='divider'>",unsafe_allow_html=True)
            section("Step 1 — Virality Check")
            with st.spinner("Checking virality..."):
                try: vr=ai_virality(model,idea,fmt,funnel,ctx)
                except Exception as e: st.error(str(e)); return
            vs=vr['virality_score']
            vc='#00e5a0' if vs>=75 else '#ffd700' if vs>=60 else '#ff4560'
            vb=vr['breakdown']
            cols6=st.columns(6)
            for col,k,l in zip(cols6[:5],['audience_demand','trend_alignment','differentiation','creator_fit','monetization_fit'],['Audience','Trend','Different','Creator','Monetize']):
                with col:
                    v_=vb.get(k,0); c_='#00e5a0' if v_>=16 else '#ffd700' if v_>=12 else '#ff4560'
                    st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.2rem;color:{c_};'>{v_}/20</div><div class='metric-lbl'>{l}</div></div>",unsafe_allow_html=True)
            with cols6[5]: st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:{vc};'>{vs}</div><div class='metric-lbl'>Virality</div></div>",unsafe_allow_html=True)
            vdict_c='#00e5a0' if vr['verdict']=='approved' else '#ff4560'
            step_box(vr['verdict'].upper(),vr['verdict_reason'],vdict_c)
            if vr.get('better_angle'): step_box("💡 Better angle",vr['better_angle'],'#ffd700')
            if vr['verdict']=='rejected': st.warning("Update idea with better angle above and rerun."); return
            st.markdown("<hr class='divider'>",unsafe_allow_html=True)
            section("Step 2 — Title & Hook")
            with st.spinner("Generating title and hook..."):
                try: th=ai_title_hook(model,idea,fmt,funnel,ctx)
                except Exception as e: st.error(str(e)); return
            ts,hs=th['title_score'],th['hook_score']
            c1_,c2_=st.columns(2)
            with c1_:
                alts=''.join([f"<div style='font-size:0.78rem;padding:4px 0;border-bottom:1px solid #1e2229;'>{'🟢' if a['score']>=75 else '🟡'}({a['score']}) {a['title']}</div>" for a in th.get('alternative_titles',[])])
                st.markdown(f"<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span class='metric-lbl'>TITLE</span>{score_badge(ts)}</div><div style='font-size:1rem;font-weight:700;margin-bottom:8px;'>\"{th['title']}\"</div><div style='font-size:0.75rem;color:#6b7280;margin-bottom:8px;'>{th['title_reasoning']}</div>{alts}</div>",unsafe_allow_html=True)
            with c2_:
                st.markdown(f"<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span class='metric-lbl'>HOOK</span>{score_badge(hs)}</div><div style='font-size:0.82rem;color:#c9d1d9;line-height:1.7;font-family:\"JetBrains Mono\",monospace;'>{th['hook_script']}</div><div style='font-size:0.72rem;color:#6b7280;margin-top:8px;'>{th['hook_reasoning']}</div></div>",unsafe_allow_html=True)
            
            st.markdown("<hr class='divider'>",unsafe_allow_html=True)
            section("Step 3 — Full Script")
            
            # ✅ FIXED: Format-aware script generation
            if fmt == 'short':
                with st.spinner("Writing Short script (100-130 words)..."):
                    try: script = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, fmt, 1)
                    except Exception as e: st.error(str(e)); return
            else:
                with st.spinner("Writing script part 1 of 2..."):
                    try: p1 = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, fmt, 1)
                    except Exception as e: st.error(str(e)); return
                with st.spinner("Writing script part 2 of 2..."):
                    try: p2 = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, fmt, 2, p1)
                    except Exception: p2 = ""
                script = p1 + "\n\n" + p2

            wc=len(script.split()); est=round(wc/130)
            tts_fixes = {'MQL5':'Em Cue El Five','FTMO':'F T M O','MT5':'M T 5','NFP':'N F P','Sharpe':'Sharp','EURUSD':'Euro U S D','EA':'E A'}
            script_tts = script
            for k,v in tts_fixes.items(): script_tts = script_tts.replace(k,v)
            
            st.markdown(f"<div style='display:flex;gap:1rem;margin-bottom:0.75rem;'><span class='score-badge score-green'>📝 {wc} words</span><span class='score-badge score-green'>⏱️ ~{est} min</span><span class='score-badge score-yellow'>🔊 TTS-ready version below</span></div>",unsafe_allow_html=True)
            stab1,stab2=st.tabs(["📄  Original Script","🔊  TTS-Ready (Chatterbox)"])
            with stab1: st.markdown(f"<div class='script-block'>{script}</div>",unsafe_allow_html=True)
            with stab2:
                st.markdown("<div style='font-size:0.78rem;color:#6b7280;margin-bottom:0.5rem;'>Phonetics applied. Ready to paste into Chatterbox Cell 5.</div>",unsafe_allow_html=True)
                st.markdown(f"<div class='script-block'>{script_tts}</div>",unsafe_allow_html=True)
            col_dl1,col_dl2=st.columns(2)
            with col_dl1: st.download_button("⬇️  Download Script",script,file_name=f"script_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
            with col_dl2: st.download_button("⬇️  Download TTS Version",script_tts,file_name=f"script_tts_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
            
            st.markdown("<hr class='divider'>",unsafe_allow_html=True)
            section("Step 4 — Thumbnail · SEO · Shorts · CTA")
            with st.spinner("Generating packaging..."):
                try: pk=ai_packaging(model,idea,th['title'],fmt,funnel,ctx)
                except Exception as e: st.error(str(e)); return
            th_data=pk.get('thumbnail',{})
            seo=pk.get('seo',{})
            shorts=pk.get('shorts',[])
            cta=pk.get('cta_script','')
            rec=th_data.get('recommended','1')
            
            # ✅ FIXED: Thumbnail options rendering (no nested f-strings)
            tc1, tc2 = st.columns(2)
            for col, key in zip([tc1, tc2], ['option_1', 'option_2']):
                with col:
                    opt = th_data.get(key, {})
                    num = key.split('_')[1]
                    is_rec = rec == num
                    border = '#00e5a0' if is_rec else '#1e2229'
                    rec_tag = ' ⭐ RECOMMENDED' if is_rec else ''
                    colors_html = ''.join([f"<span style='display:inline-block;width:16px;height:16px;border-radius:3px;background:{c};margin-right:3px;vertical-align:middle;'></span>" for c in opt.get('colors', [])])
                    sub_text_html = f'<div style="font-size:0.75rem;color:#6b7280;margin-bottom:4px;">Sub: {opt.get("sub_text")}</div>' if opt.get('sub_text') else ''
                    card_html = (
                        f"<div class='metric-card' style='border-color:{border};'>"
                        f"<div style='font-size:0.72rem;font-weight:700;color:#6b7280;margin-bottom:8px;'>OPTION {num}{rec_tag}</div>"
                        f"<div style='font-size:0.9rem;font-weight:600;margin-bottom:4px;'>\"{opt.get('main_text','')}\"</div>"
                        f"{sub_text_html}"
                        f"<div style='font-size:0.75rem;color:#9ca3af;margin-bottom:6px;'>{opt.get('concept','')}</div>"
                        f"<div style='font-size:0.72rem;color:#6b7280;'>Visual: {opt.get('visual','')}</div>"
                        f"<div style='margin:8px 0;'>{colors_html}</div>"
                        f"<div style='font-size:0.7rem;color:#6b7280;border-top:1px solid #1e2229;padding-top:8px;'>{opt.get('canva_steps','')}</div>"
                        f"<div style='font-size:0.72rem;color:#00e5a0;margin-top:6px;font-weight:600;'>CTR target: {opt.get('predicted_ctr','')}</div>"
                        f"</div>"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                    
            section("SEO Package")
            tags_html=''.join([f"<span class='tag'>{t}</span>" for t in seo.get('tags',[])])
            st.markdown(f"<div class='step-box'><div style='font-size:0.78rem;font-weight:600;margin-bottom:6px;'>Description:</div><div style='font-size:0.78rem;color:#9ca3af;'>{seo.get('description_line1','')}</div><div style='font-size:0.78rem;color:#9ca3af;'>{seo.get('description_line2','')}</div><div style='margin-top:10px;'>{tags_html}</div></div>",unsafe_allow_html=True)
            if seo.get('chapters') and fmt=='long':
                ch_text='\n'.join([f"{c['time']} {c['title']}" for c in seo['chapters']])
                st.markdown(f"<div class='script-block' style='font-size:0.8rem;'>{ch_text}</div>",unsafe_allow_html=True)
            section("3 Shorts to Extract")
            for i,s in enumerate(shorts,1):
                st.markdown(f"<div class='video-card'><div style='display:flex;gap:0.5rem;align-items:center;margin-bottom:4px;'><span style='font-size:0.65rem;font-weight:700;color:#00e5a0;border:1px solid #00e5a0;border-radius:4px;padding:1px 6px;'>SHORT #{i}</span><span style='font-size:0.83rem;font-weight:600;'>{s.get('title','')}</span></div><div style='font-size:0.75rem;color:#9ca3af;margin-bottom:3px;'>Hook: {s.get('hook','')}</div><div style='font-size:0.72rem;color:#6b7280;'>Clip: {s.get('clip','')}</div></div>",unsafe_allow_html=True)
            section("CTA Script")
            st.markdown(f"<div class='script-block' style='font-size:0.82rem;'>{cta}</div>",unsafe_allow_html=True)
            db_save('video_history',{'user_id':user_id,'idea':idea,'format':fmt,'funnel':funnel,'title':th['title'],'title_score':ts,'hook_score':hs,'virality_score':vs,'word_count':wc,'script':script,'tags':json.dumps(seo.get('tags',[])),'status':'generated','real_ctr':None,'real_retention':None},user_id)
            st.markdown("<hr class='divider'>",unsafe_allow_html=True)
            st.markdown(f"<div style='background:rgba(0,229,160,0.05);border:1px solid rgba(0,229,160,0.2);border-radius:12px;padding:1.25rem;'><div style='font-size:0.9rem;font-weight:700;color:#00e5a0;margin-bottom:0.75rem;'>✅  Video Factory Complete — saved to History</div><div style='display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem;'><span style='font-size:0.8rem;color:#9ca3af;'>Virality <b style='color:#00e5a0;'>{vs}/100</b></span><span style='font-size:0.8rem;color:#9ca3af;'>Title <b style='color:#00e5a0;'>{ts}/100</b></span><span style='font-size:0.8rem;color:#00e5a0;'>Hook <b>{hs}/100</b></span><span style='font-size:0.8rem;color:#9ca3af;'>Script <b style='color:#e8eaf0;'>{wc} words</b></span><span style='font-size:0.8rem;color:#9ca3af;'>~{est} min</span></div><div style='font-size:0.8rem;color:#6b7280;line-height:1.8;'>1. Download TTS script → paste into Chatterbox &nbsp;·&nbsp; 2. Build thumbnail in Canva &nbsp;·&nbsp; 3. Record OBS &nbsp;·&nbsp; 4. Sync Shotcut &nbsp;·&nbsp; 5. Upload with SEO &nbsp;·&nbsp; 6. Come back to History to log real CTR</div></div>",unsafe_allow_html=True)

    # ── AUTO SUGGEST ──
    with tab2:
        section("Auto-suggest 3 video ideas from competitor trends")
        st.markdown("<div style='font-size:0.8rem;color:#6b7280;margin-bottom:1rem;'>Run Competitor Intel first for best results.</div>",unsafe_allow_html=True)
        existing=[v['title'] for v in DEFAULT_VIDEOS]
        if st.button("💡  Generate 3 Video Ideas",use_container_width=True):
            model=get_model(); ctx=build_context()
            trending=st.session_state.get('competitor_trending',[])
            if not trending:
                trending=[{'title':'AI trading bot Python','views_per_day':1200,'days_old':5},{'title':'FTMO prop firm algo','views_per_day':800,'days_old':10}]
                st.info("Using generic trends. Run Competitor Intel for better suggestions.")
            with st.spinner("Generating..."):
                try: result=ai_suggestions(model,trending,existing,ctx)
                except Exception as e: st.error(str(e)); return
            for s in result.get('suggestions',[]):
                fmt_=s.get('format','').upper().replace('_',' ')
                score=s.get('title_score',0)
                score_class = 'score-green' if score>=75 else 'score-yellow'
                fmt_c='#0066ff' if 'LONG' in fmt_ else '#00e5a0'
                tags_html=''.join([f"<span class='tag'>{t}</span>" for t in s.get('tags',[])])
                card_html = (
                    f"<div class='video-card' style='margin-bottom:1rem;'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;'>"
                    f"<div><span style='font-size:0.65rem;font-weight:700;color:{fmt_c};border:1px solid {fmt_c};border-radius:4px;padding:1px 6px;margin-right:6px;'>IDEA #{s.get('id')} · {fmt_}</span>"
                    f"<span class='score-badge {score_class}' style='font-size:0.65rem;'>Title {score}/100</span></div>"
                    f"<span class='funnel-badge'>{s.get('funnel','').upper()}</span></div>"
                    f"<div style='font-size:0.9rem;font-weight:700;margin-bottom:4px;'>\"{s.get('title','')}\"</div>"
                    f"<div style='font-size:0.78rem;color:#6b7280;margin-bottom:8px;'>{s.get('topic','')} · {s.get('why_now','')}</div>"
                    f"<div style='font-size:0.75rem;color:#9ca3af;background:#0d1117;border-radius:6px;padding:0.6rem 0.8rem;margin-bottom:8px;font-family:JetBrains Mono,monospace;'>{s.get('hook','')}</div>"
                    f"<div style='font-size:0.72rem;color:#6b7280;margin-bottom:4px;'>📺 {s.get('show','')}</div>"
                    f"<div style='font-size:0.72rem;color:#6b7280;margin-bottom:4px;'>🔒 {s.get('hide','')}</div>"
                    f"<div style='font-size:0.72rem;color:#6b7280;margin-bottom:8px;'>📢 {s.get('cta','')}</div>"
                    f"<div>{tags_html}</div></div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)
            st.info("💡 Pick one idea, go to Full Factory tab, paste it as your idea.")

    # ── TITLE SCORER ──
    with tab3:
        section("Score a title and hook before you record")
        score_title=st.text_input("Title",placeholder="e.g. I Built a Prop Firm EA That Passed FTMO in 30 Days")
        score_hook=st.text_area("Hook (optional)",height=100,placeholder="Paste your opening 30 seconds...")
        c1_,c2_=st.columns(2)
        with c1_: rctr=st.number_input("Real CTR % (if posted)",min_value=0.0,value=0.0,format="%.1f")
        with c2_: rret=st.number_input("Real Retention % (if posted)",min_value=0.0,value=0.0,format="%.1f")
        if st.button("📊  Score Title & Hook",use_container_width=True) and score_title.strip():
            model=get_model(); ctx=build_context()
            with st.spinner("Scoring..."):
                try: result=ai_score(model,score_title,score_hook,ctx,rctr if rctr>0 else None,rret if rret>0 else None)
                except Exception as e: st.error(str(e)); return
            ts,hs=result.get('title_score',0),result.get('hook_score',0)
            c1_m,c2_m=st.columns(2)
            with c1_m: 
                title_emoji = '🟢' if ts>=75 else '🟡' if ts>=50 else '🔴'
                st.markdown(f"<div class='metric-card'><div class='metric-val'>{title_emoji} {ts}/100</div><div class='metric-lbl'>Title Score</div></div>",unsafe_allow_html=True)
            with c2_m: 
                hook_emoji = '🟢' if hs>=75 else '🟡' if hs>=50 else '🔴'
                st.markdown(f"<div class='metric-card'><div class='metric-val'>{hook_emoji} {hs}/100</div><div class='metric-lbl'>Hook Score</div></div>",unsafe_allow_html=True)
            step_box("Title Diagnosis",result.get('title_diagnosis',''))
            step_box("Hook Diagnosis",result.get('hook_diagnosis',''))
            if result.get('calibration_note'): step_box("📐 Calibration Note",result['calibration_note'],'#ffd700')
            section("Best Title")
            st.markdown(f"<div style='background:rgba(0,229,160,0.05);border:1px solid rgba(0,229,160,0.3);border-radius:8px;padding:1rem;'><div style='font-size:1rem;font-weight:700;margin-bottom:6px;'>\"{result.get('best_title','')}\"</div><div style='font-size:0.78rem;color:#6b7280;'>{result.get('best_title_reason','')}</div></div>",unsafe_allow_html=True)
            section("All 5 Variations")
            for v in result.get('title_variations',[]): step_box(f"[{v['type']}] {v['title']}",v['why'])
            if result.get('hook_rewrites'):
                best_v=result.get('best_hook_version','A')
                section("Hook Rewrites")
                for hw in result['hook_rewrites']:
                    is_best=hw['version']==best_v
                    border='#00e5a0' if is_best else '#1e2229'
                    label=" ⭐ USE THIS" if is_best else ""
                    st.markdown(f"<div class='step-box' style='border-left-color:{border};margin-bottom:0.5rem;'><div style='font-size:0.72rem;font-weight:700;color:#6b7280;margin-bottom:4px;'>VERSION {hw['version']} — {hw['type']}{label}</div><div class='script-block' style='font-size:0.78rem;padding:0.6rem 0.8rem;margin-bottom:6px;'>{hw['script']}</div><div style='font-size:0.72rem;color:#6b7280;'>{hw['why']}</div></div>",unsafe_allow_html=True)
            step_box("🖼️ Thumbnail Concept",result.get('thumbnail_concept',''))

    # ── THUMBNAIL GENERATOR ──
    with tab4:
        section("AI Thumbnail Generator")
        st.markdown("<div style='font-size:0.82rem;color:#6b7280;margin-bottom:1rem;'>Generates a thumbnail brief + actual image using AI. Free via Pollinations AI.</div>",unsafe_allow_html=True)
        th_title=st.text_input("Video title",placeholder="I Built a Prop Firm EA That Passed FTMO in 30 Days",key="th_title")
        th_result_text=st.text_input("Key result to show",placeholder="EA passed FTMO, 30 days, automated, risk managed",key="th_result")
        th_style=st.selectbox("Style",["dark minimal","dark dramatic","green success","red warning","split screen"])
        col_brief,col_gen=st.columns(2)
        with col_brief: brief_btn=st.button("📋  Generate Design Brief",use_container_width=True)
        with col_gen:   gen_btn  =st.button("🖼️  Generate Thumbnail Image",use_container_width=True)
        if brief_btn and th_title:
            model=get_model(); ctx=build_context()
            with st.spinner("Generating thumbnail brief..."):
                try: th_brief=ai_thumbnail_prompt(model,th_title,th_result_text,th_style)
                except Exception as e: st.error(str(e)); return
            colors_html=''.join([f"<span style='display:inline-block;width:20px;height:20px;border-radius:4px;background:{c};margin-right:4px;vertical-align:middle;'></span>" for c in th_brief.get('color_scheme','#000').split(',')])
            sub_text_brief = f"<div style='font-size:0.85rem;color:#6b7280;margin-bottom:8px;'>Sub text: \"{th_brief.get('sub_text','')}\"</div>" if th_brief.get('sub_text') else ''
            st.markdown(f"""
            <div class='metric-card' style='margin-top:1rem;'>
                <div style='font-size:0.72rem;color:#6b7280;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.08em;'>Thumbnail Design Brief</div>
                <div style='font-size:1.1rem;font-weight:700;margin-bottom:4px;'>Main text: "{th_brief.get('main_text','')}"</div>
                {sub_text_brief}
                <div style='font-size:0.78rem;color:#9ca3af;margin-bottom:8px;'>Layout: {th_brief.get('layout','')}</div>
                <div style='margin-bottom:12px;'>{colors_html}</div>
                <div style='font-size:0.75rem;color:#ffd700;margin-bottom:8px;'>CTR target: {th_brief.get('predicted_ctr','')}</div>
                <div style='font-size:0.78rem;font-weight:600;margin-bottom:6px;'>Canva steps:</div>
                <div style='font-size:0.75rem;color:#9ca3af;'>{th_brief.get('canva_steps','')}</div>
            </div>
            """, unsafe_allow_html=True)
            st.session_state['th_brief'] = th_brief
        if gen_btn and th_title:
            brief=st.session_state.get('th_brief',{})
            img_prompt=brief.get('image_prompt','') if brief else f"YouTube thumbnail dark background {th_title} {th_result_text} bold text high contrast professional trading"
            if not img_prompt:
                img_prompt=f"YouTube thumbnail for algorithmic trading video titled {th_title}, dark background, bold text, high contrast, professional, {th_style}"
            with st.spinner("Generating thumbnail image... (free via Pollinations AI, takes 15-20 seconds)"):
                img_bytes=generate_thumbnail_image(img_prompt)
                if img_bytes:
                    st.image(img_bytes, caption="AI Generated Thumbnail — download and edit in Canva", use_column_width=True)
                    st.download_button("⬇️  Download Thumbnail",img_bytes,file_name=f"thumbnail_{datetime.now().strftime('%Y%m%d_%H%M')}.jpg",mime="image/jpeg")
                    st.info("💡 This is a starting point. Open in Canva, add your bold text overlay and adjust colors.")
                else:
                    st.error("Image generation failed. Try the design brief instead and build in Canva manually.")

    # ── 📐 LONG → SHORTS EXTRACTOR (NEW) ──
    with tab5:
        section("📐 Long Script → 3 Shorts Extractor")
        st.markdown("<div style='font-size:0.8rem;color:#6b7280;margin-bottom:1rem;'>Paste your long-form script below. AI will extract 3 distinct, high-retention Shorts with titles, hooks, scripts, SEO descriptions, and frame-by-frame visual plans.</div>", unsafe_allow_html=True)
        
        long_script_input = st.text_area("Paste Full Long Video Script", height=250, placeholder="Paste your complete 10-20 minute script here...")
        col_f, col_b = st.columns([1, 3])
        with col_f: ext_funnel = st.selectbox("Target Funnel", list(FUNNEL_DESCRIPTIONS.keys()), key="ext_funnel")
        with col_b: 
            if st.button("⚡  Extract 3 Shorts", use_container_width=True) and long_script_input.strip():
                model = get_model()
                ctx = build_context()
                with st.spinner("Analyzing script & extracting Shorts..."):
                    try:
                        result = ai_extract_shorts_from_long(model, long_script_input, ctx, ext_funnel)
                    except Exception as e:
                        st.error(f"Extraction failed: {e}")
                        return
                
                if 'shorts' in result:
                    for i, s in enumerate(result['shorts'], 1):
                        st.markdown(f"<hr class='divider'>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1rem;font-weight:700;color:#00e5a0;margin-bottom:0.5rem;'>🎬 SHORT #{i}: {s.get('title','')} <span class='score-badge score-green' style='margin-left:8px;'>{s.get('title_score',0)}/100</span></div>", unsafe_allow_html=True)
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"<div class='metric-card'><div class='metric-lbl'>HOOK (0-3s)</div><div style='font-size:0.85rem;color:#c9d1d9;line-height:1.5;font-family:\"JetBrains Mono\",monospace;margin-top:4px;'>{s.get('hook','')}</div></div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='metric-card' style='margin-top:0.75rem;'><div class='metric-lbl'>FULL SCRIPT (100-130 words)</div><div style='font-size:0.8rem;color:#c9d1d9;line-height:1.7;font-family:\"JetBrains Mono\",monospace;margin-top:4px;max-height:200px;overflow-y:auto;'>{s.get('script','')}</div></div>", unsafe_allow_html=True)
                        with c2:
                            vp = s.get('visual_plan', {})
                            st.markdown(f"""
                            <div class='metric-card'>
                                <div class='metric-lbl'>🎥 VISUAL PLAN</div>
                                <div style='margin-top:8px;font-size:0.78rem;color:#9ca3af;'>
                                <div style='margin-bottom:6px;'><b style='color:#00e5a0;'>0-3s (Hook):</b> {vp.get('hook_visual','Show result/chart spike')}</div>
                                <div style='margin-bottom:6px;'><b style='color:#0066ff;'>3-40s (Value):</b> {vp.get('value_visual','Screen recording/code walkthrough')}</div>
                                <div><b style='color:#ffd700;'>40-55s (CTA):</b> {vp.get('cta_visual','Point to description/link overlay')}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            tags_html = ''.join([f"<span class='tag'>{t}</span>" for t in s.get('tags', [])])
                            st.markdown(f"<div class='step-box' style='margin-top:0.75rem;'><div style='font-size:0.78rem;font-weight:600;margin-bottom:4px;'>📝 SEO DESCRIPTION</div><div style='font-size:0.75rem;color:#9ca3af;'>{s.get('description','')}</div><div style='margin-top:6px;'>{tags_html}</div></div>", unsafe_allow_html=True)
                        
                        col_dl, _ = st.columns([1, 3])
                        with col_dl:
                            st.download_button(f"⬇️ Download Short #{i}", s.get('script',''), file_name=f"short_{i}_{datetime.now().strftime('%Y%m%d')}.txt", key=f"dl_short_{i}")
                    
                    st.success("✅  3 Shorts extracted! Save them and record one per day to drive traffic back to your long video.")
                else:
                    st.error("AI returned invalid format. Try again.")
            elif not long_script_input.strip():
                st.info("👉 Paste your long script above to start extraction.")


def page_history():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>📁 Video History</h1>",unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Every video you generate is saved here. Update real metrics to calibrate the model.</p>",unsafe_allow_html=True)
    records=db_fetch('video_history',user_id,50)
    if not records:
        st.markdown("<div style='background:#111318;border:1px solid #1e2229;border-radius:12px;padding:2rem;text-align:center;margin-top:2rem;'><div style='font-size:2rem;margin-bottom:0.5rem;'>📁</div><div style='font-size:1rem;font-weight:600;margin-bottom:0.5rem;'>No videos yet</div><div style='font-size:0.82rem;color:#6b7280;'>Run the Video Factory to generate your first video package. It will be saved here automatically.</div></div>",unsafe_allow_html=True)
        return
    section(f"{len(records)} videos generated")
    for r in records:
        ts_=r.get('title_score',0)
        hs_=r.get('hook_score',0)
        vs_=r.get('virality_score',0)
        real_ctr=r.get('real_ctr')
        real_ret=r.get('real_retention')
        created=r.get('created_at','')[:10] if r.get('created_at') else ''
        with st.expander(f"{'✅' if real_ctr else '⏳'} {r.get('title','Untitled')} — {created}"):
            col1,col2,col3,col4=st.columns(4)
            with col1: st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.3rem;'>{'🟢' if vs_>=75 else '🟡'} {vs_}</div><div class='metric-lbl'>Virality</div></div>",unsafe_allow_html=True)
            with col2: st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.3rem;'>{'🟢' if ts_>=75 else '🟡'} {ts_}</div><div class='metric-lbl'>Title Score</div></div>",unsafe_allow_html=True)
            with col3: st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.3rem;'>{'🟢' if hs_>=75 else '🟡'} {hs_}</div><div class='metric-lbl'>Hook Score</div></div>",unsafe_allow_html=True)
            with col4:
                ctr_c_='#00e5a0' if real_ctr and real_ctr>=4 else '#ffd700' if real_ctr else '#6b7280'
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.3rem;color:{ctr_c_};'>{f'{real_ctr}%' if real_ctr else '—'}</div><div class='metric-lbl'>Real CTR</div></div>",unsafe_allow_html=True)
            if r.get('script'):
                if st.checkbox("Show script",key=f"script_{r.get('id','')}"):
                    st.markdown(f"<div class='script-block' style='max-height:300px;overflow-y:auto;'>{r['script']}</div>",unsafe_allow_html=True)
                    st.download_button("⬇️  Download Script",r['script'],file_name=f"script_{r.get('id','')}.txt",key=f"dl_{r.get('id','')}")
            st.markdown("<div class='section-header'>Update Real Performance (after 7 days)</div>",unsafe_allow_html=True)
            with st.form(f"update_{r.get('id','')}"):
                uc1,uc2,uc3=st.columns(3)
                with uc1: new_ctr=st.number_input("Real CTR %",min_value=0.0,value=float(real_ctr) if real_ctr else 0.0,format="%.1f",key=f"ctr_{r.get('id','')}")
                with uc2: new_ret=st.number_input("Real Retention %",min_value=0.0,value=float(real_ret) if real_ret else 0.0,format="%.1f",key=f"ret_{r.get('id','')}")
                with uc3: new_views=st.number_input("Real Views",min_value=0,value=r.get('real_views',0) or 0,key=f"views_{r.get('id','')}")
                if st.form_submit_button("💾  Save Real Metrics",use_container_width=True):
                    db_update('video_history',r['id'],{'real_ctr':new_ctr,'real_retention':new_ret,'real_views':new_views,'status':'posted'})
                    st.success("✅  Metrics saved — model will use this for calibration")
                    st.rerun()
            if real_ctr and ts_:
                gap=real_ctr - (ts_/100*10)
                if gap > 1: step_box("📐 Calibration","Model score predicted well — CTR above expectation. Title formula is working.",'#00e5a0')
                elif gap < -1: step_box("📐 Calibration","Model over-predicted CTR. Thumbnail may be the weak point — score was higher than real performance.",'#ff4560')
                else: step_box("📐 Calibration","Model score aligned with real CTR. Calibration is accurate for this type of title.",'#ffd700')


def page_weekly_report():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>📧 Weekly Report</h1>",unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Generate your Monday morning content briefing. Get it in your inbox automatically.</p>",unsafe_allow_html=True)
    gemini_key=cfg.get('gemini_api_key','')
    if not gemini_key:
        st.warning("⚠️  Add Gemini API key in Settings.")
        return
    section("Email Setup")
    with st.form("email_setup"):
        email_input=st.text_input("Your email for weekly reports",value=cfg.get('email',''),placeholder="you@gmail.com")
        if st.form_submit_button("💾  Save Email"):
            st.session_state['config']['email']=email_input
            db_save('user_configs',{'config_json':st.session_state['config']},user_id)
            st.success("✅  Email saved")
    st.markdown("<hr class='divider'>",unsafe_allow_html=True)
    section("Generate This Week's Report")
    col_gen,col_send=st.columns(2)
    with col_gen: gen_report=st.button("📊  Generate Report Now",use_container_width=True)
    with col_send: send_report=st.button("📧  Send to My Email",use_container_width=True,disabled=not cfg.get('email',''))
    if gen_report:
        model=get_model()
        competitor_data=st.session_state.get('competitor_data',{})
        if not competitor_data:
            st.info("No competitor data found. Run Competitor Intel first for better report quality.")
            competitor_data={'trending':[{'title':'FTMO prop firm algo','views_per_day':800,'days_old':5}]}
        with st.spinner("Generating your Monday morning report..."):
            try: report=generate_weekly_report(model,competitor_data,cfg)
            except Exception as e: st.error(str(e)); return
        st.session_state['weekly_report']=report
        st.markdown(f"""
        <div style='background:rgba(0,229,160,0.05);border:1px solid rgba(0,229,160,0.2);border-radius:12px;padding:1.5rem;margin-top:1rem;'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;'>
                <div style='font-size:1rem;font-weight:700;color:#00e5a0;'>⚡ Weekly Content Report</div>
                <div style='font-size:0.75rem;color:#6b7280;'>{report.get('report_date','')}</div>
            </div>
            <div style='font-size:0.85rem;color:#9ca3af;margin-bottom:1.5rem;'>{report.get('weekly_summary','')}</div>
        </div>
        """, unsafe_allow_html=True)
        section("Top 3 Video Ideas This Week")
        for idea in report.get('top_3_video_ideas',[]):
            score_c='#00e5a0' if idea.get('estimated_virality',0)>=80 else '#ffd700'
            st.markdown(f"""
            <div class='video-card'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;'>
                    <div style='font-size:0.9rem;font-weight:700;'>#{idea.get('rank')} {idea.get('title','')}</div>
                    <span style='font-size:0.7rem;font-weight:700;color:{score_c};border:1px solid {score_c};border-radius:4px;padding:1px 6px;'>Virality {idea.get('estimated_virality',0)}</span>
                </div>
                <div style='font-size:0.78rem;color:#9ca3af;font-family:JetBrains Mono,monospace;margin-bottom:6px;'>{idea.get('hook','')}</div>
                <div style='font-size:0.72rem;color:#6b7280;'>{idea.get('why_this_week','')} · Funnel: {idea.get('funnel','')}</div>
            </div>
            """, unsafe_allow_html=True)
        section("This Week Priorities")
        for p in report.get('this_week_priorities',[]): step_box("→",p)
        section("Diagnostics")
        step_box("CTR",report.get('ctr_diagnosis',''))
        step_box("Retention",report.get('retention_diagnosis',''))
        step_box("Thumbnail Fix",report.get('thumbnail_fix',''),'#ffd700')
        db_save('weekly_reports',{'user_id':user_id,'report':json.dumps(report)},user_id)
        st.success("✅  Report saved to history")
    if send_report:
        report=st.session_state.get('weekly_report')
        if not report:
            st.warning("Generate the report first, then send.")
        else:
            resend_key=st.secrets.get("RESEND_API_KEY","") if hasattr(st,'secrets') else ""
            if not resend_key:
                st.info("RESEND_API_KEY not configured in Streamlit secrets. Add it to enable email sending.")
            else:
                with st.spinner("Sending email..."):
                    ok=send_email_report(report,cfg.get('email',''))
                st.success("✅  Report sent to your email!") if ok else st.error("Email failed. Check RESEND_API_KEY in secrets.")


def page_settings():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>⚙️ Settings</h1>",unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Configure your API keys and channel info.</p>",unsafe_allow_html=True)
    section("API Keys")
    with st.form("settings"):
        gem_key=st.text_input("Gemini API Key (free — aistudio.google.com)",value=cfg.get('gemini_api_key',''),type="password",placeholder="AIza...")
        yt_key=st.text_input("YouTube Data API Key (console.cloud.google.com)",value=cfg.get('youtube_api_key',''),type="password",placeholder="AIza...")
        section("Channel Info")
        ch_name=st.text_input("Channel Name",value=cfg.get('channel_name','AlgoQuant Trading'))
        bio=st.text_input("Creator Bio",value=cfg.get('creator_bio','Financial engineer from Morocco, self-taught quant'))
        prods=st.text_input("Products",value=cfg.get('products','SaaS, MQL5 EAs, courses, freelance'))
        email=st.text_input("Email for weekly reports",value=cfg.get('email',''))
        section("Channel Stats")
        c1,c2,c3,c4=st.columns(4)
        with c1: new_s=st.number_input("Subscribers",min_value=0,value=cfg.get('subscribers',5))
        with c2: new_h=st.number_input("Watch Hours",min_value=0.0,value=float(cfg.get('watch_hours',1.4)),format="%.1f")
        with c3: new_c=st.number_input("Avg CTR %",min_value=0.0,value=float(cfg.get('avg_ctr',2.5)),format="%.1f")
        with c4: new_v=st.number_input("Total Videos",min_value=0,value=cfg.get('total_videos',4))
        if st.form_submit_button("💾  Save All Settings",use_container_width=True):
            new_config={
                'gemini_api_key':gem_key,'youtube_api_key':yt_key,
                'channel_name':ch_name,'creator_bio':bio,'products':prods,'email':email,
                'subscribers':new_s,'watch_hours':new_h,'avg_ctr':new_c,'total_videos':new_v,
            }
            st.session_state['config']=new_config
            db_save('user_configs',{'config_json':new_config},user_id)
            st.success("✅  Settings saved")
    st.markdown("<hr class='divider'>",unsafe_allow_html=True)
    section("Streamlit Secrets Required")
    st.code("""# Add these in Streamlit Cloud → Settings → Secrets
GEMINI_API_KEY = "AIza..."
YOUTUBE_API_KEY = "AIza..."
GOOGLE_CLIENT_ID = "..."
GOOGLE_CLIENT_SECRET = "..."
REDIRECT_URI = "https://yourapp.streamlit.app"
RESEND_API_KEY = "re_..."
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."
""", language="toml")
    st.markdown("<hr class='divider'>",unsafe_allow_html=True)
    section("Supabase Setup (for persistence)")
    st.markdown("""
    <div class='step-box'>
        <div style='font-size:0.82rem;font-weight:600;margin-bottom:3px;'>1. Create free account at supabase.com</div>
        <div style='font-size:0.75rem;color:#9ca3af;'>New project → copy URL and anon key from Settings → API</div>
    </div>
    <div class='step-box'>
        <div style='font-size:0.82rem;font-weight:600;margin-bottom:3px;'>2. Run this SQL in Supabase SQL Editor</div>
    </div>
    """, unsafe_allow_html=True)
    st.code("""-- Run this in Supabase SQL Editor
create table video_history (
  id uuid default gen_random_uuid() primary key,
  user_id text, idea text, format text, funnel text,
  title text, title_score int, hook_score int,
  virality_score int, word_count int, script text,
  tags text, status text default 'generated',
  real_ctr float, real_retention float, real_views int,
  created_at timestamp default now()
);
create table competitor_reports (
  id uuid default gen_random_uuid() primary key,
  user_id text, data text, channel_count int,
  created_at timestamp default now()
);
create table channel_snapshots (
  id uuid default gen_random_uuid() primary key,
  user_id text, subscribers int, watch_hours float,
  avg_ctr float, total_videos int,
  created_at timestamp default now()
);
create table weekly_reports (
  id uuid default gen_random_uuid() primary key,
  user_id text, report text,
  created_at timestamp default now()
);
create table user_configs (
  id uuid default gen_random_uuid() primary key,
  user_id text unique, config_json jsonb,
  created_at timestamp default now()
);
""", language="sql")
    step_box("3. Add SUPABASE_URL and SUPABASE_KEY to Streamlit secrets","Then redeploy. All video history, reports, and settings will persist across sessions.")


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
