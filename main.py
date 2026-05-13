"""
AlgoQuant Studio — Complete MVP
Single-file Streamlit application.
Deploy: streamlit run algoquant_studio.py
Install: pip install streamlit google-generativeai google-api-python-client pandas
"""

import json
import re
import time
import textwrap
from datetime import datetime
from collections import Counter

import streamlit as st
import pandas as pd
import google.generativeai as genai

# ════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AlgoQuant Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ════════════════════════════════════════════════════════════
# GLOBAL CSS
# ════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg:      #0a0c10;
  --surface: #111318;
  --border:  #1e2229;
  --accent:  #00e5a0;
  --accent2: #0066ff;
  --warn:    #ff6b35;
  --text:    #e8eaf0;
  --muted:   #6b7280;
  --green:   #00e5a0;
  --red:     #ff4560;
  --yellow:  #ffd700;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: 'Space Grotesk', sans-serif !important;
}
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
h1,h2,h3,h4 {
  font-family: 'Space Grotesk', sans-serif !important;
  color: var(--text) !important; font-weight: 700 !important;
}
.stButton > button {
  background: var(--accent) !important; color: #000 !important;
  border: none !important; border-radius: 8px !important;
  font-weight: 600 !important; font-family: 'Space Grotesk',sans-serif !important;
  padding: 0.5rem 1.5rem !important; transition: all 0.2s !important;
}
.stButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 20px rgba(0,229,160,0.3) !important;
}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
  background: var(--surface) !important; border: 1px solid var(--border) !important;
  color: var(--text) !important; border-radius: 8px !important;
  font-family: 'Space Grotesk',sans-serif !important;
}
.stTabs [data-baseweb="tab-list"] { background: var(--surface) !important; border-radius: 8px; }
.stTabs [data-baseweb="tab"] { color: var(--muted) !important; font-family: 'Space Grotesk',sans-serif !important; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; }
.stDataFrame { background: var(--surface) !important; }
.stExpander { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }

.metric-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.25rem 1.5rem;
  position: relative; overflow: hidden;
}
.metric-card::before {
  content:''; position:absolute; top:0;left:0;right:0;
  height:2px; background:var(--accent);
}
.metric-val { font-size:2rem;font-weight:700;color:var(--accent);line-height:1;margin-bottom:0.25rem; }
.metric-lbl { font-size:0.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em; }

.video-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.75rem;
  transition: border-color 0.2s;
}
.video-card:hover { border-color: var(--accent); }

.score-badge { display:inline-block;padding:0.2rem 0.6rem;border-radius:20px;font-size:0.75rem;font-weight:600; }
.score-green  { background:rgba(0,229,160,0.15);color:var(--green); }
.score-yellow { background:rgba(255,215,0,0.15);color:var(--yellow); }
.score-red    { background:rgba(255,69,96,0.15);color:var(--red); }

.section-header {
  font-size:0.7rem;text-transform:uppercase;letter-spacing:0.12em;
  color:var(--muted);margin-bottom:0.75rem;margin-top:1.5rem;
}
.tag {
  display:inline-block;background:rgba(0,102,255,0.15);color:#60a5fa;
  border:1px solid rgba(0,102,255,0.3);border-radius:4px;
  padding:0.15rem 0.5rem;font-size:0.72rem;margin:0.15rem;
}
.funnel-badge {
  display:inline-block;padding:0.2rem 0.7rem;border-radius:20px;
  font-size:0.72rem;font-weight:600;
  background:rgba(255,107,53,0.15);color:var(--warn);
}
.step-box {
  background:var(--surface);border:1px solid var(--border);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
  padding:0.75rem 1rem;margin-bottom:0.5rem;
}
.script-block {
  background:#0d1117;border:1px solid var(--border);border-radius:8px;
  padding:1rem 1.25rem;font-family:'JetBrains Mono',monospace;
  font-size:0.82rem;color:#c9d1d9;line-height:1.7;white-space:pre-wrap;
}
.divider { border:none;border-top:1px solid var(--border);margin:1.25rem 0; }
#MainMenu,footer,header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# ENGINE — ALL AI + YOUTUBE LOGIC
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

DEFAULT_VIDEOS = [
    {'title':'Why Your Python Backtesting Is Lying to You','format':'Short','views':76,'ctr':2.5,'retention':37.5,'subs':2,'p3_score':None},
    {'title':'Bitcoin Strategy Backtesting Python','format':'Short','views':41,'ctr':0.0,'retention':47.5,'subs':0,'p3_score':None},
    {'title':'How to Validate Bitcoin Trading in 8 Minutes','format':'Long','views':75,'ctr':2.5,'retention':8.1,'subs':2,'p3_score':None},
    {'title':'3 Traps That Make Crypto Backtest Look Profitable','format':'Long','views':11,'ctr':2.8,'retention':0.0,'subs':1,'p3_score':None},
]


def get_model():
    key = st.session_state.get('config', {}).get('gemini_api_key', '')
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel('gemini-1.5-flash')


def call_gemini(model, prompt, max_tokens=2000):
    for attempt in range(2):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens, temperature=0.7)
            )
            raw = resp.text.strip()
            raw = re.sub(r'```json|```', '', raw).strip()
            o, c = raw.count('{'), raw.count('}')
            if o > c:
                raw += '}' * (o - c)
            return json.loads(raw)
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
            else:
                raise e


def call_gemini_text(model, prompt, max_tokens=2000):
    for attempt in range(2):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens, temperature=0.7)
            )
            return resp.text.strip()
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
            else:
                raise e


def build_context():
    cfg = st.session_state.get('config', {})
    return f"""
Channel: {cfg.get('channel_name','AlgoQuant Trading')}
Niche: Algorithmic trading, quantitative finance, automated trading systems

Target audiences:
- Prop firm traders (FTMO, Funded Next, The5ers) looking to automate
- Manual traders wanting to convert their edge into code
- Crypto quant investors building systematic strategies
- Algo investors running portfolio of EAs

Creator: {cfg.get('creator_bio','Financial engineer from Morocco, self-taught quant')}
Pipeline: idea → Python backtest → MQL5 → live MT5
Products: {cfg.get('products','SaaS, MQL5 EAs, courses, freelance')}

What works in this niche (competitor data):
- Titles starting with I: 100% success, 80k avg views
- Dollar sign in title: 100% success, 113k avg views
- Contains Python/backtest/FTMO/algo/bot: 100% success
- Contains AI or GPT: 100% success
- Contains a number: 88% success
- Warning/never/secret: very high performance
- Honest failure content: massive engagement

Channel stats: {cfg.get('subscribers',5)} subs · {cfg.get('avg_ctr',2.5)}% CTR · {cfg.get('watch_hours',1.4)}h watch time

Hook rules (CRITICAL — 8.1% long form retention is the main problem):
- First sentence MUST contain the result or bold claim
- NEVER start with Hi, Welcome, Today we are, or channel intro
- Must match what the title promises exactly
- TTS-friendly: short sentences, natural pauses
"""


# ─── Competitor fetch ────────────────────────────────────────

def fetch_competitor_videos(api_key, channels, videos_per_channel=20):
    from googleapiclient.discovery import build as yt_build
    youtube    = yt_build('youtube', 'v3', developerKey=api_key)
    all_videos = []
    for name, cid in channels.items():
        try:
            cr = youtube.channels().list(part='contentDetails,statistics', id=cid).execute()
            if not cr['items']:
                continue
            cd  = cr['items'][0]
            uid = cd['contentDetails']['relatedPlaylists']['uploads']
            subs= int(cd['statistics'].get('subscriberCount',0))
            vids= []
            npt = None
            while len(vids) < videos_per_channel:
                pr = youtube.playlistItems().list(
                    part='contentDetails', playlistId=uid,
                    maxResults=min(50,videos_per_channel-len(vids)),
                    pageToken=npt).execute()
                for it in pr['items']:
                    vids.append(it['contentDetails']['videoId'])
                npt = pr.get('nextPageToken')
                if not npt:
                    break
            for i in range(0,len(vids),50):
                sr = youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(vids[i:i+50])).execute()
                for v in sr['items']:
                    sn    = v['snippet']
                    st2   = v.get('statistics',{})
                    dur   = v['contentDetails']['duration']
                    m     = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur)
                    tsec  = int(m.group(1) or 0)*3600+int(m.group(2) or 0)*60+int(m.group(3) or 0)
                    pub   = datetime.strptime(sn['publishedAt'],'%Y-%m-%dT%H:%M:%SZ')
                    dold  = max((datetime.utcnow()-pub).days,1)
                    views = int(st2.get('viewCount',0))
                    all_videos.append({
                        'channel':name,'channel_subs':subs,
                        'title':sn['title'],'video_id':v['id'],
                        'url':f"https://youtube.com/watch?v={v['id']}",
                        'published':pub.strftime('%Y-%m-%d'),
                        'days_old':dold,'views':views,
                        'likes':int(st2.get('likeCount',0)),
                        'comments':int(st2.get('commentCount',0)),
                        'views_per_day':round(views/dold,1),
                        'duration_sec':tsec,'is_short':tsec<=60,
                    })
        except Exception:
            continue
    return all_videos


def analyze_patterns(videos, threshold=5000):
    STOP = {'a','an','the','and','or','but','in','on','at','to','for','of','with','by',
            'from','is','it','my','i','your','how','what','why','when','this','that',
            'you','we','are','was','be','have','has','do','did','will','can','get',
            'as','its','not','into','using','vs','if','so'}
    lf   = [v for v in videos if not v['is_short']]
    sh   = [v for v in videos if v['is_short']]
    succ = [v for v in lf if v['views'] >= threshold]
    def words(titles):
        w=[]
        for t in titles:
            c=re.sub(r'[^a-zA-Z0-9\s]','',t.lower())
            for x in c.split():
                if x not in STOP and len(x)>2: w.append(x)
        return w
    top_words = Counter(words([v['title'] for v in succ])).most_common(20)
    trending  = sorted([v for v in lf if v['days_old']<=30], key=lambda x:x['views_per_day'],reverse=True)[:5]
    evergreen = sorted([v for v in lf if v['days_old']>180], key=lambda x:x['views_per_day'],reverse=True)[:5]
    top20     = sorted(lf, key=lambda x:x['views'],reverse=True)[:20]
    return {'total':len(videos),'long_count':len(lf),'short_count':len(sh),
            'success_count':len(succ),'top_words':top_words,
            'trending':trending,'evergreen':evergreen,'top20':top20}


# ─── AI functions ────────────────────────────────────────────

def ai_virality(model, idea, fmt, funnel, ctx):
    return call_gemini(model, f"""
You are a YouTube growth expert for algorithmic trading.
{ctx}
Video idea: {idea}
Format: {FORMAT_CONTEXT[fmt]}
Funnel: {funnel}
Score 0-100 across: audience_demand, trend_alignment, differentiation, creator_fit, monetization_fit (each 20).
If below 60 suggest better angle. If 60+ approve.
Return ONLY valid JSON no markdown:
{{"idea_summary":"one sentence","virality_score":78,
"breakdown":{{"audience_demand":16,"trend_alignment":15,"differentiation":14,"creator_fit":18,"monetization_fit":15}},
"verdict":"approved or rejected","verdict_reason":"2 sentences","better_angle":"if rejected else null"}}
""", 800)


def ai_title_hook(model, idea, fmt, funnel, ctx):
    return call_gemini(model, f"""
You are a YouTube growth expert for algorithmic trading.
{ctx}
Idea: {idea}
Format: {FORMAT_CONTEXT[fmt]}
Funnel: {FUNNEL_DESCRIPTIONS[funnel]}
Generate best title score above 75 and hook. Hook: result in first sentence TTS-ready never Hi or Welcome.
Short: under 130 words. Long: 60-90 words first 30 seconds.
Return ONLY valid JSON no markdown:
{{"title":"best title","title_score":82,"title_reasoning":"why",
"hook_script":"full hook","hook_score":85,"hook_reasoning":"why",
"alternative_titles":[{{"title":"alt","score":78}},{{"title":"alt","score":75}},{{"title":"alt","score":76}}]}}
""", 1200)


def ai_script_part(model, idea, title, hook, funnel, ctx, part, prev=''):
    cont = f'\nContinue from: "{prev[-300:]}"' if part==2 else ''
    inst = 'Write FIRST HALF ~1000 words. End at natural transition.' if part==1 else 'Write SECOND HALF ~1000 words. End with subscribe CTA then funnel CTA.'
    return call_gemini_text(model, f"""
You are a YouTube scriptwriter for algorithmic trading.
{ctx}
Title: {title}
Idea: {idea}
Funnel: {FUNNEL_DESCRIPTIONS[funnel]}
{cont}
Rules: TTS-friendly short sentences. Show concept not code. [minute] markers. Never Hi Welcome.
{inst}
{'Start with: ' + hook if part==1 else ''}
Return ONLY raw script text. No JSON. No markdown.
""", 2000)


def ai_packaging(model, idea, title, fmt, funnel, ctx):
    return call_gemini(model, f"""
You are a YouTube packaging expert for algorithmic trading.
{ctx}
Title: {title}
Idea: {idea}
Format: {fmt}
Funnel: {FUNNEL_DESCRIPTIONS[funnel]}
Generate thumbnail 2 options SEO 3 shorts CTA.
Return ONLY valid JSON no markdown:
{{"thumbnail":{{"option_1":{{"concept":"","background":"","main_text":"","sub_text":"","visual":"","colors":["#hex"],"canva_steps":"","predicted_ctr":""}},"option_2":{{"concept":"","background":"","main_text":"","sub_text":"","visual":"","colors":["#hex"],"canva_steps":"","predicted_ctr":""}},"recommended":"1","recommended_reason":""}},"seo":{{"tags":["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10"],"description_line1":"","description_line2":"","chapters":[{{"time":"0:00","title":""}},{{"time":"2:00","title":""}},{{"time":"5:00","title":""}},{{"time":"10:00","title":""}},{{"time":"14:00","title":""}}]}},"shorts":[{{"title":"","hook":"","clip":""}},{{"title":"","hook":"","clip":""}},{{"title":"","hook":"","clip":""}}],"cta_script":""}}
""", 2500)


def ai_suggestions(model, trending, existing, ctx):
    tt = '\n'.join([f"- {v['title']} ({v.get('views_per_day',0):,.0f}/day, {v.get('days_old',0)}d)" for v in trending[:5]])
    et = '\n'.join([f"- {t}" for t in existing[:10]])
    return call_gemini(model, f"""
You are a YouTube content strategist for algorithmic trading.
{ctx}
Trending now:\n{tt}
Already posted (do not repeat):\n{et}
Suggest 3 ideas: 1 Short + 2 Long Form. Titles above 75. Hooks result-first no Hi no Welcome.
Return ONLY valid JSON no markdown:
{{"date":"{datetime.now().strftime('%Y-%m-%d')}","suggestions":[
{{"id":1,"format":"short","topic":"","why_now":"","title":"","title_score":80,"hook":"","show":"","hide":"","funnel":"ea","cta":"","thumb_text":"","tags":["t1","t2","t3","t4","t5"]}},
{{"id":2,"format":"long_form","topic":"","why_now":"","title":"","title_score":85,"hook":"","show":"","hide":"","funnel":"ea","cta":"","thumb_text":"","tags":["t1","t2","t3","t4","t5"]}},
{{"id":3,"format":"long_form","topic":"","why_now":"","title":"","title_score":82,"hook":"","show":"","hide":"","funnel":"ea","cta":"","thumb_text":"","tags":["t1","t2","t3","t4","t5"]}}
]}}
""", 3000)


def ai_score(model, title, hook, ctx, real_ctr=None, real_ret=None):
    is_short = len(hook.split()) < 130 if hook else False
    fmt_note = 'SHORT — emotional hook most critical.' if is_short else 'LONG FORM — all dimensions equal.'
    cal      = f'Real CTR: {real_ctr}%. Real retention: {real_ret}%. Calibrate.' if real_ctr else ''
    hs       = f'Also score this hook:\n{hook}' if hook else 'No hook.'
    return call_gemini(model, f"""
You are a YouTube growth expert for algorithmic trading.
{ctx}
Format: {fmt_note}
Title: {title}
{hs}
{cal}
Score title 0-100: ctr_potential keyword_strength emotional_hook niche_fit pattern_match (each 20).
Score hook 0-100: speed_to_value result_first pattern_interrupt audience_targeting curiosity_gap (each 20).
5 title variations: personal story, number result, urgency fear, search optimized, controversy.
3 hook rewrites TTS-ready result first never Hi: A ultra-fast B story C controversy.
Return ONLY valid JSON no markdown:
{{"title":"{title}","detected_format":"short or long_form","title_score":72,
"title_breakdown":{{"ctr_potential":15,"keyword_strength":18,"emotional_hook":12,"niche_fit":17,"pattern_match":10}},
"title_diagnosis":"","hook_score":45,
"hook_breakdown":{{"speed_to_value":7,"result_first":5,"pattern_interrupt":8,"audience_targeting":12,"curiosity_gap":13}},
"hook_diagnosis":"","calibration_note":null,
"title_variations":[{{"type":"Personal story","title":"","why":""}},{{"type":"Number result","title":"","why":""}},{{"type":"Urgency fear","title":"","why":""}},{{"type":"Search optimized","title":"","why":""}},{{"type":"Controversy","title":"","why":""}}],
"best_title":"","best_title_reason":"",
"hook_rewrites":[{{"version":"A","type":"Ultra-fast","script":"","why":""}},{{"version":"B","type":"Story-driven","script":"","why":""}},{{"version":"C","type":"Controversy","script":"","why":""}}],
"best_hook_version":"A","best_hook_reason":"","thumbnail_concept":""}}
""", 3000)


# ════════════════════════════════════════════════════════════
# SHARED UI HELPERS
# ════════════════════════════════════════════════════════════

def score_badge(score):
    cls = 'score-green' if score>=75 else 'score-yellow' if score>=50 else 'score-red'
    em  = '🟢' if score>=75 else '🟡' if score>=50 else '🔴'
    return f"<span class='score-badge {cls}'>{em} {score}/100</span>"


def section(title):
    st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)


def step_box(title, body, border_color='var(--accent)'):
    st.markdown(f"""
    <div class='step-box' style='border-left-color:{border_color};'>
        <div style='font-size:0.82rem;font-weight:600;margin-bottom:3px;'>{title}</div>
        <div style='font-size:0.78rem;color:#9ca3af;'>{body}</div>
    </div>""", unsafe_allow_html=True)


def small_metric(val, lbl, color='var(--accent)'):
    return f"<div class='metric-card'><div class='metric-val' style='color:{color};font-size:1.5rem;'>{val}</div><div class='metric-lbl'>{lbl}</div></div>"


def video_card(v):
    ret_c = '#00e5a0' if v.get('retention',0)>=40 else '#ffd700' if v.get('retention',0)>=20 else '#ff4560'
    ctr_c = '#00e5a0' if v.get('ctr',0)>=4 else '#ffd700' if v.get('ctr',0)>=2 else '#ff4560'
    fmt_c = '#0066ff' if v.get('format','')=='Long' else '#00e5a0'
    ret_d = f"{v.get('retention',0)}%" if v.get('retention',0)>0 else '—'
    ctr_d = f"{v.get('ctr',0)}%" if v.get('ctr',0)>0 else '—'
    p3    = str(int(v['p3_score'])) if v.get('p3_score') else '—'
    st.markdown(f"""
    <div class='video-card'>
        <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
            <div style='flex:1;'>
                <div style='font-size:0.85rem;font-weight:600;margin-bottom:6px;'>{v['title']}</div>
                <div style='display:flex;gap:1.2rem;flex-wrap:wrap;'>
                    <span style='font-size:0.75rem;color:#6b7280;'>👁 <b style='color:#e8eaf0;'>{v.get('views',0)}</b></span>
                    <span style='font-size:0.75rem;'>CTR <b style='color:{ctr_c};'>{ctr_d}</b></span>
                    <span style='font-size:0.75rem;'>Ret <b style='color:{ret_c};'>{ret_d}</b></span>
                    <span style='font-size:0.75rem;color:#6b7280;'>+{v.get('subs',0)} subs</span>
                    <span style='font-size:0.75rem;color:#ffd700;'>P3: {p3}</span>
                </div>
            </div>
            <span style='font-size:0.65rem;font-weight:700;color:{fmt_c};border:1px solid {fmt_c};border-radius:4px;padding:2px 8px;margin-left:8px;'>{v.get('format','').upper()}</span>
        </div>
    </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════

if 'config' not in st.session_state:
    st.session_state['config'] = {
        'channel_name':'AlgoQuant Trading',
        'creator_bio':'Financial engineer from Morocco, self-taught quant',
        'products':'SaaS, MQL5 EAs, courses, freelance',
        'subscribers':5, 'watch_hours':1.4,
        'avg_ctr':2.5, 'total_videos':4,
        'gemini_api_key':'', 'youtube_api_key':'',
    }

cfg = st.session_state['config']

with st.sidebar:
    st.markdown("""
    <div style='padding:1rem 0 1.5rem;'>
        <div style='font-size:1.4rem;font-weight:700;color:#00e5a0;letter-spacing:-0.02em;'>⚡ AlgoQuant</div>
        <div style='font-size:0.72rem;color:#6b7280;letter-spacing:0.08em;text-transform:uppercase;margin-top:2px;'>Content Intelligence Studio</div>
    </div>""", unsafe_allow_html=True)

    page = st.radio("",
        ["🏠  Dashboard","🔍  Competitor Intel","📊  My Channel","🏭  Video Factory","⚙️  Settings"],
        label_visibility="collapsed")

    st.markdown("<hr style='border-color:#1e2229;margin:1rem 0;'>", unsafe_allow_html=True)
    section("Channel Status")

    subs  = cfg.get('subscribers', 5)
    hours = cfg.get('watch_hours', 1.4)
    sp    = min(subs/1000*100, 100)
    hp    = min(hours/4000*100, 100)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown(f"<div style='text-align:center;'><div style='font-size:1.3rem;font-weight:700;color:#00e5a0;'>{subs}</div><div style='font-size:0.65rem;color:#6b7280;'>SUBS</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='text-align:center;'><div style='font-size:1.3rem;font-weight:700;color:#0066ff;'>{hours:.1f}h</div><div style='font-size:0.65rem;color:#6b7280;'>WATCH HRS</div></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style='margin-top:0.75rem;'>
        <div style='font-size:0.7rem;color:#6b7280;margin-bottom:3px;'>Subs {sp:.1f}% to monetization</div>
        <div style='background:#1e2229;border-radius:4px;height:4px;margin-bottom:8px;'>
            <div style='background:#00e5a0;width:{sp}%;height:4px;border-radius:4px;'></div>
        </div>
        <div style='font-size:0.7rem;color:#6b7280;margin-bottom:3px;'>Watch hrs {hp:.3f}% to monetization</div>
        <div style='background:#1e2229;border-radius:4px;height:4px;'>
            <div style='background:#0066ff;width:{min(hp*50,100)}%;height:4px;border-radius:4px;'></div>
        </div>
    </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════

def page_dashboard():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>Good morning, Creator ⚡</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Your content intelligence dashboard.</p>", unsafe_allow_html=True)

    section("Monetization Progress")
    c1,c2,c3,c4 = st.columns(4)
    items = [
        (str(subs), "Subscribers", f"{sp:.1f}% of 1,000", '#00e5a0'),
        (f"{hours:.1f}h", "Watch Hours", f"{hp:.3f}% of 4,000h", '#0066ff'),
        (f"{cfg.get('avg_ctr',2.5)}%", "Avg CTR", "Target: 4%+", '#ffd700' if cfg.get('avg_ctr',2.5)<4 else '#00e5a0'),
        (str(cfg.get('total_videos',4)), "Videos Posted", "Keep posting", '#00e5a0'),
    ]
    for col,(val,lbl,sub,col_) in zip([c1,c2,c3,c4],items):
        with col:
            st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:{col_};'>{val}</div><div class='metric-lbl'>{lbl}</div><div style='font-size:0.7rem;color:#6b7280;margin-top:6px;'>{sub}</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    left, right = st.columns([3,2])

    with left:
        section("This Week's Priority Actions")
        actions = [
            ("🔴","Fix thumbnail on 'How to Validate Bitcoin' video","CTR 2.5% — thumbnail says wrong topic. Redesign now."),
            ("🟡","Post 6 Shorts this week","Shorts retention 37-47% is healthy. Volume is the fix."),
            ("🟢","Run Video Factory — Prop Firm EA kill-switch","Virality 78, Title 92, Hook 94 — record this week."),
            ("🟡","Reply to every comment within 24h","Algorithm rewards engagement. Critical for new channels."),
            ("🟢","Run Competitor Intel Monday","Update trending topics for fresh auto-suggestions."),
        ]
        for em,t,d in actions:
            st.markdown(f"""<div class='step-box'><div style='display:flex;align-items:center;gap:0.5rem;'><span>{em}</span><span style='font-size:0.85rem;font-weight:600;'>{t}</span></div><div style='font-size:0.75rem;color:#6b7280;margin-top:2px;padding-left:1.3rem;'>{d}</div></div>""", unsafe_allow_html=True)

    with right:
        section("Your Videos")
        for v in DEFAULT_VIDEOS:
            video_card(v)

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    section("Monday Morning Routine (30 min)")
    steps = [
        ("1","Competitor Intel","Run Phase 1 — see what is trending"),
        ("2","Update Analytics","Paste stats into My Channel"),
        ("3","Auto Suggest","Get 3 video ideas from trends"),
        ("4","Video Factory","Generate full package for best idea"),
        ("5","Record & Post","OBS + Chatterbox + Shotcut + Upload"),
    ]
    cols = st.columns(5)
    for col,(num,t,d) in zip(cols,steps):
        with col:
            st.markdown(f"""<div style='background:#111318;border:1px solid #1e2229;border-radius:12px;padding:1rem;text-align:center;'><div style='width:28px;height:28px;background:rgba(0,229,160,0.15);border:1px solid #00e5a0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 8px;font-size:0.75rem;font-weight:700;color:#00e5a0;'>{num}</div><div style='font-size:0.78rem;font-weight:600;margin-bottom:4px;'>{t}</div><div style='font-size:0.68rem;color:#6b7280;line-height:1.4;'>{d}</div></div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# PAGE: COMPETITOR INTEL
# ════════════════════════════════════════════════════════════

def page_competitor():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>🔍 Competitor Intelligence</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Track what works in your niche. Run every Monday.</p>", unsafe_allow_html=True)

    yt_key = cfg.get('youtube_api_key','')

    with st.expander("⚙️  Channel list", expanded=False):
        channels_text = st.text_area("Channels (Name,ChannelID per line)",
            value='\n'.join([f"{k},{v}" for k,v in DEFAULT_CHANNELS.items()]), height=100)
        vids_n = st.slider("Videos per channel", 5, 50, 20)

    col_btn, col_info = st.columns([1,3])
    with col_btn:
        run_btn = st.button("🔍  Fetch Competitor Data", use_container_width=True)
    with col_info:
        st.markdown("<div style='padding-top:0.5rem;font-size:0.8rem;color:#6b7280;'>Public data only. Takes ~30 seconds.</div>", unsafe_allow_html=True)

    if 'competitor_data' in st.session_state and not run_btn:
        _show_competitor_results(st.session_state['competitor_data'])
        return

    if run_btn:
        if not yt_key:
            st.error("⚠️  Add YouTube API key in Settings.")
            return
        channels = {}
        for line in channels_text.strip().split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts)==2: channels[parts[0]] = parts[1]
        with st.spinner("Fetching..."):
            try:
                videos  = fetch_competitor_videos(yt_key, channels, vids_n)
                results = analyze_patterns(videos)
                st.session_state['competitor_data']    = results
                st.session_state['competitor_trending'] = results.get('trending',[])
                st.success(f"✅  {results['total']} videos from {len(channels)} channels")
                _show_competitor_results(results)
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.markdown("""<div style='background:#111318;border:1px solid #1e2229;border-radius:12px;padding:2rem;text-align:center;margin-top:2rem;'><div style='font-size:2rem;margin-bottom:0.5rem;'>🔍</div><div style='font-size:1rem;font-weight:600;margin-bottom:0.5rem;'>Ready to fetch competitor data</div><div style='font-size:0.82rem;color:#6b7280;'>Add YouTube API key in Settings then click above.</div></div>""", unsafe_allow_html=True)


def _show_competitor_results(results):
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    for col,(val,lbl) in zip([c1,c2,c3,c4],[
        (str(results['total']),"Total Videos"),
        (str(results['long_count']),"Long Form"),
        (str(results['short_count']),"Shorts"),
        (str(results['success_count']),"Above 5k Views"),
    ]):
        with col:
            st.markdown(f"<div class='metric-card'><div class='metric-val'>{val}</div><div class='metric-lbl'>{lbl}</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        section("🔥 Trending Now")
        for v in results.get('trending',[]):
            st.markdown(f"""<div class='video-card'><div style='font-size:0.82rem;font-weight:600;margin-bottom:4px;'>{v['title'][:55]}</div><div style='font-size:0.72rem;color:#6b7280;'>{v['channel']} · {v['views']:,} views · <span style='color:#00e5a0;'>{v['views_per_day']:,.0f}/day</span></div><a href='{v['url']}' target='_blank' style='font-size:0.68rem;color:#0066ff;text-decoration:none;'>Watch ↗</a></div>""", unsafe_allow_html=True)

    with right:
        section("🌲 Evergreen")
        for v in results.get('evergreen',[]):
            st.markdown(f"""<div class='video-card'><div style='font-size:0.82rem;font-weight:600;margin-bottom:4px;'>{v['title'][:55]}</div><div style='font-size:0.72rem;color:#6b7280;'>{v['channel']} · {v['views']:,} views · <span style='color:#ffd700;'>{v['views_per_day']:,.0f}/day still</span></div><a href='{v['url']}' target='_blank' style='font-size:0.68rem;color:#0066ff;text-decoration:none;'>Watch ↗</a></div>""", unsafe_allow_html=True)

    section("🔑 Top Keywords in Successful Titles")
    kw_html = ''.join([f"<span class='tag'>{w} ({c})</span>" for w,c in results.get('top_words',[])[:15]])
    st.markdown(f"<div style='line-height:2;'>{kw_html}</div>", unsafe_allow_html=True)

    section("🏆 Top 20 Videos")
    if results.get('top20'):
        df = pd.DataFrame(results['top20'])[['channel','title','views','views_per_day','days_old']]
        df.columns=['Channel','Title','Views','Views/Day','Age(days)']
        df['Views'] = df['Views'].apply(lambda x:f"{x:,}")
        df['Views/Day'] = df['Views/Day'].apply(lambda x:f"{x:,.0f}")
        st.dataframe(df, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════
# PAGE: MY CHANNEL
# ════════════════════════════════════════════════════════════

def page_analytics():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>📊 My Channel Analytics</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Update every Monday from YouTube Studio.</p>", unsafe_allow_html=True)

    section("Update Channel Stats")
    with st.form("channel_stats"):
        c1,c2,c3,c4 = st.columns(4)
        with c1: new_subs = st.number_input("Subscribers", min_value=0, value=cfg.get('subscribers',5))
        with c2: new_hrs  = st.number_input("Watch Hours", min_value=0.0, value=float(cfg.get('watch_hours',1.4)), format="%.1f")
        with c3: new_ctr  = st.number_input("Avg CTR %", min_value=0.0, value=float(cfg.get('avg_ctr',2.5)), format="%.1f")
        with c4: new_vids = st.number_input("Total Videos", min_value=0, value=cfg.get('total_videos',4))
        if st.form_submit_button("💾  Save Stats", use_container_width=True):
            st.session_state['config'].update({'subscribers':new_subs,'watch_hours':new_hrs,'avg_ctr':new_ctr,'total_videos':new_vids})
            st.success("✅  Saved")

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    section("Monetization Progress")
    sp2 = min(cfg.get('subscribers',5)/1000*100,100)
    hp2 = min(cfg.get('watch_hours',1.4)/4000*100,100)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span style='font-weight:600;'>Subscribers</span><span style='color:#00e5a0;font-weight:700;'>{cfg.get('subscribers',5):,} / 1,000</span></div><div style='background:#1e2229;border-radius:6px;height:8px;'><div style='background:linear-gradient(90deg,#00e5a0,#00b377);width:{sp2}%;height:8px;border-radius:6px;'></div></div><div style='font-size:0.72rem;color:#6b7280;margin-top:6px;'>{sp2:.1f}% · Need {max(1000-cfg.get('subscribers',5),0):,} more</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span style='font-weight:600;'>Watch Hours</span><span style='color:#0066ff;font-weight:700;'>{cfg.get('watch_hours',1.4):.1f} / 4,000h</span></div><div style='background:#1e2229;border-radius:6px;height:8px;'><div style='background:linear-gradient(90deg,#0066ff,#0044cc);width:{min(hp2*50,100):.2f}%;height:8px;border-radius:6px;'></div></div><div style='font-size:0.72rem;color:#6b7280;margin-top:6px;'>{hp2:.3f}% · Need {max(4000-cfg.get('watch_hours',1.4),0):.1f}h more</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    section("Video Performance Tracker")
    for v in DEFAULT_VIDEOS:
        video_card(v)

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    section("Automated Diagnosis")
    avg_ctr = cfg.get('avg_ctr', 2.5)
    diags = [
        ("📈 CTR",
         "🔴 Below 2% — thumbnail is #1 priority." if avg_ctr<2 else
         "🟡 2-4% — decent, test stronger hooks and thumbnails." if avg_ctr<4 else
         "🟢 Above 4% — strong. Keep the formula."),
        ("⏱️ Long Form Retention",
         "🔴 8.1% — CRITICAL. People leave in first 45 seconds. First sentence must deliver the result. Cut all setup."),
        ("📡 Traffic Sources",
         "45% from channel pages — organic not kicking in yet. Post more Shorts to reach the Shorts feed."),
        ("🔑 Key Insight",
         "Shorts retention 37-47% is healthy. Long form 8.1% is the fix. Hook mismatch is the root cause — title promises one thing, hook delivers a generic welcome."),
    ]
    for t,d in diags:
        step_box(t,d)


# ════════════════════════════════════════════════════════════
# PAGE: VIDEO FACTORY
# ════════════════════════════════════════════════════════════

def page_factory():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>🏭 Video Factory</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>One idea in. Full video package out.</p>", unsafe_allow_html=True)

    gemini_key = cfg.get('gemini_api_key','')
    if not gemini_key:
        st.warning("⚠️  Add your Gemini API key in Settings.")
        return

    tab1, tab2, tab3 = st.tabs(["🏭  Full Factory","💡  Auto Suggest","📊  Title Scorer"])

    # ─── TAB 1: FACTORY ─────────────────────────────────────
    with tab1:
        section("Describe your video idea")
        col1, col2, col3 = st.columns([3,1,1])
        with col1:
            idea = st.text_area("Idea", placeholder="e.g. Build a prop firm EA in MQL5 that monitors daily drawdown and shuts down when FTMO limit is hit", height=80, label_visibility='collapsed')
        with col2:
            fmt = st.selectbox("Format", ["long","short"])
        with col3:
            funnel = st.selectbox("Funnel", list(FUNNEL_DESCRIPTIONS.keys()))

        if st.button("⚡  Run Video Factory", use_container_width=True) and idea.strip():
            model = get_model()
            ctx   = build_context()

            # STEP 1
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            section("Step 1 — Virality Check")
            with st.spinner("Checking virality..."):
                try:
                    vr = ai_virality(model, idea, fmt, funnel, ctx)
                except Exception as e:
                    st.error(str(e)); return

            vs    = vr['virality_score']
            vc    = '#00e5a0' if vs>=75 else '#ffd700' if vs>=60 else '#ff4560'
            vb    = vr['breakdown']
            cols6 = st.columns(6)
            for col, k, l in zip(cols6[:5],
                ['audience_demand','trend_alignment','differentiation','creator_fit','monetization_fit'],
                ['Audience','Trend','Different','Creator','Monetize']):
                with col:
                    v_ = vb.get(k,0)
                    c_ = '#00e5a0' if v_>=16 else '#ffd700' if v_>=12 else '#ff4560'
                    st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.2rem;color:{c_};'>{v_}/20</div><div class='metric-lbl'>{l}</div></div>", unsafe_allow_html=True)
            with cols6[5]:
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:{vc};'>{vs}</div><div class='metric-lbl'>Virality</div></div>", unsafe_allow_html=True)

            vdict_c = '#00e5a0' if vr['verdict']=='approved' else '#ff4560'
            step_box(vr['verdict'].upper(), vr['verdict_reason'], vdict_c)
            if vr.get('better_angle'):
                step_box("💡 Better angle", vr['better_angle'], '#ffd700')
            if vr['verdict']=='rejected':
                st.warning("Update idea with the better angle above and rerun.")
                return

            # STEP 2
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            section("Step 2 — Title & Hook")
            with st.spinner("Generating title and hook..."):
                try:
                    th = ai_title_hook(model, idea, fmt, funnel, ctx)
                except Exception as e:
                    st.error(str(e)); return

            ts,hs = th['title_score'], th['hook_score']
            c1_,c2_ = st.columns(2)
            with c1_:
                alts = ''.join([f"<div style='font-size:0.78rem;padding:4px 0;border-bottom:1px solid #1e2229;'>{'🟢' if a['score']>=75 else '🟡'} ({a['score']}) {a['title']}</div>" for a in th.get('alternative_titles',[])])
                st.markdown(f"""<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span class='metric-lbl'>TITLE</span>{score_badge(ts)}</div><div style='font-size:1rem;font-weight:700;margin-bottom:8px;'>"{th['title']}"</div><div style='font-size:0.75rem;color:#6b7280;margin-bottom:8px;'>{th['title_reasoning']}</div>{alts}</div>""", unsafe_allow_html=True)
            with c2_:
                st.markdown(f"""<div class='metric-card'><div style='display:flex;justify-content:space-between;margin-bottom:8px;'><span class='metric-lbl'>HOOK</span>{score_badge(hs)}</div><div style='font-size:0.82rem;color:#c9d1d9;line-height:1.7;font-family:"JetBrains Mono",monospace;'>{th['hook_script']}</div><div style='font-size:0.72rem;color:#6b7280;margin-top:8px;'>{th['hook_reasoning']}</div></div>""", unsafe_allow_html=True)

            # STEP 3
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            section("Step 3 — Full Script")
            with st.spinner("Writing script part 1 of 2..."):
                try: p1 = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, 1)
                except Exception as e: st.error(str(e)); return
            with st.spinner("Writing script part 2 of 2..."):
                try: p2 = ai_script_part(model, idea, th['title'], th['hook_script'], funnel, ctx, 2, p1)
                except Exception: p2=""

            script = p1+"\n\n"+p2
            wc     = len(script.split())
            est    = round(wc/130)
            st.markdown(f"<div style='display:flex;gap:1rem;margin-bottom:0.75rem;'><span class='score-badge score-green'>📝 {wc} words</span><span class='score-badge score-green'>⏱️ ~{est} min</span><span class='score-badge score-yellow'>🔊 Paste into Chatterbox</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='script-block'>{script}</div>", unsafe_allow_html=True)
            st.download_button("⬇️  Download Script", script, file_name=f"script_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")

            # STEP 4
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            section("Step 4 — Thumbnail · SEO · Shorts · CTA")
            with st.spinner("Generating packaging..."):
                try: pk = ai_packaging(model, idea, th['title'], fmt, funnel, ctx)
                except Exception as e: st.error(str(e)); return

            th_data = pk.get('thumbnail',{})
            seo     = pk.get('seo',{})
            shorts  = pk.get('shorts',[])
            cta     = pk.get('cta_script','')
            rec     = th_data.get('recommended','1')

            # Thumbnails
            tc1, tc2 = st.columns(2)
            for col, key in zip([tc1,tc2],['option_1','option_2']):
                with col:
                    opt = th_data.get(key,{})
                    num = key.split('_')[1]
                    is_rec = rec==num
                    border = '#00e5a0' if is_rec else '#1e2229'
                    rec_tag = ' ⭐ RECOMMENDED' if is_rec else ''
                    colors_html = ''.join([f"<span style='display:inline-block;width:16px;height:16px;border-radius:3px;background:{c};margin-right:3px;vertical-align:middle;'></span>" for c in opt.get('colors',[])])
                    st.markdown(f"""<div class='metric-card' style='border-color:{border};'><div style='font-size:0.72rem;font-weight:700;color:#6b7280;margin-bottom:8px;'>OPTION {num}{rec_tag}</div><div style='font-size:0.9rem;font-weight:600;margin-bottom:4px;'>"{opt.get('main_text','')}"</div>{f"<div style='font-size:0.75rem;color:#6b7280;margin-bottom:4px;'>Sub: {opt.get('sub_text','')}</div>" if opt.get('sub_text') else ''}<div style='font-size:0.75rem;color:#9ca3af;margin-bottom:6px;'>{opt.get('concept','')}</div><div style='font-size:0.72rem;color:#6b7280;'>Visual: {opt.get('visual','')}</div><div style='margin:8px 0;'>{colors_html}</div><div style='font-size:0.7rem;color:#6b7280;border-top:1px solid #1e2229;padding-top:8px;'>{opt.get('canva_steps','')}</div><div style='font-size:0.72rem;color:#00e5a0;margin-top:6px;font-weight:600;'>CTR target: {opt.get('predicted_ctr','')}</div></div>""", unsafe_allow_html=True)

            # SEO
            section("SEO Package")
            tags_html = ''.join([f"<span class='tag'>{t}</span>" for t in seo.get('tags',[])])
            st.markdown(f"""<div class='step-box'><div style='font-size:0.78rem;font-weight:600;margin-bottom:6px;'>Description:</div><div style='font-size:0.78rem;color:#9ca3af;'>{seo.get('description_line1','')}</div><div style='font-size:0.78rem;color:#9ca3af;'>{seo.get('description_line2','')}</div><div style='margin-top:10px;'>{tags_html}</div></div>""", unsafe_allow_html=True)
            if seo.get('chapters') and fmt=='long':
                ch_text = '\n'.join([f"{c['time']} {c['title']}" for c in seo['chapters']])
                st.markdown(f"<div class='script-block' style='font-size:0.8rem;'>{ch_text}</div>", unsafe_allow_html=True)

            # Shorts
            section("3 Shorts to Extract")
            for i,s in enumerate(shorts,1):
                st.markdown(f"""<div class='video-card'><div style='display:flex;gap:0.5rem;align-items:center;margin-bottom:4px;'><span style='font-size:0.65rem;font-weight:700;color:#00e5a0;border:1px solid #00e5a0;border-radius:4px;padding:1px 6px;'>SHORT #{i}</span><span style='font-size:0.83rem;font-weight:600;'>{s.get('title','')}</span></div><div style='font-size:0.75rem;color:#9ca3af;margin-bottom:3px;'>Hook: {s.get('hook','')}</div><div style='font-size:0.72rem;color:#6b7280;'>Clip: {s.get('clip','')}</div></div>""", unsafe_allow_html=True)

            # CTA
            section("CTA Script")
            st.markdown(f"<div class='script-block' style='font-size:0.82rem;'>{cta}</div>", unsafe_allow_html=True)

            # Summary
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            st.markdown(f"""<div style='background:rgba(0,229,160,0.05);border:1px solid rgba(0,229,160,0.2);border-radius:12px;padding:1.25rem;'><div style='font-size:0.9rem;font-weight:700;color:#00e5a0;margin-bottom:0.75rem;'>✅  Video Factory Complete</div><div style='display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem;'><span style='font-size:0.8rem;color:#9ca3af;'>Virality <b style='color:#00e5a0;'>{vs}/100</b></span><span style='font-size:0.8rem;color:#9ca3af;'>Title <b style='color:#00e5a0;'>{ts}/100</b></span><span style='font-size:0.8rem;color:#9ca3af;'>Hook <b style='color:#00e5a0;'>{hs}/100</b></span><span style='font-size:0.8rem;color:#9ca3af;'>Script <b style='color:#e8eaf0;'>{wc} words</b></span><span style='font-size:0.8rem;color:#9ca3af;'>~{est} min</span></div><div style='font-size:0.8rem;color:#6b7280;line-height:1.8;'>1. Copy script → Chatterbox TTS &nbsp;·&nbsp; 2. Build thumbnail in Canva &nbsp;·&nbsp; 3. Record OBS &nbsp;·&nbsp; 4. Sync Shotcut &nbsp;·&nbsp; 5. Upload with SEO &nbsp;·&nbsp; 6. Score after 7 days</div></div>""", unsafe_allow_html=True)

    # ─── TAB 2: AUTO SUGGEST ────────────────────────────────
    with tab2:
        section("Auto-suggest 3 video ideas from competitor trends")
        st.markdown("<div style='font-size:0.8rem;color:#6b7280;margin-bottom:1rem;'>Run Competitor Intel first for best results.</div>", unsafe_allow_html=True)

        existing = [v['title'] for v in DEFAULT_VIDEOS]

        if st.button("💡  Generate 3 Video Ideas", use_container_width=True):
            model    = get_model()
            ctx      = build_context()
            trending = st.session_state.get('competitor_trending',[])
            if not trending:
                trending = [
                    {'title':'AI trading bot Python','views_per_day':1200,'days_old':5},
                    {'title':'FTMO prop firm algo','views_per_day':800,'days_old':10},
                ]
                st.info("Using generic trends. Run Competitor Intel for better suggestions.")
            with st.spinner("Generating..."):
                try:
                    result = ai_suggestions(model, trending, existing, ctx)
                except Exception as e:
                    st.error(str(e)); return

            for s in result.get('suggestions',[]):
                fmt_  = s.get('format','').upper().replace('_',' ')
                score = s.get('title_score',0)
                sc    = '#00e5a0' if score>=75 else '#ffd700'
                fmt_c = '#0066ff' if 'LONG' in fmt_ else '#00e5a0'
                tags_html = ''.join([f"<span class='tag'>{t}</span>" for t in s.get('tags',[])])
                st.markdown(f"""<div class='video-card' style='margin-bottom:1rem;'><div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;'><div><span style='font-size:0.65rem;font-weight:700;color:{fmt_c};border:1px solid {fmt_c};border-radius:4px;padding:1px 6px;margin-right:6px;'>IDEA #{s.get("id")} · {fmt_}</span><span class='score-badge {"score-green" if score>=75 else "score-yellow"}' style='font-size:0.65rem;'>Title {score}/100</span></div><span class='funnel-badge'>{s.get("funnel","").upper()}</span></div><div style='font-size:0.9rem;font-weight:700;margin-bottom:4px;'>"{s.get("title","")}"</div><div style='font-size:0.78rem;color:#6b7280;margin-bottom:8px;'>{s.get("topic","")} · {s.get("why_now","")}</div><div style='font-size:0.75rem;color:#9ca3af;background:#0d1117;border-radius:6px;padding:0.6rem 0.8rem;margin-bottom:8px;font-family:"JetBrains Mono",monospace;'>{s.get("hook","")}</div><div style='font-size:0.72rem;color:#6b7280;margin-bottom:4px;'>📺 {s.get("show","")}</div><div style='font-size:0.72rem;color:#6b7280;margin-bottom:4px;'>🔒 {s.get("hide","")}</div><div style='font-size:0.72rem;color:#6b7280;margin-bottom:8px;'>📢 {s.get("cta","")}</div><div>{tags_html}</div></div>""", unsafe_allow_html=True)

            st.info("💡 Pick one idea, go to Full Factory tab, paste as your idea.")

    # ─── TAB 3: TITLE SCORER ────────────────────────────────
    with tab3:
        section("Score a title and hook before you record")
        score_title = st.text_input("Title", placeholder="e.g. I Built a Prop Firm EA That Passed FTMO in 30 Days")
        score_hook  = st.text_area("Hook (optional)", height=100, placeholder="Paste your opening 30 seconds...")
        c1_,c2_    = st.columns(2)
        with c1_: rctr = st.number_input("Real CTR % (if posted)", min_value=0.0, value=0.0, format="%.1f")
        with c2_: rret = st.number_input("Real Retention % (if posted)", min_value=0.0, value=0.0, format="%.1f")

        if st.button("📊  Score Title & Hook", use_container_width=True) and score_title.strip():
            model = get_model()
            ctx   = build_context()
            with st.spinner("Scoring..."):
                try:
                    result = ai_score(model, score_title, score_hook, ctx,
                                       rctr if rctr>0 else None, rret if rret>0 else None)
                except Exception as e:
                    st.error(str(e)); return

            ts,hs = result.get('title_score',0), result.get('hook_score',0)
            c1_m,c2_m = st.columns(2)
            with c1_m: st.markdown(f"<div class='metric-card'><div class='metric-val'>{'🟢' if ts>=75 else '🟡' if ts>=50 else '🔴'} {ts}/100</div><div class='metric-lbl'>Title Score</div></div>", unsafe_allow_html=True)
            with c2_m: st.markdown(f"<div class='metric-card'><div class='metric-val'>{'🟢' if hs>=75 else '🟡' if hs>=50 else '🔴'} {hs}/100</div><div class='metric-lbl'>Hook Score</div></div>", unsafe_allow_html=True)

            step_box("Title Diagnosis", result.get('title_diagnosis',''))
            step_box("Hook Diagnosis", result.get('hook_diagnosis',''))
            if result.get('calibration_note'):
                step_box("📐 Calibration Note", result['calibration_note'], '#ffd700')

            section("Best Title")
            st.markdown(f"""<div style='background:rgba(0,229,160,0.05);border:1px solid rgba(0,229,160,0.3);border-radius:8px;padding:1rem;'><div style='font-size:1rem;font-weight:700;margin-bottom:6px;'>"{result.get('best_title','')}"</div><div style='font-size:0.78rem;color:#6b7280;'>{result.get('best_title_reason','')}</div></div>""", unsafe_allow_html=True)

            section("All 5 Title Variations")
            for v in result.get('title_variations',[]):
                step_box(f"[{v['type']}] {v['title']}", v['why'])

            if result.get('hook_rewrites'):
                best_v = result.get('best_hook_version','A')
                section("Hook Rewrites")
                for hw in result['hook_rewrites']:
                    is_best = hw['version']==best_v
                    border  = '#00e5a0' if is_best else '#1e2229'
                    label   = " ⭐ USE THIS" if is_best else ""
                    st.markdown(f"""<div class='step-box' style='border-left-color:{border};margin-bottom:0.5rem;'><div style='font-size:0.72rem;font-weight:700;color:#6b7280;margin-bottom:4px;'>VERSION {hw["version"]} — {hw["type"]}{label}</div><div class='script-block' style='font-size:0.78rem;padding:0.6rem 0.8rem;margin-bottom:6px;'>{hw["script"]}</div><div style='font-size:0.72rem;color:#6b7280;'>{hw["why"]}</div></div>""", unsafe_allow_html=True)

            step_box("🖼️ Thumbnail Concept", result.get('thumbnail_concept',''))


# ════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ════════════════════════════════════════════════════════════

def page_settings():
    st.markdown("<h1 style='font-size:1.8rem;margin-bottom:0.25rem;'>⚙️ Settings</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.9rem;margin-bottom:2rem;'>Configure your API keys and channel info.</p>", unsafe_allow_html=True)

    section("API Keys")
    with st.form("settings"):
        gem_key = st.text_input("Gemini API Key (free — aistudio.google.com)", value=cfg.get('gemini_api_key',''), type="password", placeholder="AIza...")
        yt_key  = st.text_input("YouTube Data API Key (console.cloud.google.com)", value=cfg.get('youtube_api_key',''), type="password", placeholder="AIza...")

        section("Channel Info")
        ch_name = st.text_input("Channel Name", value=cfg.get('channel_name','AlgoQuant Trading'))
        bio     = st.text_input("Creator Bio", value=cfg.get('creator_bio','Financial engineer from Morocco, self-taught quant'))
        prods   = st.text_input("Products (comma separated)", value=cfg.get('products','SaaS, MQL5 EAs, courses, freelance'))

        section("Channel Stats")
        c1,c2,c3,c4 = st.columns(4)
        with c1: new_s = st.number_input("Subscribers", min_value=0, value=cfg.get('subscribers',5))
        with c2: new_h = st.number_input("Watch Hours", min_value=0.0, value=float(cfg.get('watch_hours',1.4)), format="%.1f")
        with c3: new_c = st.number_input("Avg CTR %", min_value=0.0, value=float(cfg.get('avg_ctr',2.5)), format="%.1f")
        with c4: new_v = st.number_input("Total Videos", min_value=0, value=cfg.get('total_videos',4))

        if st.form_submit_button("💾  Save Settings", use_container_width=True):
            st.session_state['config'] = {
                'gemini_api_key':gem_key,'youtube_api_key':yt_key,
                'channel_name':ch_name,'creator_bio':bio,'products':prods,
                'subscribers':new_s,'watch_hours':new_h,'avg_ctr':new_c,'total_videos':new_v,
            }
            st.success("✅  Settings saved")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    section("How to get your API keys")
    step_box("Gemini API (free)", "Go to aistudio.google.com → Sign in → Get API Key → Create API key → Select project ytgrowthengine → Copy key starting with AIza")
    step_box("YouTube Data API", "Go to console.cloud.google.com → Select project ytgrowthengine → APIs & Services → Credentials → Copy your existing API key")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    section("How to deploy this app")
    step_box("Local",    "pip install streamlit google-generativeai google-api-python-client pandas  →  streamlit run algoquant_studio.py")
    step_box("Streamlit Cloud (free)", "Push this file to a GitHub repo → go to share.streamlit.io → Connect repo → Deploy. Your app is live at a public URL.")


# ════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════

if   "🏠" in page: page_dashboard()
elif "🔍" in page: page_competitor()
elif "📊" in page: page_analytics()
elif "🏭" in page: page_factory()
elif "⚙️" in page: page_settings()
