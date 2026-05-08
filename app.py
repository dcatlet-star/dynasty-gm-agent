from flask import Flask, request, jsonify, send_from_directory
import anthropic
import os
import json
import sqlite3
from datetime import datetime, timedelta
import requests

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SLEEPER_LEAGUE_IDS = {
    "gentlemans": "1314472610167279616",
    "velvet_spade": "1315445968161734656"
}

def init_db():
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, week_key TEXT, role TEXT, content TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS player_rankings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT UNIQUE, position TEXT, team TEXT,
                  elo_score REAL DEFAULT 1500, comparisons INTEGER DEFAULT 0, last_updated TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS player_profiles
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT UNIQUE, profile_data TEXT, last_updated TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS dashboard_cache
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, cache_key TEXT UNIQUE, data TEXT, last_updated TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_week_key():
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    return week_start.strftime("%Y-W%U")

LEAGUE_CONTEXT = """
=== OWNER PROFILE ===
Username: MJBrutus (Sleeper: dcatlet)
Leagues: Capital Gains (#430 FFPC), Twenty Run Savages (#210 FFPC), Gentleman's Dynasty (Sleeper), Velvet Spade (Sleeper)
Primary valuation: KTC SuperFlex+TE format
Philosophy: Day-trading mindset, picks > players in rebuilds, prefer players under 28
League priority: Velvet Spade > TRS > Capital Gains > Gentleman's
Last updated: May 8, 2026

=== UNIVERSAL TRADE RULES ===
- Cornerstones: 25% KTC surplus required
- Standard trades: 5% surplus target | max 10% deficit if strong fit
- Never surrender more than 2 firsts without top-12 dynasty asset return
- Picks > players in rebuild leagues | Prefer players under 28
- Proactively surface 1+ trade per league per week
- Trade messages: under 20 words, 2 sentences max, direct and confident
- KTC SuperFlex+TE is primary valuation always

=== DATA SOURCES ===
1. KTC (keeptradecut.com) SuperFlex+TE always
2. RosterAudit (rosteraudit.com)
3. OurLads (ourlads.com) NFL depth charts
4. NFL.com official draft capital
5. Dynasty Data Lab (dynastydatalab.com)
6. FantasyPros, Rotoballer, ESPN, CBS Sports, Underdog (@UnderdogFantasy)
7. Schefter, Rapoport, Glazer breaking news
Flag data older than 72hrs with DATA WARNING. Always web search before answering.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEAGUE 1: CAPITAL GAINS — FFPC #430
$250 | 12-team SuperFlex TE Premium | 4pt pass TDs | 1.5 TE rec
Lineup: 1QB/2RB/3WR/1TE/1SFLX/2FLEX | No K/DST | 20+3IR | No taxi | FAAB $1000
Strategy: ACTIVE REBUILD 2027 contention | Priority: #3

UNTOUCHABLES: Drake Maye, Drake London
CORE: LaPorta, Burden, MHJ, Tate
MOVEABLE: Milroe, all RBs, depth WRs/TEs

ROSTER (29 players — cut to 20 September):
QB: Drake Maye(NE) | Jaxson Dart(NYG) | Carson Beck(ARI) | Jalen Milroe(SEA)
RB: Dylan Sampson(CLE) | Mike Washington(LV) | Tank Bigsby(PHI) | Kimani Vidal(LAC) | Jaylen Wright(MIA) | Devin Neal(NO)
WR: Drake London(ATL) | Luther Burden(CHI) | Carnell Tate(TEN) | MHJ(ARI) | Jalen Coker(CAR) | Denzel Boston(CLE) | Calvin Ridley(TEN) | Chris Brazzell(CAR) | Skyler Bell(BUF) | Chimere Dike(TEN) | Malachi Fields(NYG) | Jaylin Noel(HOU) | Caleb Douglas(MIA)
TE: Sam LaPorta(DET) | Chig Okonkwo(WAS) | Eli Stowers(PHI) | Mason Taylor(NYJ) | Max Klare(LAR) | Oscar Delp(NO)
2026 PICKS REMAINING: 6.03, 7.03
2027 PICKS: R1(own), R1(Dudesss), R1(GNAwin0), R1(TeddySalad), R2(own), R2(LegendsDie), R2(GNAwin0), R3-R7

CONSOLATION: Tank Wks 1-13 (bottom 2 VP) → WIN consolation Wks 14-17 → 1.01 pick 2027
SEPTEMBER CUTS (9 needed): Neal, Vidal, Wright, Sampson, Noel, Douglas, Coker, Okonkwo, Milroe

LEAGUE INTEL:
Boston Black Mambas: Allen/CMC/Saquon/Henry/Cook — LAST DANCE, 2027R1 could be top 4
Seize The Grey: Burrow/Herbert/Love — CONTENDER thin picks
GNAwin0DSFTF: Lawrence/Jeanty/Tuten — MID, owns dcatlet 2027 picks
Blunderbuss 430: Mahomes/Swift/Pollard — CONTENDER, has LegendsDie 2027R1
TeddySaladTF: Daniels/Murray/Bowers — MID no early 2027 picks
Legends Never Die: C.Williams/Mayfield/Jacobs — REBUILDING only R6/R7
Mayan Factors: Lamar/Goff/Gibbs/Kittle — CONTENDER 2027R1
Risk It Brisket: Hurts/Purdy/Bijan/AJBrown — CONTENDER thin picks
Shoot The Glass: Allen/Mahomes/Barkley/Bowers — ELITE CONTENDER

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEAGUE 2: TWENTY RUN SAVAGES — FFPC #210
$100 | 12-team SuperFlex TE Premium + K+DST | 20+3IR | No taxi | FAAB $1000
Strategy: COMPETING NOW | Priority: #2
K+DST REQUIRED ALWAYS — Boswell(K) + TB DST currently rostered

UNTOUCHABLES: Drake Maye, Bijan Robinson
CORE: Loveland, JSN, Lemon
MOVEABLE: Mayfield, Watson, depth

ROSTER (23 players confirmed May 8):
QB: Drake Maye(NE) | Baker Mayfield(TB) | Deshaun Watson(CLE)
RB: Bijan Robinson(ATL) | Rico Dowdle(PIT) | Kyle Monangai(CHI) | Dylan Sampson(CLE) | Emmett Johnson(KC)
WR: JSN(SEA) | Mike Evans(SF) | Makai Lemon(PHI) | Jakobi Meyers(JAC) | KC Concepcion(CLE) | Josh Downs(IND) | Jalen McMillan(TB) | Adonai Mitchell(NYJ) | Zachariah Branch(ATL)
TE: Colston Loveland(CHI) | Dallas Goedert(PHI) | Brenton Strange(JAC) | Eli Raridon(NE)
K: Chris Boswell(PIT) | DST: TB Team Defense
2026 PICKS: 3.07, 4.03(Marino's), 4.07, 5.03(Marino's), 5.07, 6.07, 7.07
2027 PICKS: R1(Stinky), R1(own), R2(own), R3-R7

LEAGUE INTEL:
Shoot The Glass: Allen/Mahomes/Barkley/Bowers/Andrews — ELITE
Boulder Free Zone: Lamar/CMC/Jeanty/LaPorta/Sadiq — STRONG
Evil Empire: C.Williams/Hurts/Gibbs/J.Taylor — CONTENDER
Settler22$: Willis/Stroud/Sanders/Judkins/Tate — STRONG has 2026 R1.08
Stinky: Burrow/Love/C.Brown — has 2027R1 owed to dcatlet
Nuclear Options: Stafford/Ward — FULL REBUILD entire pick stack
H2OSONDC: Daniels/Prescott/Murray/Kittle/Hockenson — STRONG
Marino's Isotoners: Mendoza/Tua/Stowers — has dcatlet Marino 2026 picks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEAGUE 3: GENTLEMAN'S DYNASTY — SLEEPER FREE
14-team | SuperFlex | TE Premium 1.5 | 4pt TDs | -2 fumble | K+DST
23+3IR+4taxi | FAAB $200 | Trade deadline Wk14
Strategy: REBUILD 2027-28 | Priority: #4
Sleeper ID: 1314472610167279616

UNTOUCHABLES: Mahomes, Bowers
CORE: Judkins, MHJ, Tate

MAX PF WARNING: Taxi squad points COUNT toward Max PF seeding. Monitor weekly.

ROSTER:
QB: Mahomes(KC)LOCK | McCarthy(MIN)sell | Flacco(CIN)sell | Richardson(IND)sell | Rodgers sell
RB: Judkins(CLE) | Tuten(JAX) | McLaughlin(DEN) | Benson(ARI) | T.Etienne(CAR) | Kamara(NO)sell
WR: MHJ(ARI) | Higgins(HOU) | Meyers(JAX) | Shaheed(SEA) | McCaffrey(WAS) | T.Hunter(JAX) | Thornton(LV) | Kupp(SEA) | Tolbert(MIA)
TE: Bowers(LV)LOCK | Njoku(FA)sell | All(CIN)
TAXI: Tate(WR-TEN) | Bell(WR-MIA) | Klare(TE-LAR)
2027: 1st(own), 2nd(Stiller29), 2nd(own), 4th | 2028: 1st, 2nd, 3rd, 4th

GM SCOUTING:
c1smith11: LaPorta on block → #1 acquisition target
McGido: Desperate TE#14 → sell Njoku
Goooz: Desperate TE#12 → secondary Njoku target
SenorHyde: Desperate QB#14 → sell McCarthy/Richardson
mstan16: Desperate RB#14 → sell Kamara/Etienne
DynastyMad: Desperate WR#13 → sell WR depth

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEAGUE 4: VELVET SPADE — SLEEPER $250/$525 startup
12-team | SuperFlex | TE Premium 1.5 | 6PT PASSING TDs
1QB/2RB/2WR/1TE/3FLEX/1SFLX | 23+5taxi+2IR | Max 30
FAAB $1000 tradeable | Waivers Wed 3AM ET | Trade deadline Wk13
Startup May 15 2026 | 28 rounds | Snake + 3rd round reversal | 12hr timer
Sleeper ID: 1315445968161734656 | Priority: #1

SCORING: All TDs 6pt | Pass 0.04/yd | Rush/Rec 0.1/yd | PPR RB/WR 1.0 TE 1.5
BONUSES: 40+yd play +1 | 400+pass yd +2 | 200+rush/rec yd +2 | -2 INT | -2 fumble

DRAFT ORDER: 1.pdwyer13 2.dcatlet(YOU) 3.yerkdog 4.jefisk24 5.Smohr609
6.ColeTrain8300 7.DrTrollPhD 8.colinmonie 9.EazyDakar 10.jakemills69 11.NateSneller 12.sneller
3RD ROUND REVERSAL: Rounds 2 AND 3 both reversed (sneller gets 2.01 AND 3.01)

YOUR PICKS: 1.02|2.11|3.11|4.02|5.11|6.02|7.11|8.02|9.11|10.02|11.11|12.02...pattern: 2nd odd rounds, 11th even rounds
Near back-to-back: 5.11+6.02, 7.11+8.02, 9.11+10.02 etc.

STARTUP STRATEGY: 6pt TDs = elite QBs 15-20% more valuable. NEVER leave R1 without elite QB.
BUILD A: 1.02 Maye → 2.11 elite WR/RB → 3.11 second elite → 4.02 young RB/WR
BUILD B: 1.02 Bijan → 2.11 Maye/Allen → 3.11 elite WR → 4.02 second position
BUILD C: Trade back to 1.04-1.06 + extra pick (only if staying top 6)

STARTUP PICK VALUES (6pt TD adjusted):
1.01:10000 1.02:9500 1.03:8800 1.04:7800 1.05:7000 1.06:6300 1.07:5600 1.08:5000
1.09:4400 1.10:3900 1.11:3400 1.12:2900 2.01:2600 2.02:2400 2.03:2200 2.04:2050
2.05:1900 2.06:1750 2.07:1600 2.08:1450 2.09:1300 2.10:1150 2.11:1000 2.12:850
3.01:800 3.02:750 3.03:700 3.04:650 3.05:600 3.06:560 3.07:520 3.08:480 3.09:440 3.10:410 3.11:380 3.12:350
4.01:320 4.02:300 4.03:280 4.04:260 4.05:245 4.06:230 4.07:215 4.08:200 4.09:185 4.10:172 4.11:160 4.12:148
Trade threshold: execute if within 15% of fair value

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOKIE RANKINGS (May 8 2026 KTC SuperFlex+TE):
GONE: Love|Tate|Mendoza|Tyson|Lemon|Price|Sadiq|Concepcion|Simpson|Cooper|Stowers|Boston
AVAILABLE: Coleman 2940|Bell 2904(+8)|Singleton 2877|Bernard 2860(+10)|Sarratt 2709
Brazzell 2621|Branch 2563|Fields 2542(+3)|M.Washington 2502|A.Williams 2445(+7)
Klare 2286(+1)|S.Bell 2326|Lane 2283|Allen 2273|Hurst 1853|Nussmeier 1763
Stribling 1575(+19)|Klubnik 1571|Trigg 1546|Claiborne 1429|Allar 1001|Beck 993|Delp 1154|Raridon 734|Joly ~700

KTC BASELINE May 2 2026 (flag 500+ moves):
Maye 9500|Bowers 8100|Bijan 8200|JSN 7800|London 6500|Loveland 6200|LaPorta 5800
Mahomes 5600|MHJ 5200|Lemon 4978|Tate 4567|Dart 4500|Concepcion 4452|Judkins 3500
Downs 3800|McCarthy 3200|Richardson 2800|Mayfield 2800|Watson 1800|Tuten 1500
"""

SYSTEM_PROMPT = f"""You are an elite dynasty fantasy football Assistant GM for MJBrutus. You manage 4 leagues with different strategies, scoring systems, and timelines. Deep expertise in dynasty formats, startup drafts, trade theory, and roster construction.

{LEAGUE_CONTEXT}

CORE BEHAVIORS:
1. ALWAYS web search for current player values, injuries, depth charts before answering
2. KTC SuperFlex+TE primary. Cross-reference RosterAudit, FantasyPros, Rotoballer, ESPN, Underdog
3. Check ourlads.com for NFL depth charts | NFL.com for draft capital
4. One clear decisive recommendation — not a menu
5. Flag data older than 72hrs with DATA WARNING
6. Apply trade rules strictly — flag any deal outside 10% deficit
7. Always identify which league and strategy phase applies
8. Factor scoring differences — especially 6pt TDs in Velvet Spade
9. Surface 1+ trade opportunity per league per week proactively
10. Trade messages: under 20 words, 2 sentences max, direct and confident
11. Track KTC vs May 2 baseline — flag 500+ point moves
12. Gentleman's: monitor Max PF taxi implications weekly
13. TRS: confirm K+DST always rostered
14. Velvet Spade: use startup pick value chart for all trade up/down analysis
15. Capital Gains: always factor two-phase consolation strategy

RESPONSE FORMAT: Lead with recommendation | Current data + sources + dates | Risks and concerns | Specific action item | Headers for complex analysis | Mobile-friendly

TRADE MESSAGE: Under 20 words | 2 sentences | State exact terms | Direct, no hedging
Example: "Sending Njoku and a 2027 2nd for LaPorta. Works for both of us."

PROACTIVE: Surface opportunities unprompted. Flag material situation changes across all leagues. Weekly: 1 specific trade offer per league."""

DEFAULT_PLAYERS = [
    ("Drake Maye", "QB", "NE"), ("Brock Bowers", "TE", "LV"), ("Bijan Robinson", "RB", "ATL"),
    ("Ja'Marr Chase", "WR", "CIN"), ("Justin Jefferson", "WR", "MIN"), ("CeeDee Lamb", "WR", "DAL"),
    ("Breece Hall", "RB", "NYJ"), ("Sam LaPorta", "TE", "DET"), ("Jayden Daniels", "QB", "WAS"),
    ("Carnell Tate", "WR", "TEN"), ("Makai Lemon", "WR", "PHI"), ("Jordyn Tyson", "WR", "NO"),
    ("Jadarian Price", "RB", "SEA"), ("Kenyon Sadiq", "TE", "NYJ"), ("KC Concepcion", "WR", "CLE"),
    ("Patrick Mahomes", "QB", "KC"), ("Josh Allen", "QB", "BUF"), ("Lamar Jackson", "QB", "BAL"),
    ("Ashton Jeanty", "RB", "LV"), ("Christian McCaffrey", "RB", "SF"), ("Colston Loveland", "TE", "CHI"),
    ("Quinshon Judkins", "RB", "CLE"), ("Drake London", "WR", "ATL"), ("Luther Burden", "WR", "CHI"),
    ("Marvin Harrison Jr", "WR", "ARI"), ("Jaxson Dart", "QB", "NYG"), ("Jaxon Smith-Njigba", "WR", "SEA"),
    ("Malik Nabers", "WR", "NYG"), ("Brian Thomas", "WR", "JAC"), ("Puka Nacua", "WR", "LAR"),
    ("De'Von Achane", "RB", "MIA"), ("Jahmyr Gibbs", "RB", "DET"), ("Travis Hunter", "WR", "JAC"),
    ("Amon-Ra St. Brown", "WR", "DET"), ("Zay Flowers", "WR", "BAL"), ("Ladd McConkey", "WR", "LAC"),
    ("Dallas Goedert", "TE", "PHI"), ("Travis Kelce", "TE", "KC"), ("Mark Andrews", "TE", "BAL"),
    ("Jeremiyah Love", "RB", "ARI"), ("Fernando Mendoza", "QB", "LV"), ("Eli Stowers", "TE", "PHI"),
]

def seed_players():
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    for name, pos, team in DEFAULT_PLAYERS:
        c.execute("INSERT OR IGNORE INTO player_rankings (player_name, position, team, elo_score, comparisons, last_updated) VALUES (?, ?, ?, 1500, 0, ?)",
                 (name, pos, team, datetime.now().isoformat()))
    conn.commit()
    conn.close()

seed_players()

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    image_data = data.get('image', None)
    week_key = get_week_key()

    if image_data:
        image_content = image_data.split(',')[1] if ',' in image_data else image_data
        media_type = 'image/png' if 'png' in image_data else 'image/jpeg'
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_content}},
            {"type": "text", "text": user_message if user_message else "Analyze this screenshot for my dynasty leagues."}
        ]
    else:
        content = user_message

    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_history WHERE week_key=? ORDER BY id", (week_key,))
    history_rows = c.fetchall()
    conn.close()

    messages = []
    for role, msg_content in history_rows:
        try:
            parsed = json.loads(msg_content)
            messages.append({"role": role, "content": parsed})
        except:
            messages.append({"role": role, "content": msg_content})

    messages.append({"role": "user", "content": content})
    if len(messages) > 20:
        messages = messages[-20:]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=messages
        )

        assistant_message = ""
        for block in response.content:
            if hasattr(block, 'text'):
                assistant_message += block.text

        conn = sqlite3.connect('dynasty.db')
        c = conn.cursor()
        user_content_str = json.dumps(content) if isinstance(content, list) else content
        c.execute("INSERT INTO chat_history (week_key, role, content, timestamp) VALUES (?, ?, ?, ?)",
                 (week_key, 'user', user_content_str, datetime.now().isoformat()))
        c.execute("INSERT INTO chat_history (week_key, role, content, timestamp) VALUES (?, ?, ?, ?)",
                 (week_key, 'assistant', assistant_message, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        return jsonify({"response": assistant_message, "success": True})
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}", "success": False})

@app.route('/api/chat/history', methods=['GET'])
def get_history():
    week_key = get_week_key()
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp FROM chat_history WHERE week_key=? ORDER BY id", (week_key,))
    rows = c.fetchall()
    conn.close()
    history = []
    for role, content, timestamp in rows:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                text = next((b.get('text','') for b in parsed if isinstance(b,dict) and b.get('type')=='text'), '')
                has_image = any(isinstance(b,dict) and b.get('type')=='image' for b in parsed)
                history.append({"role": role, "content": text, "has_image": has_image, "timestamp": timestamp})
            else:
                history.append({"role": role, "content": content, "has_image": False, "timestamp": timestamp})
        except:
            history.append({"role": role, "content": content, "has_image": False, "timestamp": timestamp})
    return jsonify({"history": history, "success": True})

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    week_key = get_week_key()
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE week_key=?", (week_key,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/chat/search', methods=['POST'])
def search_chat():
    query = request.json.get('query', '').lower()
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp, week_key FROM chat_history ORDER BY id DESC LIMIT 500")
    rows = c.fetchall()
    conn.close()
    results = []
    for role, content, timestamp, week_key in rows:
        if query in content.lower():
            results.append({"role": role, "content": content[:300], "timestamp": timestamp, "week": week_key})
        if len(results) >= 20:
            break
    return jsonify({"results": results, "success": True})

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
            messages=[{"role": "user", "content": """Generate a dynasty GM dashboard. Return ONLY valid JSON:
{"alerts":[{"type":"warning|info|opportunity","league":"league","message":"text","action":"what to do"}],
"news":[{"player":"name","team":"team","leagues":["which leagues"],"headline":"news","impact":"dynasty impact","recommendation":"BUY|SELL|HOLD|MONITOR"}],
"movers":[{"player":"name","direction":"up|down","change":"amount","reason":"why","action":"what to do"}],
"trade_targets":[{"player":"name","owner":"their team","league":"which league","offer":"under 20 words","rationale":"why"}],
"weekly_priorities":["priority 1","priority 2","priority 3"]}"""}]
        )
        assistant_message = "".join(b.text for b in response.content if hasattr(b, 'text'))
        cleaned = assistant_message.strip().lstrip('```json').lstrip('```').rstrip('```').strip()
        return jsonify({"data": json.loads(cleaned), "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

@app.route('/api/player/profile', methods=['POST'])
def get_player_profile():
    player_name = request.json.get('player', '')
    league = request.json.get('league', 'all')
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT profile_data, last_updated FROM player_profiles WHERE player_name=?", (player_name,))
    row = c.fetchone()
    conn.close()
    if row:
        last_updated = datetime.fromisoformat(row[1])
        if datetime.now() - last_updated < timedelta(hours=24):
            return jsonify({"profile": json.loads(row[0]), "success": True, "cached": True})
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": f"""Create dynasty player profile for {player_name}, league context: {league}. Return ONLY valid JSON:
{{"name":"","position":"","team":"","age":0,"ktc_value":0,"ktc_trend":"","position_rank":"","trade_liquidity":"High|Medium|Low","recommendation":"BUY|SELL|HOLD","recommendation_reason":"","league_specific":{{"Capital Gains":"","TRS":"","Gentlemans":"","Velvet Spade":""}},"latest_news":[],"dynasty_outlook":"","injury_history":"","contract_status":"","depth_chart":"","startup_adp":"","ppg_2025":0,"ppg_2024":0}}"""}]
        )
        assistant_message = "".join(b.text for b in response.content if hasattr(b, 'text'))
        cleaned = assistant_message.strip().lstrip('```json').lstrip('```').rstrip('```').strip()
        profile = json.loads(cleaned)
        conn = sqlite3.connect('dynasty.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO player_profiles (player_name, profile_data, last_updated) VALUES (?, ?, ?)",
                 (player_name, json.dumps(profile), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"profile": profile, "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

@app.route('/api/rankings/pair', methods=['GET'])
def get_ranking_pair():
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT player_name, position, team, elo_score, comparisons FROM player_rankings ORDER BY comparisons ASC, RANDOM() LIMIT 2")
    rows = c.fetchall()
    conn.close()
    players = [{"name": r[0], "position": r[1], "team": r[2], "elo": r[3], "comparisons": r[4]} for r in rows]
    return jsonify({"players": players, "success": True})

@app.route('/api/rankings/vote', methods=['POST'])
def submit_vote():
    winner = request.json.get('winner')
    loser = request.json.get('loser')
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT elo_score FROM player_rankings WHERE player_name=?", (winner,))
    w_row = c.fetchone()
    c.execute("SELECT elo_score FROM player_rankings WHERE player_name=?", (loser,))
    l_row = c.fetchone()
    if w_row and l_row:
        k = 32
        w_elo, l_elo = w_row[0], l_row[0]
        exp_w = 1 / (1 + 10 ** ((l_elo - w_elo) / 400))
        exp_l = 1 / (1 + 10 ** ((w_elo - l_elo) / 400))
        c.execute("UPDATE player_rankings SET elo_score=?, comparisons=comparisons+1, last_updated=? WHERE player_name=?",
                 (w_elo + k * (1 - exp_w), datetime.now().isoformat(), winner))
        c.execute("UPDATE player_rankings SET elo_score=?, comparisons=comparisons+1, last_updated=? WHERE player_name=?",
                 (l_elo + k * (0 - exp_l), datetime.now().isoformat(), loser))
        conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/rankings/list', methods=['GET'])
def get_rankings():
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("SELECT player_name, position, team, elo_score, comparisons FROM player_rankings ORDER BY elo_score DESC LIMIT 200")
    rows = c.fetchall()
    conn.close()
    rankings = [{"rank": i+1, "name": r[0], "position": r[1], "team": r[2], "elo": round(r[3]), "comparisons": r[4]} for i, r in enumerate(rows)]
    return jsonify({"rankings": rankings, "success": True})

@app.route('/api/rankings/add', methods=['POST'])
def add_player():
    name = request.json.get('name', '')
    position = request.json.get('position', '')
    team = request.json.get('team', '')
    if not name:
        return jsonify({"success": False, "error": "Name required"})
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO player_rankings (player_name, position, team, elo_score, comparisons, last_updated) VALUES (?, ?, ?, 1500, 0, ?)",
             (name, position, team, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/trade/evaluate', methods=['POST'])
def evaluate_trade():
    data = request.json
    league = data.get('league', '')
    giving = data.get('giving', [])
    receiving = data.get('receiving', [])
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": f"""Evaluate this trade for {league}:
GIVING: {', '.join(giving)}
RECEIVING: {', '.join(receiving)}
Return ONLY valid JSON:
{{"verdict":"ACCEPT|DECLINE|COUNTER","value_giving":0,"value_receiving":0,"surplus_pct":0,"within_threshold":true,"analysis":"","my_perspective":"","their_perspective":"","counter":"","trade_message":"under 20 words","positional_fit":"","strategy_fit":""}}"""}]
        )
        assistant_message = "".join(b.text for b in response.content if hasattr(b, 'text'))
        cleaned = assistant_message.strip().lstrip('```json').lstrip('```').rstrip('```').strip()
        return jsonify({"result": json.loads(cleaned), "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

@app.route('/api/draft/chart', methods=['GET'])
def get_draft_chart():
    chart = {
        "pick_values": {
            "1.01":10000,"1.02":9500,"1.03":8800,"1.04":7800,"1.05":7000,"1.06":6300,
            "1.07":5600,"1.08":5000,"1.09":4400,"1.10":3900,"1.11":3400,"1.12":2900,
            "2.01":2600,"2.02":2400,"2.03":2200,"2.04":2050,"2.05":1900,"2.06":1750,
            "2.07":1600,"2.08":1450,"2.09":1300,"2.10":1150,"2.11":1000,"2.12":850,
            "3.01":800,"3.02":750,"3.03":700,"3.04":650,"3.05":600,"3.06":560,
            "3.07":520,"3.08":480,"3.09":440,"3.10":410,"3.11":380,"3.12":350,
            "4.01":320,"4.02":300,"4.03":280,"4.04":260,"4.05":245,"4.06":230,
            "4.07":215,"4.08":200,"4.09":185,"4.10":172,"4.11":160,"4.12":148
        },
        "my_picks": ["1.02","2.11","3.11","4.02","5.11","6.02","7.11","8.02","9.11","10.02"],
        "scoring_notes": "6pt TD format. Elite QBs (Maye, Allen, Lamar) worth ~20% premium.",
        "execute_threshold": 0.15
    }
    return jsonify({"chart": chart, "success": True})

@app.route('/api/sleeper/sync', methods=['POST'])
def sync_sleeper():
    results = {}
    try:
        url = "https://api.sleeper.app/v1/players/nfl"
        r = requests.get(url, timeout=30)
        players_db = r.json() if r.status_code == 200 else {}
    except:
        players_db = {}
    for league_name, league_id in SLEEPER_LEAGUE_IDS.items():
        try:
            rosters_r = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters", timeout=10)
            users_r = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users", timeout=10)
            if rosters_r.status_code == 200 and users_r.status_code == 200:
                rosters = rosters_r.json()
                users = users_r.json()
                user_map = {u['user_id']: u.get('display_name', u['user_id']) for u in users}
                league_rosters = []
                for roster in rosters:
                    owner_name = user_map.get(roster.get('owner_id'), 'Unknown')
                    player_names = []
                    for pid in roster.get('players', []):
                        if pid in players_db:
                            p = players_db[pid]
                            name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                            player_names.append(f"{name} ({p.get('position','')}-{p.get('team','FA')})")
                    league_rosters.append({"owner": owner_name, "players": player_names})
                results[league_name] = league_rosters
        except Exception as e:
            results[league_name] = {"error": str(e)}
    return jsonify({"rosters": results, "success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
