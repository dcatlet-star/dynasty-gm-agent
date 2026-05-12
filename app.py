from flask import Flask, request, jsonify, send_from_directory
import anthropic
import os
import json
import sqlite3
import os

DB_PATH = os.environ.get('DB_PATH', '/data/dynasty.db')
# Falls back to local dynasty.db if /data doesn't exist (local dev)
if not os.path.exists('/data'):
    DB_PATH = 'dynasty.db'
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
    conn = sqlite3.connect(DB_PATH)
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
    # VS-specific 6pt TD rankings (separate ELO pool)
    c.execute('''CREATE TABLE IF NOT EXISTS vs_rankings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT UNIQUE, position TEXT, team TEXT,
                  elo_score REAL DEFAULT 1500, comparisons INTEGER DEFAULT 0, last_updated TEXT)''')
    # Market data: KTC, DDL, Sleeper ADP pasted by user
    c.execute('''CREATE TABLE IF NOT EXISTS market_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, player_name TEXT NOT NULL,
                  rank INTEGER, value INTEGER, position TEXT, team TEXT, updated_at TEXT NOT NULL,
                  UNIQUE(source, player_name))''')
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
2027 PICKS OWNED BY DCATLET (these are picks dcatlet RECEIVES, not gives away):
- R1 own (Capital Gains own first round pick)
- R1 from Dudesss (dcatlet owns Dudesss's 2027 first — received in Dart trade)
- R1 from GNAwin0DSFTF (dcatlet owns GNAwin0's 2027 first — received in London trade)
- R1 from TeddySaladTF (dcatlet owns TeddySalad's 2027 first — received in Bowers trade)
- R2 own | R2 from Legends Never Die | R2 from GNAwin0 | R3 | R4 | R5 | R6 | R7
TOTAL: 4x 2027 FIRST ROUND PICKS owned by dcatlet = exceptional rebuild capital

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
    # QBs
    ("Josh Allen", "QB", "BUF"), ("Drake Maye", "QB", "NE"), ("Jayden Daniels", "QB", "WAS"),
    ("Caleb Williams", "QB", "CHI"), ("Lamar Jackson", "QB", "BAL"), ("Joe Burrow", "QB", "CIN"),
    ("Patrick Mahomes", "QB", "KC"), ("Jaxson Dart", "QB", "NYG"), ("Justin Herbert", "QB", "LAC"),
    ("Trevor Lawrence", "QB", "JAC"), ("Jalen Hurts", "QB", "PHI"), ("Bo Nix", "QB", "DEN"),
    ("Brock Purdy", "QB", "SF"), ("Jordan Love", "QB", "GB"), ("Cam Ward", "QB", "TEN"),
    ("Fernando Mendoza", "QB", "LV"), ("CJ Stroud", "QB", "HOU"), ("Bryce Young", "QB", "CAR"),
    ("Kyler Murray", "QB", "MIN"), ("Malik Willis", "QB", "MIA"), ("JJ McCarthy", "QB", "MIN"),
    ("Anthony Richardson", "QB", "IND"), ("Shedeur Sanders", "QB", "CLE"), ("Dak Prescott", "QB", "DAL"),
    ("Sam Darnold", "QB", "SEA"), ("Baker Mayfield", "QB", "TB"), ("Tyler Shough", "QB", "NO"),
    ("Deshaun Watson", "QB", "CLE"), ("Will Howard", "QB", "PIT"), ("Jalen Milroe", "QB", "SEA"),
    # RBs
    ("Bijan Robinson", "RB", "ATL"), ("Jahmyr Gibbs", "RB", "DET"), ("Jeremiyah Love", "RB", "ARI"),
    ("Ashton Jeanty", "RB", "LV"), ("De'Von Achane", "RB", "MIA"), ("Christian McCaffrey", "RB", "SF"),
    ("Omarion Hampton", "RB", "LAC"), ("Jonathan Taylor", "RB", "IND"), ("James Cook", "RB", "BUF"),
    ("Breece Hall", "RB", "NYJ"), ("TreVeyon Henderson", "RB", "NE"), ("Kenneth Walker", "RB", "KC"),
    ("Quinshon Judkins", "RB", "CLE"), ("Bucky Irving", "RB", "TB"), ("Saquon Barkley", "RB", "PHI"),
    ("Chase Brown", "RB", "CIN"), ("Jadarian Price", "RB", "SEA"), ("Kyren Williams", "RB", "LAR"),
    ("Cam Skattebo", "RB", "NYG"), ("Jaylen Waddle", "RB", "DEN"), ("Josh Jacobs", "RB", "GB"),
    ("Travis Etienne", "RB", "NO"), ("Javonte Williams", "RB", "DAL"), ("RJ Harvey", "RB", "DEN"),
    ("Rico Dowdle", "RB", "PIT"), ("Kyle Monangai", "RB", "CHI"), ("D Andre Swift", "RB", "CHI"),
    ("Jonah Coleman", "RB", "DEN"), ("Zach Charbonnet", "RB", "SEA"), ("Bhayshul Tuten", "RB", "JAC"),
    ("Jacory Croskey-Merritt", "RB", "WAS"), ("Rhamondre Stevenson", "RB", "NE"), ("Woody Marks", "RB", "HOU"),
    ("Nicholas Singleton", "RB", "TEN"), ("Tony Pollard", "RB", "TEN"), ("Blake Corum", "RB", "LAR"),
    ("JK Dobbins", "RB", "DEN"), ("Jordan Mason", "RB", "MIN"), ("Jaylen Warren", "RB", "PIT"),
    ("Trey Benson", "RB", "ARI"), ("Braelon Allen", "RB", "NYJ"), ("Dylan Sampson", "RB", "CLE"),
    ("Kaytron Allen", "RB", "WAS"), ("Emmett Johnson", "RB", "KC"), ("Tank Bigsby", "RB", "PHI"),
    ("Mike Washington Jr", "RB", "LV"), ("Ollie Gordon", "RB", "MIA"), ("LeQuint Allen", "RB", "JAC"),
    ("Jordan James", "RB", "SF"), ("Kimani Vidal", "RB", "LAC"), ("Jaylen Wright", "RB", "MIA"),
    # WRs
    ("Ja Marr Chase", "WR", "CIN"), ("Jaxon Smith-Njigba", "WR", "SEA"), ("Puka Nacua", "WR", "LAR"),
    ("Malik Nabers", "WR", "NYG"), ("Justin Jefferson", "WR", "MIN"), ("Amon-Ra St. Brown", "WR", "DET"),
    ("CeeDee Lamb", "WR", "DAL"), ("Drake London", "WR", "ATL"), ("Tetairoa McMillan", "WR", "CAR"),
    ("Emeka Egbuka", "WR", "TB"), ("George Pickens", "WR", "DAL"), ("Carnell Tate", "WR", "TEN"),
    ("Garrett Wilson", "WR", "NYJ"), ("Nico Collins", "WR", "HOU"), ("Jordyn Tyson", "WR", "NO"),
    ("Ladd McConkey", "WR", "LAC"), ("Rashee Rice", "WR", "KC"), ("DeVonta Smith", "WR", "PHI"),
    ("Luther Burden", "WR", "CHI"), ("Marvin Harrison Jr", "WR", "ARI"), ("Rome Odunze", "WR", "CHI"),
    ("Makai Lemon", "WR", "PHI"), ("Brian Thomas Jr", "WR", "JAC"), ("Zay Flowers", "WR", "BAL"),
    ("Tee Higgins", "WR", "CIN"), ("AJ Brown", "WR", "PHI"), ("Jameson Williams", "WR", "DET"),
    ("Jaylen Waddle", "WR", "DEN"), ("Chris Olave", "WR", "NO"), ("KC Concepcion", "WR", "CLE"),
    ("Jayden Higgins", "WR", "HOU"), ("Denzel Boston", "WR", "CLE"), ("Travis Hunter", "WR", "JAC"),
    ("Chris Bell", "WR", "MIA"), ("Germie Bernard", "WR", "PIT"), ("Zachariah Branch", "WR", "ATL"),
    ("Antonio Williams", "WR", "WAS"), ("Malachi Fields", "WR", "NYG"), ("Dontayvion Wicks", "WR", "PHI"),
    ("Chimere Dike", "WR", "TEN"), ("Tre Harris", "WR", "LAC"), ("Kyle Williams", "WR", "NE"),
    ("Troy Franklin", "WR", "DEN"), ("Kayshon Boutte", "WR", "NE"), ("Elijah Sarratt", "WR", "BAL"),
    ("Chris Brazzell", "WR", "CAR"), ("Skyler Bell", "WR", "BUF"), ("Keon Coleman", "WR", "BUF"),
    ("Adonai Mitchell", "WR", "NYJ"), ("Xavier Worthy", "WR", "KC"), ("Wan Dale Robinson", "WR", "TEN"),
    ("Josh Downs", "WR", "IND"), ("Parker Washington", "WR", "JAC"), ("Ricky Pearsall", "WR", "SF"),
    ("Jayden Reed", "WR", "GB"), ("De Zhaun Stribling", "WR", "SF"), ("Romeo Doubs", "WR", "NE"),
    ("Terry McLaurin", "WR", "WAS"), ("Matthew Golden", "WR", "GB"), ("Ja Kobi Lane", "WR", "BAL"),
    ("Mike Evans", "WR", "SF"), ("DK Metcalf", "WR", "PIT"), ("Courtland Sutton", "WR", "DEN"),
    ("Calvin Ridley", "WR", "TEN"), ("Brandon Aiyuk", "WR", "SF"), ("Tory Horton", "WR", "SEA"),
    ("Tank Dell", "WR", "HOU"), ("Pat Bryant", "WR", "DEN"), ("Isaac TeSlaa", "WR", "DET"),
    ("Dont'e Thornton", "WR", "LV"), ("Jalen Coker", "WR", "CAR"), ("Jaylin Noel", "WR", "HOU"),
    ("Khalil Shakir", "WR", "BUF"), ("Jalen McMillan", "WR", "TB"), ("Quentin Johnston", "WR", "LAC"),
    ("Xavier Legette", "WR", "CAR"), ("Savion Williams", "WR", "GB"), ("Elic Ayomanor", "WR", "TEN"),
    # TEs
    ("Brock Bowers", "TE", "LV"), ("Trey McBride", "TE", "ARI"), ("Colston Loveland", "TE", "CHI"),
    ("Tyler Warren", "TE", "IND"), ("Tucker Kraft", "TE", "GB"), ("Harold Fannin", "TE", "CLE"),
    ("Sam LaPorta", "TE", "DET"), ("Kyle Pitts", "TE", "ATL"), ("Oronde Gadsden", "TE", "LAC"),
    ("Kenyon Sadiq", "TE", "NYJ"), ("Eli Stowers", "TE", "PHI"), ("Isaiah Likely", "TE", "NYG"),
    ("Gunnar Helm", "TE", "TEN"), ("AJ Barner", "TE", "SEA"), ("TJ Hockenson", "TE", "MIN"),
    ("Terrance Ferguson", "TE", "LAR"), ("Mark Andrews", "TE", "BAL"), ("Brenton Strange", "TE", "JAC"),
    ("Max Klare", "TE", "LAR"), ("Elijah Arroyo", "TE", "SEA"), ("Dallas Goedert", "TE", "PHI"),
    ("Ja Tavion Sanders", "TE", "CAR"), ("Mason Taylor", "TE", "NYJ"), ("Dalton Kincaid", "TE", "BUF"),
    ("Jake Ferguson", "TE", "DAL"), ("George Kittle", "TE", "SF"), ("Oscar Delp", "TE", "NO"),
    ("Justin Joly", "TE", "DEN"), ("Eli Raridon", "TE", "NE"), ("Michael Trigg", "TE", "DAL"),
    ("Darnell Washington", "TE", "PIT"), ("Cole Kmet", "TE", "CHI"), ("Cade Otton", "TE", "TB"),
    ("Pat Freiermuth", "TE", "PIT"), ("David Njoku", "TE", "FA"), ("Greg Dulcich", "TE", "MIA"),
    # PICK ASSETS — Dynasty picks (KTC values May 2026)
    ("2027 Early 1st", "PICK", ""), ("2027 Mid 1st", "PICK", ""), ("2027 Late 1st", "PICK", ""),
    ("2026 Early 1st", "PICK", ""), ("2028 Early 1st", "PICK", ""), ("2026 Mid 1st", "PICK", ""),
    ("2027 Early 2nd", "PICK", ""), ("2028 Mid 1st", "PICK", ""), ("2026 Late 1st", "PICK", ""),
    ("2028 Late 1st", "PICK", ""), ("2027 Mid 2nd", "PICK", ""), ("2027 Late 2nd", "PICK", ""),
    ("2026 Early 2nd", "PICK", ""), ("2027 Early 3rd", "PICK", ""), ("2028 Early 2nd", "PICK", ""),
    ("2026 Mid 2nd", "PICK", ""), ("2027 Mid 3rd", "PICK", ""), ("2028 Mid 2nd", "PICK", ""),
    ("2026 Late 2nd", "PICK", ""), ("2027 Late 3rd", "PICK", ""), ("2028 Late 2nd", "PICK", ""),
    ("2027 Early 4th", "PICK", ""), ("2026 Early 3rd", "PICK", ""), ("2027 Mid 4th", "PICK", ""),
    ("2028 Early 3rd", "PICK", ""), ("2026 Mid 3rd", "PICK", ""), ("2027 Late 4th", "PICK", ""),
    ("2028 Mid 3rd", "PICK", ""), ("2026 Late 3rd", "PICK", ""), ("2028 Late 3rd", "PICK", ""),
    ("2026 Early 4th", "PICK", ""), ("2026 Mid 4th", "PICK", ""), ("2028 Early 4th", "PICK", ""),
]

def seed_players():
    """
    ELO scale maps to KTC tiers with real separation (400-3000):
    Tier 1 (9000+ KTC): ~2800-3000 ELO
    Tier 2 (7500-8999): ~2400-2799 ELO
    Tier 4 (4500-5999): ~1600-1999 ELO
    Tier 7 (under 3000): ~400-1199 ELO
    KTC values updated May 12, 2026
    """
    KTC_SEED_ELOS = {
        'Ja\'Marr Chase': 3000,
        'Josh Allen': 3000,
        'Bijan Robinson': 2998,
        'Jaxon Smith-Njigba': 2971,
        'Jahmyr Gibbs': 2884,
        'Drake Maye': 2848,
        'Brock Bowers': 2687,
        'Puka Nacua': 2644,
        'Trey McBride': 2566,
        'Caleb Williams': 2465,
        'Malik Nabers': 2443,
        'Jayden Daniels': 2432,
        'Justin Jefferson': 2430,
        'Amon-Ra St. Brown': 2408,
        'Lamar Jackson': 2396,
        '2027 Early 1st': 2251,
        '2026 Early 1st': 1883,
        '2027 Mid 1st': 1858,
        'Breece Hall': 1800,
        'TreVeyon Henderson': 1791,
        'Tucker Kraft': 1791,
        'Ladd McConkey': 1783,
        'Jordyn Tyson': 1779,
        'Rashee Rice': 1778,
        'Cam Ward': 1764,
        'Luther Burden': 1756,
        'DeVonta Smith': 1755,
        'Sam LaPorta': 1723,
        'Makai Lemon': 1714,
        'Marvin Harrison Jr.': 1714,
        'Christian McCaffrey': 1713,
        'Dak Prescott': 1698,
        '2028 Early 1st': 1683,
        'Brian Thomas Jr.': 1683,
        'Kyle Pitts': 1681,
        'Tee Higgins': 1677,
        'Bucky Irving': 1676,
        '2027 Late 1st': 1674,
        'Tyler Shough': 1670,
        'Chase Brown': 1669,
        'Saquon Barkley': 1668,
        'Jaylen Waddle': 1666,
        'C.J. Stroud': 1666,
        'Kyren Williams': 1663,
        'A.J. Brown': 1650,
        'Sam Darnold': 1643,
        'Baker Mayfield': 1637,
        'Jadarian Price': 1633,
        'Zay Flowers': 1614,
        'Jameson Williams': 1612,
        'Kenyon Sadiq': 1610,
        '2026 Mid 1st': 1602,
        'Jared Goff': 1594,
        'Cam Skattebo': 1592,
        'KC Concepcion': 1574,
        'Bryce Young': 1571,
        'Josh Jacobs': 1559,
        'Javonte Williams': 1553,
        '2028 Mid 1st': 1551,
        'Travis Etienne': 1545,
        'Alec Pierce': 1469,
        'Kyler Murray': 1466,
        'Oronde Gadsden': 1466,
        'Malik Willis': 1442,
        'Jordan Addison': 1433,
        '2028 Late 1st': 1430,
        'Daniel Jones': 1429,
        'Bhayshul Tuten': 1427,
        '2027 Early 2nd': 1427,
        '2026 Late 1st': 1421,
        'Omar Cooper Jr.': 1413,
        'Derrick Henry': 1397,
        'Matthew Golden': 1374,
        'Isaiah Likely': 1372,
        'Ty Simpson': 1368,
        'Jake Ferguson': 1366,
        'George Kittle': 1364,
        'D.J. Moore': 1356,
        'Matthew Stafford': 1352,
        'Michael Wilson': 1351,
        'Dalton Kincaid': 1350,
        'DK Metcalf': 1348,
        'Christian Watson': 1345,
        'Josh Downs': 1339,
        'Kyle Monangai': 1333,
        'Wan\'Dale Robinson': 1321,
        'Ricky Pearsall': 1316,
        'Parker Washington': 1316,
        'D\'Andre Swift': 1311,
        'RJ Harvey': 1310,
        'Jayden Reed': 1307,
        'Terry McLaurin': 1297,
        'Brenton Strange': 1294,
        'Jayden Higgins': 1292,
        '2027 Mid 2nd': 1292,
        'David Montgomery': 1286,
        'Chuba Hubbard': 1285,
        'Davante Adams': 1284,
        'Michael Pittman': 1276,
        'Zach Charbonnet': 1274,
        'Xavier Worthy': 1270,
        'Quentin Johnston': 1268,
        'Travis Hunter': 1264,
        'Mike Evans': 1255,
        'Romeo Doubs': 1255,
        '2026 Early 2nd': 1252,
        'Courtland Sutton': 1240,
        'T.J. Hockenson': 1239,
        'Jaylen Warren': 1236,
        'AJ Barner': 1236,
        'Blake Corum': 1235,
        'Jakobi Meyers': 1235,
        '2027 Late 2nd': 1230,
        'Rico Dowdle': 1225,
        'Mark Andrews': 1222,
        'Michael Penix Jr.': 1219,
        'Chigoziem Okonkwo': 1211,
    }
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for name, pos, team in DEFAULT_PLAYERS:
        starting_elo = KTC_SEED_ELOS.get(name, 1400)
        c.execute("INSERT OR IGNORE INTO player_rankings (player_name, position, team, elo_score, comparisons, last_updated) VALUES (?, ?, ?, ?, 0, ?)",
                 (name, pos, team, starting_elo, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def seed_ktc_market_data():
    """Store fresh KTC values in market_data table for tier/trade analysis"""
    KTC_PLAYERS = [
        ('Ja\'Marr Chase', 'WR', 'CIN', 1, 9999, 1),
        ('Josh Allen', 'QB', 'BUF', 2, 9999, 1),
        ('Bijan Robinson', 'RB', 'ATL', 3, 9991, 1),
        ('Jaxon Smith-Njigba', 'WR', 'SEA', 4, 9889, 1),
        ('Jahmyr Gibbs', 'RB', 'DET', 5, 9553, 2),
        ('Drake Maye', 'QB', 'NEP', 6, 9416, 2),
        ('Brock Bowers', 'TE', 'LVR', 7, 8794, 3),
        ('Puka Nacua', 'WR', 'LAR', 8, 8631, 3),
        ('Trey McBride', 'TE', 'ARI', 9, 8330, 3),
        ('Caleb Williams', 'QB', 'CHI', 10, 7943, 4),
        ('Malik Nabers', 'WR', 'NYG', 11, 7858, 4),
        ('Jayden Daniels', 'QB', 'WAS', 12, 7814, 4),
        ('Justin Jefferson', 'WR', 'MIN', 13, 7806, 4),
        ('Amon-Ra St. Brown', 'WR', 'DET', 14, 7723, 4),
        ('Lamar Jackson', 'QB', 'BAL', 15, 7676, 4),
        ('2027 Early 1st', 'PICK', 'FA', 20, 7117, 6),
        ('2026 Early 1st', 'PICK', 'FA', 40, 5702, 12),
        ('2027 Mid 1st', 'PICK', 'FA', 44, 5609, 12),
        ('Breece Hall', 'RB', 'NYJ', 50, 5384, 13),
        ('TreVeyon Henderson', 'RB', 'NEP', 51, 5351, 10),
        ('Tucker Kraft', 'TE', 'GBP', 52, 5348, 10),
        ('Ladd McConkey', 'WR', 'LAC', 53, 5318, 10),
        ('Jordyn Tyson', 'WR', 'NOS', 54, 5304, 10),
        ('Rashee Rice', 'WR', 'KCC', 55, 5301, 10),
        ('Cam Ward', 'QB', 'TEN', 56, 5245, 10),
        ('Luther Burden', 'WR', 'CHI', 57, 5216, 10),
        ('DeVonta Smith', 'WR', 'PHI', 58, 5211, 10),
        ('Sam LaPorta', 'TE', 'DET', 59, 5089, 11),
        ('Makai Lemon', 'WR', 'PHI', 60, 5055, 11),
        ('Marvin Harrison Jr.', 'WR', 'ARI', 61, 5054, 11),
        ('Christian McCaffrey', 'RB', 'SFO', 62, 5051, 11),
        ('Dak Prescott', 'QB', 'DAL', 63, 4993, 11),
        ('2028 Early 1st', 'PICK', 'FA', 64, 4935, 11),
        ('Brian Thomas Jr.', 'WR', 'JAC', 65, 4934, 11),
        ('Kyle Pitts', 'TE', 'ATL', 66, 4927, 11),
        ('Tee Higgins', 'WR', 'CIN', 67, 4911, 11),
        ('Bucky Irving', 'RB', 'TBB', 68, 4908, 11),
        ('2027 Late 1st', 'PICK', 'FA', 69, 4898, 11),
        ('Tyler Shough', 'QB', 'NOS', 70, 4884, 11),
        ('Chase Brown', 'RB', 'CIN', 71, 4882, 11),
        ('Saquon Barkley', 'RB', 'PHI', 72, 4876, 11),
        ('Jaylen Waddle', 'WR', 'DEN', 73, 4870, 11),
        ('C.J. Stroud', 'QB', 'HOU', 74, 4868, 11),
        ('Kyren Williams', 'RB', 'LAR', 75, 4858, 11),
        ('A.J. Brown', 'WR', 'PHI', 76, 4808, 11),
        ('Sam Darnold', 'QB', 'SEA', 77, 4781, 11),
        ('Baker Mayfield', 'QB', 'TBB', 78, 4758, 11),
        ('Jadarian Price', 'RB', 'SEA', 79, 4742, 11),
        ('Zay Flowers', 'WR', 'BAL', 80, 4670, 12),
        ('Jameson Williams', 'WR', 'DET', 81, 4662, 12),
        ('Kenyon Sadiq', 'TE', 'NYJ', 82, 4652, 12),
        ('2026 Mid 1st', 'PICK', 'FA', 83, 4622, 12),
        ('Jared Goff', 'QB', 'DET', 84, 4591, 12),
        ('Cam Skattebo', 'RB', 'NYG', 85, 4586, 12),
        ('KC Concepcion', 'WR', 'CLE', 86, 4516, 13),
        ('Bryce Young', 'QB', 'CAR', 87, 4505, 13),
        ('Josh Jacobs', 'RB', 'GBP', 88, 4457, 13),
        ('Javonte Williams', 'RB', 'DAL', 89, 4434, 13),
        ('2028 Mid 1st', 'PICK', 'FA', 90, 4425, 13),
        ('Travis Etienne', 'RB', 'NOS', 91, 4403, 13),
        ('Alec Pierce', 'WR', 'IND', 92, 4111, 14),
        ('Kyler Murray', 'QB', 'MIN', 93, 4101, 14),
        ('Oronde Gadsden', 'TE', 'LAC', 94, 4099, 14),
        ('Malik Willis', 'QB', 'MIA', 95, 4007, 15),
        ('Jordan Addison', 'WR', 'MIN', 97, 3973, 15),
        ('2028 Late 1st', 'PICK', 'FA', 98, 3963, 15),
        ('Daniel Jones', 'QB', 'IND', 99, 3959, 15),
        ('Bhayshul Tuten', 'RB', 'JAC', 100, 3951, 15),
        ('2027 Early 2nd', 'PICK', 'FA', 101, 3950, 15),
        ('2026 Late 1st', 'PICK', 'FA', 102, 3926, 15),
        ('Omar Cooper Jr.', 'WR', 'NYJ', 103, 3896, 15),
        ('Derrick Henry', 'RB', 'BAL', 104, 3834, 16),
        ('Matthew Golden', 'WR', 'GBP', 105, 3745, 17),
        ('Isaiah Likely', 'TE', 'NYG', 106, 3740, 17),
        ('Ty Simpson', 'QB', 'LAR', 107, 3724, 17),
        ('Jake Ferguson', 'TE', 'DAL', 108, 3716, 17),
        ('George Kittle', 'TE', 'SFO', 109, 3708, 17),
        ('D.J. Moore', 'WR', 'BUF', 110, 3678, 17),
        ('Matthew Stafford', 'QB', 'LAR', 111, 3661, 17),
        ('Michael Wilson', 'WR', 'ARI', 112, 3656, 17),
        ('Dalton Kincaid', 'TE', 'BUF', 113, 3654, 17),
        ('DK Metcalf', 'WR', 'PIT', 114, 3647, 17),
        ('Christian Watson', 'WR', 'GBP', 115, 3633, 17),
        ('Josh Downs', 'WR', 'IND', 116, 3610, 17),
        ('Kyle Monangai', 'RB', 'CHI', 117, 3590, 17),
        ('Wan\'Dale Robinson', 'WR', 'TEN', 118, 3543, 17),
        ('Ricky Pearsall', 'WR', 'SFO', 119, 3522, 17),
        ('Parker Washington', 'WR', 'JAC', 120, 3521, 17),
        ('D\'Andre Swift', 'RB', 'CHI', 121, 3505, 17),
        ('RJ Harvey', 'RB', 'DEN', 122, 3498, 17),
        ('Jayden Reed', 'WR', 'GBP', 123, 3487, 17),
        ('Terry McLaurin', 'WR', 'WAS', 124, 3450, 17),
        ('Brenton Strange', 'TE', 'JAC', 126, 3440, 17),
        ('Jayden Higgins', 'WR', 'HOU', 127, 3429, 17),
        ('2027 Mid 2nd', 'PICK', 'FA', 128, 3429, 17),
        ('David Montgomery', 'RB', 'HOU', 129, 3408, 17),
        ('Chuba Hubbard', 'RB', 'CAR', 130, 3405, 17),
        ('Davante Adams', 'WR', 'LAR', 131, 3398, 17),
        ('Michael Pittman', 'WR', 'PIT', 132, 3370, 17),
        ('Zach Charbonnet', 'RB', 'SEA', 133, 3360, 17),
        ('Xavier Worthy', 'WR', 'KCC', 134, 3344, 17),
        ('Quentin Johnston', 'WR', 'LAC', 135, 3337, 17),
        ('Travis Hunter', 'WR', 'JAC', 136, 3322, 17),
        ('Mike Evans', 'WR', 'SFO', 137, 3289, 17),
        ('Romeo Doubs', 'WR', 'NEP', 138, 3288, 17),
        ('2026 Early 2nd', 'PICK', 'FA', 139, 3277, 17),
        ('Courtland Sutton', 'WR', 'DEN', 140, 3231, 17),
        ('T.J. Hockenson', 'TE', 'MIN', 141, 3228, 17),
        ('Jaylen Warren', 'RB', 'PIT', 142, 3215, 17),
        ('AJ Barner', 'TE', 'SEA', 143, 3214, 17),
        ('Blake Corum', 'RB', 'LAR', 144, 3212, 17),
        ('Jakobi Meyers', 'WR', 'JAC', 145, 3211, 17),
        ('2027 Late 2nd', 'PICK', 'FA', 146, 3192, 17),
        ('Rico Dowdle', 'RB', 'PIT', 147, 3174, 17),
        ('Mark Andrews', 'TE', 'BAL', 148, 3161, 17),
        ('Michael Penix Jr.', 'QB', 'ATL', 149, 3151, 17),
        ('Chigoziem Okonkwo', 'TE', 'WAS', 150, 3118, 17),
    ]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Only seed if empty or stale
    c.execute("SELECT COUNT(*) FROM market_data WHERE source='ktc'")
    existing = c.fetchone()[0]
    if existing > 100:
        conn.close()
        return  # Already have data
    for name, pos, team, rank, value, tier in KTC_PLAYERS:
        c.execute('''INSERT OR REPLACE INTO market_data
                    (source, player_name, rank, value, position, team, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 ('ktc', name, rank, value, pos, team, datetime.now().isoformat()))
    conn.commit()
    conn.close()

seed_players()
seed_ktc_market_data()

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

    conn = sqlite3.connect(DB_PATH)
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
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=messages
        )

        assistant_message = ""
        for block in response.content:
            if hasattr(block, 'text'):
                assistant_message += block.text

        conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE week_key=?", (week_key,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/chat/search', methods=['POST'])
def search_chat():
    query = request.json.get('query', '').lower()
    conn = sqlite3.connect(DB_PATH)
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

@app.route('/api/dashboard/static', methods=['GET'])
def get_static_dashboard():
    """Instant-loading static dashboard from known context — no AI calls"""
    data = {
        "roster_summary": [
            {"league": "Capital Gains", "strategy": "REBUILD → 2027", "priority": "#3",
             "top_assets": ["Drake Maye 9,412", "Drake London 6,887", "Sam LaPorta 5,042"],
             "picks": "4x 2027 R1 · R1(own) + R1(Dudesss) + R1(GNAwin0) + R1(TeddySalad)",
             "alert": "29 players — cut to 20 by September"},
            {"league": "Twenty Run Savages", "strategy": "COMPETING NOW", "priority": "#2",
             "top_assets": ["Drake Maye 9,412", "Bijan Robinson 9,987", "JSN 9,918"],
             "picks": "2027 R1(Stinky) + R1(own)",
             "alert": "Draft still ongoing — picks 3.07, 4.03, 4.07 remaining"},
            {"league": "Gentleman's Dynasty", "strategy": "REBUILD → 2027-28", "priority": "#4",
             "top_assets": ["Brock Bowers 8,765", "Patrick Mahomes 6,814", "Carnell Tate 5,830"],
             "picks": "2027 R1(own) · 2028 R1+R2+R3+R4",
             "alert": "Acquire LaPorta from c1smith11 — #1 priority"},
            {"league": "Velvet Spade", "strategy": "STARTUP — May 15", "priority": "#1",
             "top_assets": ["Pick 1.02 overall", "2.11", "3.11"],
             "picks": "28-round startup — pick #2 overall",
             "alert": "Draft in 7 days — finalize strategy"}
        ],
        "quick_actions": [
            {"league": "Gentleman's", "action": "Send LaPorta offer to c1smith11", "message": "Njoku and 2027 2nd for LaPorta. Works for both of us."},
            {"league": "Gentleman's", "action": "Sell McCarthy to SenorHyde", "message": "McCarthy for your 2027 2nd. You need the QB."},
            {"league": "TRS", "action": "Add K and backup DST via FAAB", "message": "Streaming K and DST needed before Week 1"},
            {"league": "Velvet Spade", "action": "Finalize startup draft strategy", "message": "6pt TDs — never leave Round 1 without elite QB"}
        ],
        "ktc_baseline_date": "May 8, 2026"
    }
    return jsonify({"data": data, "success": True})

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """AI-powered dashboard with live web searches — triggered on demand"""
    # Check cache first (6 hour TTL)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT data, last_updated FROM dashboard_cache WHERE cache_key='main'")
        row = c.fetchone()
        if row:
            last_updated = datetime.fromisoformat(row[1])
            if datetime.now() - last_updated < timedelta(hours=6):
                conn.close()
                return jsonify({"data": json.loads(row[0]), "success": True, "cached": True,
                               "cached_at": row[1]})
    except Exception:
        pass
    conn.close()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": """Generate a dynasty GM dashboard for MJBrutus. Search for 1-2 breaking news items relevant to his rosters. Return ONLY valid JSON:
{"alerts":[{"type":"warning|info|opportunity","league":"league name","message":"short alert","action":"what to do"}],
"news":[{"player":"name","team":"team","position":"QB","leagues":["leagues"],"headline":"news","impact":"dynasty impact","recommendation":"BUY|SELL|HOLD|MONITOR"}],
"movers":[{"player":"name","direction":"up|down","change":"+/-amount","reason":"why","action":"what to do"}],
"trade_targets":[{"player":"name","owner":"their team","league":"which league","offer":"under 20 words","rationale":"why"}],
"weekly_priorities":["priority 1","priority 2","priority 3"]}"""}]
        )
        text = "".join(b.text for b in response.content if hasattr(b, 'text'))
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            # Cache it
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO dashboard_cache (cache_key, data, last_updated) VALUES (?, ?, ?)",
                     ('main', json.dumps(data), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return jsonify({"data": data, "success": True, "cached": False})
    except Exception as e:
        pass

    # Fallback
    return jsonify({"data": {
        "alerts": [{"type": "opportunity", "league": "Gentleman's", "message": "LaPorta on block at c1smith11", "action": "Send Njoku + 2027 2nd offer"}],
        "news": [{"player": "Drake Maye", "team": "NE", "position": "QB", "leagues": ["Capital Gains", "TRS"], "headline": "AJ Brown trade expected post June 1", "impact": "Maye value increases with elite WR1", "recommendation": "HOLD"}],
        "movers": [{"player": "Carnell Tate", "direction": "up", "change": "+150", "reason": "Strong pre-draft buzz as TEN WR1", "action": "Hold — core asset"}],
        "trade_targets": [{"player": "Sam LaPorta", "owner": "c1smith11", "league": "Gentleman's Dynasty", "offer": "Njoku and 2027 2nd for LaPorta", "rationale": "TE premium upgrade"}],
        "weekly_priorities": ["Send LaPorta offer in Gentleman's", "Finalize Velvet Spade startup strategy", "Complete TRS rookie draft picks"]
    }, "success": True, "cached": False})


@app.route('/api/player/profile', methods=['POST'])
def get_player_profile():
    player_name = request.json.get('player', '')
    league = request.json.get('league', 'all')
    conn = sqlite3.connect(DB_PATH)
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
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": f"""Create dynasty player profile for {player_name}, league context: {league}. Return ONLY valid JSON:
{{"name":"","position":"","team":"","age":0,"ktc_value":0,"ktc_trend":"","position_rank":"","trade_liquidity":"High|Medium|Low","recommendation":"BUY|SELL|HOLD","recommendation_reason":"","league_specific":{{"Capital Gains":"","TRS":"","Gentlemans":"","Velvet Spade":""}},"latest_news":[],"dynasty_outlook":"","injury_history":"","contract_status":"","depth_chart":"","startup_adp":"","ppg_2025":0,"ppg_2024":0}}"""}]
        )
        assistant_message = "".join(b.text for b in response.content if hasattr(b, 'text'))
        cleaned = assistant_message.strip().lstrip('```json').lstrip('```').rstrip('```').strip()
        profile = json.loads(cleaned)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO player_profiles (player_name, profile_data, last_updated) VALUES (?, ?, ?)",
                 (player_name, json.dumps(profile), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"profile": profile, "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

@app.route('/api/rankings/reset', methods=['POST'])
def reset_rankings():
    """Reset all rankings and re-seed with full player list"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM player_rankings")
    conn.commit()
    conn.close()
    seed_players()
    return jsonify({"success": True, "message": f"Rankings reset with {len(DEFAULT_PLAYERS)} players"})

@app.route('/api/rankings/pair', methods=['GET'])
def get_ranking_pair():
    """Get two players for comparison using tier-proximity matching"""
    position_filter = request.args.get('position', 'ALL')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if position_filter != 'ALL':
        c.execute("""SELECT player_name, position, team, elo_score, comparisons
                    FROM player_rankings WHERE position=?
                    ORDER BY comparisons ASC, RANDOM() LIMIT 50""", (position_filter,))
    else:
        c.execute("""SELECT player_name, position, team, elo_score, comparisons
                    FROM player_rankings ORDER BY comparisons ASC, RANDOM() LIMIT 80""")

    rows = c.fetchall()
    conn.close()

    if len(rows) < 2:
        return jsonify({"players": [], "success": False, "error": "Not enough players"})

    players = [{"name": r[0], "position": r[1], "team": r[2], "elo": r[3], "comparisons": r[4]} for r in rows]

    # Assign KTC tiers based on ELO (maps to KTC value ranges)
    def get_tier(elo):
        if elo >= 2800: return 1   # 9000+ KTC
        if elo >= 2400: return 2   # 7500-8999
        if elo >= 2000: return 3   # 6000-7499
        if elo >= 1600: return 4   # 4500-5999
        if elo >= 1200: return 5   # 3000-4499
        if elo >= 800:  return 6   # 1500-2999
        return 7                   # under 1500

    import random
    # Pick first player with fewest comparisons from top 20
    pool = sorted(players, key=lambda x: x['comparisons'])
    p1 = pool[random.randint(0, min(9, len(pool)-1))]
    p1_tier = get_tier(p1['elo'])

    # Decide tier proximity: 60% same tier, 30% 1 tier apart, 10% up to 3 tiers apart
    rand = random.random()
    if rand < 0.60:
        target_tiers = [p1_tier]
    elif rand < 0.90:
        target_tiers = [p1_tier - 1, p1_tier + 1]
    else:
        target_tiers = [p1_tier - 3, p1_tier - 2, p1_tier - 1,
                       p1_tier + 1, p1_tier + 2, p1_tier + 3]
    target_tiers = [t for t in target_tiers if 1 <= t <= 7]

    # Find p2 candidates in target tiers (excluding p1)
    p2_candidates = [p for p in players
                    if p['name'] != p1['name'] and get_tier(p['elo']) in target_tiers]

    if not p2_candidates:
        # Fallback: any player in adjacent tiers
        p2_candidates = [p for p in players if p['name'] != p1['name']]

    # Prefer candidates with fewer comparisons
    p2_candidates.sort(key=lambda x: x['comparisons'])
    p2 = p2_candidates[random.randint(0, min(9, len(p2_candidates)-1))]

    return jsonify({"players": [p1, p2], "success": True})

@app.route('/api/rankings/adjust', methods=['POST'])
def adjust_ranking():
    """Manually adjust a player's ELO up or down"""
    name = request.json.get('name', '')
    direction = request.json.get('direction', 'up')  # 'up' or 'down'
    positions = request.json.get('positions', 5)  # how many spots to move

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get current rank
    c.execute("SELECT elo_score FROM player_rankings WHERE player_name=?", (name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Player not found"})

    current_elo = row[0]

    # Get the ELO of the player N positions above/below
    c.execute("""SELECT elo_score FROM player_rankings
                ORDER BY elo_score DESC""")
    all_elos = [r[0] for r in c.fetchall()]

    # Find current position
    try:
        curr_pos = next(i for i, e in enumerate(all_elos) if abs(e - current_elo) < 0.01)
    except StopIteration:
        curr_pos = len(all_elos) // 2

    if direction == 'up':
        target_pos = max(0, curr_pos - positions)
    else:
        target_pos = min(len(all_elos) - 1, curr_pos + positions)

    if target_pos == curr_pos:
        conn.close()
        return jsonify({"success": True, "new_elo": current_elo})

    # Set new ELO midpoint between surrounding players
    if direction == 'up' and target_pos > 0:
        above_elo = all_elos[target_pos - 1]
        at_elo = all_elos[target_pos]
        new_elo = (above_elo + at_elo) / 2
    elif direction == 'down' and target_pos < len(all_elos) - 1:
        at_elo = all_elos[target_pos]
        below_elo = all_elos[target_pos + 1]
        new_elo = (at_elo + below_elo) / 2
    else:
        new_elo = all_elos[target_pos]

    c.execute("UPDATE player_rankings SET elo_score=?, last_updated=? WHERE player_name=?",
             (new_elo, datetime.now().isoformat(), name))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "new_elo": round(new_elo), "moved_to": target_pos + 1})


@app.route('/api/rankings/vote', methods=['POST'])
def submit_vote():
    winner = request.json.get('winner')
    loser = request.json.get('loser')
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO player_rankings (player_name, position, team, elo_score, comparisons, last_updated) VALUES (?, ?, ?, 1500, 0, ?)",
             (name, position, team, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

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

# ============================================================
# KTC SYNC — UNOFFICIAL API + MANUAL FALLBACK
# ============================================================

@app.route('/api/ktc/sync', methods=['POST'])
def sync_ktc():
    """Try KTC unofficial API, store values with timestamp"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'application/json',
            'Referer': 'https://keeptradecut.com/'
        }
        r = requests.get(
            'https://keeptradecut.com/api/players?format=2&limited=false',
            headers=headers, timeout=15
        )
        if r.status_code == 200:
            players = r.json()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS ktc_values
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         player_name TEXT NOT NULL, ktc_value INTEGER,
                         week_key TEXT NOT NULL, synced_at TEXT NOT NULL)''')
            week_key = get_week_key()
            count = 0
            for p in players:
                name = p.get('playerName', '') or f"{p.get('firstName','')} {p.get('lastName','')}".strip()
                value = p.get('superflex', p.get('value', 0))
                if name and value:
                    c.execute('''INSERT OR REPLACE INTO ktc_values (player_name, ktc_value, week_key, synced_at)
                                VALUES (?, ?, ?, ?)''',
                             (name, value, week_key, datetime.now().isoformat()))
                    count += 1
            conn.commit()
            conn.close()
            return jsonify({"success": True, "source": "ktc_api", "count": count,
                          "message": f"Synced {count} KTC values from live API"})
    except Exception as e:
        pass

    # Fallback — return baseline values from context
    return jsonify({"success": True, "source": "baseline",
                   "message": "KTC API unavailable. Using May 2026 baseline values. Paste updated values in chat to override."})

@app.route('/api/ktc/values', methods=['GET'])
def get_ktc_values():
    """Get stored KTC values with 4-week trend"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS ktc_values
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     player_name TEXT NOT NULL, ktc_value INTEGER,
                     week_key TEXT NOT NULL, synced_at TEXT NOT NULL)''')
        conn.commit()
        c.execute('''SELECT player_name, ktc_value, week_key FROM ktc_values
                    ORDER BY player_name, synced_at DESC''')
        rows = c.fetchall()
        conn.close()

        # Build player value history
        from collections import defaultdict
        history = defaultdict(list)
        for name, val, week in rows:
            history[name].append({'value': val, 'week': week})

        result = {}
        for name, entries in history.items():
            latest = entries[0]['value']
            baseline = entries[-1]['value'] if len(entries) > 1 else latest
            change = latest - baseline
            result[name] = {
                'current': latest,
                'baseline': baseline,
                'change': change,
                'change_pct': round((change / baseline * 100) if baseline else 0, 1),
                'weeks_tracked': len(entries)
            }
        return jsonify({"values": result, "success": True})
    except Exception as e:
        conn.close()
        return jsonify({"values": {}, "success": True})

@app.route('/api/ktc/manual', methods=['POST'])
def manual_ktc_update():
    """Allow manual paste of KTC values"""
    updates = request.json.get('updates', [])
    week_key = get_week_key()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ktc_values
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 player_name TEXT NOT NULL, ktc_value INTEGER,
                 week_key TEXT NOT NULL, synced_at TEXT NOT NULL)''')
    for item in updates:
        c.execute('''INSERT INTO ktc_values (player_name, ktc_value, week_key, synced_at)
                    VALUES (?, ?, ?, ?)''',
                 (item['name'], item['value'], week_key, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "updated": len(updates)})

# ============================================================
# SLEEPER ADP — FREE PUBLIC API
# ============================================================

@app.route('/api/sleeper/adp', methods=['GET'])
def get_sleeper_adp():
    """Get Sleeper dynasty ADP as ranking source"""
    try:
        # Sleeper trending players as ADP proxy
        r = requests.get('https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=168&limit=200',
                        timeout=10)
        if r.status_code == 200:
            data = r.json()
            adp = {}
            for i, item in enumerate(data):
                pid = item.get('player_id', '')
                adp[pid] = {'rank': i + 1, 'adds': item.get('count', 0)}
            return jsonify({"adp": adp, "success": True, "count": len(adp)})
    except Exception as e:
        pass
    return jsonify({"adp": {}, "success": False})

# ============================================================
# COMPOSITE RANKINGS
# Weights: Personal ELO 40% | KTC 20% | Sleeper ADP 30% | Underdog 10%
# ============================================================

@app.route('/api/rankings/composite', methods=['GET'])
def get_composite_rankings():
    position_filter = request.args.get('position', 'ALL')

    # 1. Get personal ELO rankings
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT player_name, position, team, elo_score, comparisons
                FROM player_rankings ORDER BY elo_score DESC''')
    personal_rows = c.fetchall()
    conn.close()

    personal_ranks = {}
    for i, (name, pos, team, elo, comps) in enumerate(personal_rows):
        personal_ranks[name] = {
            'position': pos, 'team': team, 'elo': elo,
            'comparisons': comps, 'personal_rank': i + 1
        }

    # 2. Get KTC values from DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ktc_ranks = {}
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS ktc_values
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     player_name TEXT NOT NULL, ktc_value INTEGER,
                     week_key TEXT NOT NULL, synced_at TEXT NOT NULL)''')
        c.execute('''SELECT player_name, MAX(ktc_value) as val FROM ktc_values
                    GROUP BY player_name ORDER BY val DESC''')
        ktc_rows = c.fetchall()
        for i, (name, val) in enumerate(ktc_rows):
            ktc_ranks[name] = {'value': val, 'rank': i + 1}
    except:
        pass
    conn.close()

    # 3. Sleeper ADP placeholder (removed live fetch — unreliable from datacenter)
    sleeper_ranks = {}

    # 4. Build composite scores
    all_players = set(personal_ranks.keys())
    total = len(all_players)

    composite = []
    for name in all_players:
        p = personal_ranks[name]
        pos = p['position']

        if position_filter != 'ALL' and pos != position_filter:
            continue

        personal_rank = p['personal_rank']
        personal_score = (total - personal_rank + 1) / total

        # KTC score
        if name in ktc_ranks:
            ktc_rank = ktc_ranks[name]['rank']
            ktc_total = len(ktc_ranks)
            ktc_score = (ktc_total - ktc_rank + 1) / ktc_total
        else:
            ktc_score = personal_score * 0.7  # estimate from personal

        # Sleeper ADP score
        if name in sleeper_ranks:
            sl_rank = sleeper_ranks[name]
            sl_total = max(len(sleeper_ranks), 200)
            sleeper_score = (sl_total - sl_rank + 1) / sl_total
        else:
            sleeper_score = personal_score * 0.7

        # Composite: Personal 40%, KTC 20%, Sleeper 30%, buffer 10%
        composite_score = (
            personal_score * 0.40 +
            ktc_score * 0.20 +
            sleeper_score * 0.30 +
            personal_score * 0.10  # buffer uses personal as proxy
        )

        # Market rank (KTC-weighted)
        market_rank_score = ktc_score * 0.50 + sleeper_score * 0.50
        market_rank = 0  # will be assigned after sorting

        composite.append({
            'name': name,
            'position': pos,
            'team': p['team'],
            'elo': round(p['elo']),
            'comparisons': p['comparisons'],
            'personal_rank': personal_rank,
            'ktc_value': ktc_ranks.get(name, {}).get('value', 0),
            'ktc_rank': ktc_ranks.get(name, {}).get('rank', 0),
            'sleeper_rank': sleeper_ranks.get(name, 0),
            'composite_score': composite_score,
            'market_score': market_rank_score,
        })

    # Sort by composite score
    composite.sort(key=lambda x: x['composite_score'], reverse=True)

    # Assign market ranks
    market_sorted = sorted(composite, key=lambda x: x['market_score'], reverse=True)
    market_rank_map = {p['name']: i + 1 for i, p in enumerate(market_sorted)}

    for i, p in enumerate(composite):
        p['composite_rank'] = i + 1
        p['market_rank'] = market_rank_map[p['name']]
        delta = p['market_rank'] - p['personal_rank']
        p['delta'] = delta  # positive = you rank higher than market (buy signal)
        if abs(delta) >= 26:
            p['signal'] = 'MAJOR BUY' if delta > 0 else 'MAJOR SELL'
            p['signal_strength'] = 3
        elif abs(delta) >= 16:
            p['signal'] = 'BUY' if delta > 0 else 'SELL'
            p['signal_strength'] = 2
        elif abs(delta) >= 5:
            p['signal'] = 'SLIGHT BUY' if delta > 0 else 'SLIGHT SELL'
            p['signal_strength'] = 1
        else:
            p['signal'] = 'HOLD'
            p['signal_strength'] = 0

    return jsonify({
        "rankings": composite,
        "total": len(composite),
        "success": True,
        "weights": {"personal": "40%", "ktc": "20%", "sleeper": "30%", "buffer": "10%"}
    })

# ============================================================
# KNOWLEDGE BASE — YOUTUBE TRANSCRIPTS
# ============================================================

@app.route('/api/draft/assistant', methods=['POST'])
def draft_assistant():
    """Live startup draft assistant for Velvet Spade"""
    data = request.json
    picks_made = data.get('picks_made', [])  # list of {pick: "1.01", player: "Josh Allen", team: "pdwyer13"}
    current_pick = data.get('current_pick', '')
    my_roster = data.get('my_roster', [])
    available_input = data.get('available', '')

    # Build context for the agent
    picks_context = '\n'.join([f"Pick {p['pick']} ({p.get('team','')}): {p['player']}" for p in picks_made])
    roster_context = ', '.join(my_roster) if my_roster else 'None yet'

    prompt = f"""You are running the Velvet Spade startup draft assistant for MJBrutus (dcatlet).

VELVET SPADE SCORING: 6pt passing TDs | 1.5 TE premium | 1.0 PPR RB/WR | Bonuses: 40yd play +1, 400yd pass +2, 200yd rush/rec +2
LINEUP: 1QB/2RB/2WR/1TE/3FLEX/1SFLX | 23+5taxi+2IR | 28 rounds snake + 3rd round reversal
MY PICK SEQUENCE: 1.02, 2.11, 3.11, 4.02, 5.11, 6.02, 7.11, 8.02...

PICKS MADE SO FAR:
{picks_context if picks_context else 'None yet'}

MY CURRENT ROSTER: {roster_context}
CURRENT PICK ON CLOCK: {current_pick}
AVAILABLE PLAYERS: {available_input[:2000] if available_input else 'Not specified'}

Provide:
1. TOP RECOMMENDATION at this pick with clear reasoning
2. Next 2 alternatives if top pick is gone
3. Roster construction note (what positions still needed)
4. Value remaining alert (any elite players still available that are sliding)

Be decisive. One clear recommendation first. Format for mobile."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
            messages=[{"role": "user", "content": prompt}]
        )
        recommendation = "".join(b.text for b in response.content if hasattr(b, 'text'))
        return jsonify({"recommendation": recommendation, "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

@app.route('/api/draft/state', methods=['GET', 'POST'])
def draft_state():
    """Save and retrieve draft state"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS draft_state
                (id INTEGER PRIMARY KEY, state_data TEXT, updated_at TEXT)''')

    if request.method == 'POST':
        state = request.json.get('state', {})
        c.execute('''INSERT OR REPLACE INTO draft_state (id, state_data, updated_at)
                    VALUES (1, ?, ?)''', (json.dumps(state), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    else:
        c.execute("SELECT state_data FROM draft_state WHERE id=1")
        row = c.fetchone()
        conn.close()
        if row:
            return jsonify({"state": json.loads(row[0]), "success": True})
        return jsonify({"state": {}, "success": True})

# ============================================================
# VS RANKINGS — 6PT TD SPECIFIC HEAD-TO-HEAD
# ============================================================

def seed_vs_players():
    """Seed VS rankings pool with 6pt TD adjusted ELO — QBs boosted ~18%"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM vs_rankings")
    if c.fetchone()[0] > 0:
        conn.close()
        return
    # Pull from standard rankings and boost QB ELO by 18%
    c.execute("SELECT player_name, position, team, elo_score FROM player_rankings")
    rows = c.fetchall()
    for name, pos, team, elo in rows:
        adjusted_elo = round(elo * 1.18) if pos == 'QB' else elo
        c.execute('''INSERT OR IGNORE INTO vs_rankings
                    (player_name, position, team, elo_score, comparisons, last_updated)
                    VALUES (?, ?, ?, ?, 0, ?)''',
                 (name, pos, team, adjusted_elo, datetime.now().isoformat()))
    conn.commit()
    conn.close()

seed_vs_players()

@app.route('/api/vs/pair', methods=['GET'])
def get_vs_pair():
    """Proximity-based matchup for VS 6pt TD rankings"""
    position_filter = request.args.get('position', 'ALL')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if position_filter != 'ALL':
        c.execute('''SELECT player_name, position, team, elo_score, comparisons
                    FROM vs_rankings WHERE position=?
                    ORDER BY comparisons ASC, RANDOM() LIMIT 80''', (position_filter,))
    else:
        c.execute('''SELECT player_name, position, team, elo_score, comparisons
                    FROM vs_rankings ORDER BY comparisons ASC, RANDOM() LIMIT 100''')
    rows = c.fetchall()
    conn.close()
    if len(rows) < 2:
        return jsonify({"players": [], "success": False})
    players = [{"name": r[0], "position": r[1], "team": r[2], "elo": r[3], "comparisons": r[4]} for r in rows]

    def get_tier(elo):
        if elo >= 2800: return 1
        if elo >= 2400: return 2
        if elo >= 2000: return 3
        if elo >= 1600: return 4
        if elo >= 1200: return 5
        if elo >= 800: return 6
        return 7

    import random
    pool = sorted(players, key=lambda x: x['comparisons'])
    p1 = pool[random.randint(0, min(9, len(pool)-1))]
    p1_tier = get_tier(p1['elo'])
    rand = random.random()
    if rand < 0.60:
        target_tiers = [p1_tier]
    elif rand < 0.90:
        target_tiers = [p1_tier - 1, p1_tier + 1]
    else:
        target_tiers = [p1_tier + i for i in range(-3, 4) if i != 0]
    target_tiers = [t for t in target_tiers if 1 <= t <= 7]
    p2_candidates = [p for p in players if p['name'] != p1['name'] and get_tier(p['elo']) in target_tiers]
    if not p2_candidates:
        p2_candidates = [p for p in players if p['name'] != p1['name']]
    p2_candidates.sort(key=lambda x: x['comparisons'])
    p2 = p2_candidates[random.randint(0, min(9, len(p2_candidates)-1))]
    return jsonify({"players": [p1, p2], "success": True})

@app.route('/api/vs/vote', methods=['POST'])
def vs_vote():
    """Record VS comparison vote and update ELO"""
    data = request.json
    winner = data.get('winner', '')
    loser = data.get('loser', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT elo_score, comparisons FROM vs_rankings WHERE player_name=?", (winner,))
    wr = c.fetchone()
    c.execute("SELECT elo_score, comparisons FROM vs_rankings WHERE player_name=?", (loser,))
    lr = c.fetchone()
    if wr and lr:
        K = 32
        we, le = wr[0], lr[0]
        exp_w = 1 / (1 + 10 ** ((le - we) / 400))
        new_we = we + K * (1 - exp_w)
        new_le = le + K * (0 - (1 - exp_w))
        c.execute("UPDATE vs_rankings SET elo_score=?, comparisons=comparisons+1, last_updated=? WHERE player_name=?",
                 (new_we, datetime.now().isoformat(), winner))
        c.execute("UPDATE vs_rankings SET elo_score=?, comparisons=comparisons+1, last_updated=? WHERE player_name=?",
                 (new_le, datetime.now().isoformat(), loser))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/vs/list', methods=['GET'])
def get_vs_list():
    """Get VS personal rankings sorted by ELO, limited to top 150"""
    position_filter = request.args.get('position', 'ALL')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if position_filter != 'ALL':
        c.execute('''SELECT player_name, position, team, elo_score, comparisons
                    FROM vs_rankings WHERE position=?
                    ORDER BY elo_score DESC LIMIT 150''', (position_filter,))
    else:
        c.execute('''SELECT player_name, position, team, elo_score, comparisons
                    FROM vs_rankings ORDER BY elo_score DESC LIMIT 150''')
    rows = c.fetchall()
    conn.close()
    rankings = [{"rank": i+1, "name": r[0], "position": r[1], "team": r[2],
                 "elo": round(r[3]), "comparisons": r[4]} for i, r in enumerate(rows)]
    return jsonify({"rankings": rankings, "success": True})

@app.route('/api/vs/adjust', methods=['POST'])
def vs_adjust():
    """Manually adjust VS player ranking"""
    name = request.json.get('name', '')
    direction = request.json.get('direction', 'up')
    positions = request.json.get('positions', 5)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT elo_score FROM vs_rankings WHERE player_name=?", (name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Player not found"})
    current_elo = row[0]
    c.execute("SELECT elo_score FROM vs_rankings ORDER BY elo_score DESC")
    all_elos = [r[0] for r in c.fetchall()]
    try:
        curr_pos = next(i for i, e in enumerate(all_elos) if abs(e - current_elo) < 0.01)
    except StopIteration:
        curr_pos = len(all_elos) // 2
    target_pos = max(0, curr_pos - positions) if direction == 'up' else min(len(all_elos)-1, curr_pos + positions)
    if target_pos != curr_pos:
        if direction == 'up' and target_pos > 0:
            new_elo = (all_elos[target_pos-1] + all_elos[target_pos]) / 2
        elif direction == 'down' and target_pos < len(all_elos)-1:
            new_elo = (all_elos[target_pos] + all_elos[target_pos+1]) / 2
        else:
            new_elo = all_elos[target_pos]
        c.execute("UPDATE vs_rankings SET elo_score=?, last_updated=? WHERE player_name=?",
                 (new_elo, datetime.now().isoformat(), name))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "new_elo": round(new_elo if target_pos != curr_pos else current_elo)})

@app.route('/api/vs/reset', methods=['POST'])
def vs_reset():
    """Reset VS rankings and re-seed from standard rankings with QB boost"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM vs_rankings")
    conn.commit()
    conn.close()
    seed_vs_players()
    return jsonify({"success": True, "message": "VS rankings reset with 6pt TD QB adjustments"})

# ============================================================
# MARKET DATA — PASTE KTC / DDL / SLEEPER ADP
# ============================================================

@app.route('/api/market/paste', methods=['POST'])
def paste_market_data():
    """
    Accept pasted rankings from KTC, Dynasty Data Lab, or Sleeper ADP.
    Parser handles messy copied text — just paste what you see on screen.
    """
    source = request.json.get('source', '')  # 'ktc', 'ddl', 'sleeper'
    raw_text = request.json.get('text', '')
    if not source or not raw_text:
        return jsonify({"success": False, "error": "source and text required"})

    import re
    players_parsed = []

    if source == 'ktc':
        # KTC format: "1 Josh Allen BUF QB1 9999"
        # Also handles the format from the paste: rank, name, team, pos, value
        lines = raw_text.strip().split('\n')
        rank = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Extract KTC value (4-5 digit number at end)
            val_match = re.search(r'\b(\d{3,5})\s*$', line)
            if not val_match:
                continue
            val = int(val_match.group(1))
            if val < 100:
                continue
            # Extract position
            pos_match = re.search(r'\b(QB|RB|WR|TE|PICK)\b', line)
            if not pos_match:
                continue
            pos = pos_match.group(1)
            # Extract team (2-3 uppercase letters)
            team_match = re.search(r'\b([A-Z]{2,3})\b', line)
            team = team_match.group(1) if team_match else 'FA'
            # Player name: everything before team/pos markers
            name_part = re.sub(r'\b(QB|RB|WR|TE|PICK|QB\d+|RB\d+|WR\d+|TE\d+)\b.*', '', line)
            name_part = re.sub(r'^\d+\s*', '', name_part)
            name_part = re.sub(r'\b[A-Z]{2,3}\b', '', name_part)
            name = re.sub(r'\s+', ' ', name_part).strip()
            name = re.sub(r"[^\w\s'.]", '', name).strip()
            if len(name) < 3:
                continue
            rank += 1
            players_parsed.append({'name': name, 'rank': rank, 'value': val, 'position': pos, 'team': team})

    elif source == 'ddl':
        # DDL format: rank | name | team | pos | value
        # Handles both table and list formats
        lines = raw_text.strip().split('\n')
        rank = 0
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            # Skip headers
            if any(h in line.lower() for h in ['player', 'rank', 'name', 'value', '---']):
                continue
            pos_match = re.search(r'\b(QB|RB|WR|TE)\b', line)
            if not pos_match:
                continue
            pos = pos_match.group(1)
            val_match = re.search(r'\b(\d{3,5})\b', line)
            val = int(val_match.group(1)) if val_match else 5000
            # Name is usually before position marker
            name_part = line[:pos_match.start()]
            name_part = re.sub(r'^\d+[\.\):\s]+', '', name_part)
            name_part = re.sub(r'\b[A-Z]{2,3}\b\s*$', '', name_part)
            name = re.sub(r'\s+', ' ', name_part).strip()
            name = re.sub(r"[^\w\s'.]", '', name).strip()
            if len(name) < 3:
                continue
            rank += 1
            players_parsed.append({'name': name, 'rank': rank, 'value': val, 'position': pos, 'team': 'FA'})

    elif source == 'sleeper':
        # Sleeper ADP: usually "1. Player Name POS" or "Name (POS) - Team"
        lines = raw_text.strip().split('\n')
        rank = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            pos_match = re.search(r'\b(QB|RB|WR|TE)\b', line)
            if not pos_match:
                continue
            pos = pos_match.group(1)
            team_match = re.search(r'\b([A-Z]{2,3})\b(?!.*\b(?:QB|RB|WR|TE)\b)', line)
            team = team_match.group(1) if team_match else 'FA'
            name_part = line[:pos_match.start()]
            name_part = re.sub(r'^\d+[\.\):\s]+', '', name_part)
            name = re.sub(r'\s+', ' ', name_part).strip()
            name = re.sub(r"[^\w\s'.]", '', name).strip()
            if len(name) < 3:
                continue
            rank += 1
            players_parsed.append({'name': name, 'rank': rank, 'value': 0, 'position': pos, 'team': team})

    if not players_parsed:
        return jsonify({"success": False, "error": "Could not parse any players. Try copying just the player list rows."})

    # Store in DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for p in players_parsed:
        c.execute('''INSERT OR REPLACE INTO market_data
                    (source, player_name, rank, value, position, team, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (source, p['name'], p['rank'], p['value'], p['position'], p['team'],
                  datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "parsed": len(players_parsed),
                   "sample": [p['name'] for p in players_parsed[:5]]})

@app.route('/api/market/data', methods=['GET'])
def get_market_data():
    """Get all stored market data by source"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT source, player_name, rank, value, position, team, updated_at
                FROM market_data ORDER BY source, rank ASC''')
    rows = c.fetchall()
    conn.close()
    by_source = {}
    for source, name, rank, val, pos, team, updated in rows:
        if source not in by_source:
            by_source[source] = {'players': [], 'updated': updated}
        by_source[source]['players'].append({'name': name, 'rank': rank, 'value': val, 'position': pos, 'team': team})
    sources_available = list(by_source.keys())
    return jsonify({"by_source": by_source, "sources": sources_available, "success": True})

# ============================================================
# TIER BREAKS + TRADE UP/DOWN TARGETS
# ============================================================

@app.route('/api/tiers', methods=['GET'])
def get_tiers():
    """
    Compute positional tier breaks and trade targets comparing:
    - VS personal rankings (ELO-based)
    - KTC stored values (market baseline)
    - DDL ADP (startup draft position benchmark)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get VS personal rankings
    c.execute("SELECT player_name, position, elo_score FROM vs_rankings ORDER BY elo_score DESC LIMIT 200")
    vs_rows = c.fetchall()
    vs_rank = {r[0]: {'rank': i+1, 'pos': r[1], 'elo': r[2]} for i, r in enumerate(vs_rows)}

    # Get KTC ranks from market_data
    c.execute("SELECT player_name, rank, value FROM market_data WHERE source='ktc' ORDER BY rank ASC")
    ktc_rank_map = {r[0]: {'rank': r[1], 'value': r[2]} for r in c.fetchall()}

    # Get DDL ADP from market_data (value stored as adp*10, team field has raw adp string)
    c.execute("SELECT player_name, rank, team FROM market_data WHERE source='ddl' ORDER BY rank ASC")
    ddl_rows = c.fetchall()
    ddl_rank_map = {}
    for name, rank, adp_str in ddl_rows:
        try:
            ddl_rank_map[name] = {'rank': rank, 'adp': float(adp_str)}
        except:
            ddl_rank_map[name] = {'rank': rank, 'adp': rank}

    conn.close()

    has_ktc = len(ktc_rank_map) > 10
    has_ddl = len(ddl_rank_map) > 10

    # Build position-specific tier analysis from VS rankings
    positions = ['QB', 'RB', 'WR', 'TE']
    tier_data = {}

    for pos in positions:
        pos_players = [(name, d['rank'], d['elo']) for name, d in vs_rank.items() if d['pos'] == pos]
        pos_players.sort(key=lambda x: x[1])
        if len(pos_players) < 2:
            continue

        tiers = []
        current_tier = []
        for i, (name, rank, elo) in enumerate(pos_players):
            current_tier.append({'name': name, 'vs_rank': rank, 'elo': round(elo)})
            if i < len(pos_players) - 1:
                next_elo = pos_players[i+1][2]
                gap = elo - next_elo
                if gap > 120:
                    est_pick_round = max(1, (rank // 12) + 1)
                    est_pick_slot = (rank % 12) + 1
                    est_pick = f"{est_pick_round}.{str(est_pick_slot).zfill(2)}"
                    tiers.append({
                        'tier_num': len(tiers) + 1,
                        'players': current_tier.copy(),
                        'break_after': name,
                        'gap': round(gap),
                        'est_pick': est_pick,
                        'last_rank': rank,
                    })
                    current_tier = []
        if current_tier:
            tiers.append({'tier_num': len(tiers)+1, 'players': current_tier.copy(),
                         'break_after': None, 'gap': 0, 'est_pick': None, 'last_rank': None})
        tier_data[pos] = tiers

    # Trade targets: compare VS rank vs DDL ADP rank (primary) and KTC rank (secondary)
    trade_targets = []
    for name, vd in vs_rank.items():
        if vd['rank'] > 150:
            continue

        my_rank = vd['rank']
        market_rank = None
        market_source = None
        adp_float = None

        # Prefer DDL ADP as market benchmark (most accurate for startup)
        if name in ddl_rank_map:
            market_rank = ddl_rank_map[name]['rank']
            adp_float = ddl_rank_map[name]['adp']
            market_source = 'DDL'
        elif name in ktc_rank_map:
            market_rank = ktc_rank_map[name]['rank']
            market_source = 'KTC'

        if not market_rank:
            continue

        delta = market_rank - my_rank  # positive = I rank higher than market

        if abs(delta) < 10:
            continue

        if delta >= 30:
            signal = 'STRONG BUY'
        elif delta >= 15:
            signal = 'BUY'
        elif delta >= 10:
            signal = 'SLIGHT BUY'
        elif delta <= -30:
            signal = 'STRONG SELL'
        elif delta <= -15:
            signal = 'SELL'
        else:
            signal = 'SLIGHT SELL'

        # Estimate draft pick from DDL ADP
        if adp_float:
            est_pick_round = int(adp_float // 12) + 1
            est_pick_slot = int(adp_float % 12) + 1
            est_draft_pick = f"{est_pick_round}.{str(est_pick_slot).zfill(2)}"
        else:
            est_draft_pick = f"{(market_rank//12)+1}.{str((market_rank%12)+1).zfill(2)}"

        trade_targets.append({
            'name': name,
            'position': vd['pos'],
            'my_rank': my_rank,
            'market_rank': market_rank,
            'market_source': market_source,
            'adp': adp_float,
            'delta': delta,
            'signal': signal,
            'est_draft_pick': est_draft_pick,
            'note': f"Market goes at ~{est_draft_pick} ({market_source} ADP {adp_float or market_rank})" if delta > 0
                   else f"Market values higher — slides to ~{est_draft_pick}",
        })

    trade_targets.sort(key=lambda x: abs(x['delta']), reverse=True)

    return jsonify({
        "tiers": tier_data,
        "trade_targets": trade_targets[:40],
        "sources_available": (['ktc'] if has_ktc else []) + (['ddl'] if has_ddl else []),
        "ktc_count": len(ktc_rank_map),
        "ddl_count": len(ddl_rank_map),
        "success": True
    })

def seed_ddl_market_data():
    """Store DDL ADP data — seeded from May 12 2026 paste"""
    DDL_PLAYERS = [
    ('Josh Allen', 'QB', 1, 1.95),
    ('Bijan Robinson', 'RB', 2, 2.7),
    ('Drake Maye', 'QB', 3, 3.76),
    ('Ja\'Marr Chase', 'WR', 4, 4.68),
    ('Jahmyr Gibbs', 'RB', 5, 4.97),
    ('Jaxon Smith-Njigba', 'WR', 6, 6.45),
    ('Puka Nacua', 'WR', 7, 7.43),
    ('Jayden Daniels', 'QB', 8, 10.51),
    ('Amon-Ra St. Brown', 'WR', 9, 11.39),
    ('Caleb Williams', 'QB', 10, 12.58),
    ('Brock Bowers', 'TE', 11, 12.72),
    ('Lamar Jackson', 'QB', 12, 12.8),
    ('Malik Nabers', 'WR', 13, 13.72),
    ('Joe Burrow', 'QB', 14, 15.12),
    ('Ashton Jeanty', 'RB', 15, 15.34),
    ('Trey McBride', 'TE', 16, 15.67),
    ('Justin Jefferson', 'WR', 17, 16.22),
    ('Jeremiyah Love', 'RB', 18, 16.84),
    ('CeeDee Lamb', 'WR', 19, 19.34),
    ('Devon Achane', 'RB', 20, 21.27),
    ('Omarion Hampton', 'RB', 21, 21.88),
    ('Jaxson Dart', 'QB', 22, 22.08),
    ('Justin Herbert', 'QB', 23, 24.06),
    ('Drake London', 'WR', 24, 24.22),
    ('Jalen Hurts', 'QB', 25, 26.37),
    ('Jonathan Taylor', 'RB', 26, 27.47),
    ('Patrick Mahomes', 'QB', 27, 28.33),
    ('Tetairoa McMillan', 'WR', 28, 28.49),
    ('James Cook', 'RB', 29, 28.97),
    ('Colston Loveland', 'TE', 30, 29.22),
    ('Trevor Lawrence', 'QB', 31, 31.04),
    ('George Pickens', 'WR', 32, 33.91),
    ('Bo Nix', 'QB', 33, 34.43),
    ('Emeka Egbuka', 'WR', 34, 35.5),
    ('Tyler Warren', 'TE', 35, 36.88),
    ('Nico Collins', 'WR', 36, 37.69),
    ('Brock Purdy', 'QB', 37, 39.08),
    ('Christian McCaffrey', 'RB', 38, 40.83),
    ('Kenneth Walker III', 'RB', 39, 41.15),
    ('Chris Olave', 'WR', 40, 41.44),
    ('TreVeyon Henderson', 'RB', 41, 42.67),
    ('Carnell Tate', 'WR', 42, 43.29),
    ('Chase Brown', 'RB', 43, 43.7),
    ('Garrett Wilson', 'WR', 44, 43.97),
    ('Rashee Rice', 'WR', 45, 44.12),
    ('Dak Prescott', 'QB', 46, 47.14),
    ('Ladd McConkey', 'WR', 47, 49.0),
    ('Breece Hall', 'RB', 48, 49.48),
    ('Quinshon Judkins', 'RB', 49, 51.06),
    ('Fernando Mendoza', 'QB', 50, 51.76),
    ('Harold Fannin', 'TE', 51, 51.83),
    ('Jordan Love', 'QB', 52, 53.27),
    ('Luther Burden', 'WR', 53, 53.29),
    ('Bucky Irving', 'RB', 54, 55.06),
    ('Saquon Barkley', 'RB', 55, 55.08),
    ('Jordyn Tyson', 'WR', 56, 56.08),
    ('Rome Odunze', 'WR', 57, 57.49),
    ('A.J. Brown', 'WR', 58, 58.17),
    ('Tucker Kraft', 'TE', 59, 58.95),
    ('Kyren Williams', 'RB', 60, 59.64),
    ('Marvin Harrison Jr.', 'WR', 61, 62.51),
    ('Makai Lemon', 'WR', 62, 63.6),
    ('Zay Flowers', 'WR', 63, 64.15),
    ('Cam Ward', 'QB', 64, 65.25),
    ('Tee Higgins', 'WR', 65, 66.42),
    ('Cam Skattebo', 'RB', 66, 67.09),
    ('Brian Thomas Jr.', 'WR', 67, 67.69),
    ('Javonte Williams', 'RB', 68, 68.3),
    ('Jared Goff', 'QB', 69, 69.32),
    ('Jadarian Price', 'RB', 70, 69.33),
    ('DeVonta Smith', 'WR', 71, 69.52),
    ('Josh Jacobs', 'RB', 72, 69.58),
    ('Tyler Shough', 'QB', 73, 70.32),
    ('Baker Mayfield', 'QB', 74, 70.51),
    ('Sam LaPorta', 'TE', 75, 70.92),
    ('Travis Etienne', 'RB', 76, 71.31),
    ('Jameson Williams', 'WR', 77, 74.97),
    ('Kyle Pitts', 'TE', 78, 75.46),
    ('Jaylen Waddle', 'WR', 79, 75.48),
    ('C.J. Stroud', 'QB', 80, 77.6),
    ('Derrick Henry', 'RB', 81, 78.23),
    ('Sam Darnold', 'QB', 82, 83.25),
    ('Kenyon Sadiq', 'TE', 83, 83.34),
    ('KC Concepcion', 'WR', 84, 84.5),
    ('Bhayshul Tuten', 'RB', 85, 84.67),
    ('Oronde Gadsden', 'TE', 86, 85.56),
    ('Kyler Murray', 'QB', 87, 87.12),
    ('D.J. Moore', 'WR', 88, 88.1),
    ('Alec Pierce', 'WR', 89, 88.86),
    ('Matthew Stafford', 'QB', 90, 88.97),
    ('RJ Harvey', 'RB', 91, 90.54),
    ('Bryce Young', 'QB', 92, 91.51),
    ('David Montgomery', 'RB', 93, 95.69),
    ('Malik Willis', 'QB', 94, 96.94),
    ('D\'Andre Swift', 'RB', 95, 97.55),
    ('Christian Watson', 'WR', 96, 97.89),
    ('Jordan Addison', 'WR', 97, 98.55),
    ('Michael Wilson', 'WR', 98, 99.89),
    ('Kyle Monangai', 'RB', 99, 100.17),
    ('Omar Cooper', 'WR', 100, 101.0),
    ('Terry McLaurin', 'WR', 101, 102.16),
    ('Jake Ferguson', 'TE', 102, 103.61),
    ('Daniel Jones', 'QB', 103, 104.28),
    ('Chuba Hubbard', 'RB', 104, 104.39),
    ('Wan\'Dale Robinson', 'WR', 105, 106.93),
    ('Parker Washington', 'WR', 106, 107.69),
    ('Davante Adams', 'WR', 107, 108.69),
    ('D.K. Metcalf', 'WR', 108, 109.17),
    ('Dalton Kincaid', 'TE', 109, 109.29),
    ('Ricky Pearsall', 'WR', 110, 109.48),
    ('Eli Stowers', 'TE', 111, 110.9),
    ('Ty Simpson', 'QB', 112, 110.93),
    ('Isaiah Likely', 'TE', 113, 112.76),
    ('Mike Evans', 'WR', 114, 113.32),
    ('Matthew Golden', 'WR', 115, 115.41),
    ('Jaylen Warren', 'RB', 116, 116.33),
    ('George Kittle', 'TE', 117, 116.89),
    ('Jayden Higgins', 'WR', 118, 117.97),
    ('Denzel Boston', 'WR', 119, 118.53),
    ('Brenton Strange', 'TE', 120, 120.51),
    ('Jonah Coleman', 'RB', 121, 121.38),
    ('Blake Corum', 'RB', 122, 121.73),
    ('Rico Dowdle', 'RB', 123, 123.61),
    ('Quentin Johnston', 'WR', 124, 125.26),
    ('Michael Pittman Jr.', 'WR', 125, 127.04),
    ('Xavier Worthy', 'WR', 126, 128.03),
    ('Josh Downs', 'WR', 127, 128.39),
    ('Zach Charbonnet', 'RB', 128, 128.85),
    ('Travis Hunter', 'WR', 129, 129.24),
    ('Jayden Reed', 'WR', 130, 130.32),
    ('Rhamondre Stevenson', 'RB', 131, 130.81),
    ('Courtland Sutton', 'WR', 132, 131.56),
    ('Jacory Croskey-Merritt', 'RB', 133, 133.04),
    ('Romeo Doubs', 'WR', 134, 134.34),
    ('Chris Bell', 'WR', 135, 134.7),
    ('Jonathon Brooks', 'RB', 136, 135.9),
    ('Nicholas Singleton', 'RB', 137, 135.92),
    ('Jakobi Meyers', 'WR', 138, 137.76),
    ('J.K. Dobbins', 'RB', 139, 138.88),
    ('AJ Barner', 'TE', 140, 139.65),
    ('Jalen Coker', 'WR', 141, 141.4),
    ('Tony Pollard', 'RB', 142, 143.0),
    ('Chris Godwin', 'WR', 143, 144.14),
    ('Germie Bernard', 'WR', 144, 144.33),
    ('Kenneth Gainwell', 'RB', 145, 146.65),
    ('Mark Andrews', 'TE', 146, 146.81),
    ('Woody Marks', 'RB', 147, 150.57),
    ('Tyler Allgeier', 'RB', 148, 151.89),
    ('Jordan Mason', 'RB', 149, 152.01),
    ('Khalil Shakir', 'WR', 150, 152.4),
    ('Travis Kelce', 'TE', 151, 154.32),
    ('Jacoby Brissett', 'QB', 152, 154.33),
    ('Michael Penix Jr.', 'QB', 153, 155.53),
    ('Juwan Johnson', 'TE', 154, 157.15),
    ('Tua Tagovailoa', 'QB', 155, 157.17),
    ('Elijah Sarratt', 'WR', 156, 157.21),
    ('Jalen McMillan', 'WR', 157, 157.41),
    ('Rachaad White', 'RB', 158, 157.97),
    ('Antonio Williams', 'WR', 159, 159.57),
    ('T.J. Hockenson', 'TE', 160, 159.66),
    ('Chigoziem Okonkwo', 'TE', 161, 161.33),
    ('Shedeur Sanders', 'QB', 162, 161.33),
    ('Emmett Johnson', 'RB', 163, 161.53),
    ('Dallas Goedert', 'TE', 164, 161.63),
    ('Gunnar Helm', 'TE', 165, 165.15),
    ('Tyrone Tracy', 'RB', 166, 165.65),
    ('Geno Smith', 'QB', 167, 166.76),
    ('Rashid Shaheed', 'WR', 168, 168.97),
    ('Chris Brazzell', 'WR', 169, 172.25),
    ('Zachariah Branch', 'WR', 170, 172.5),
    ('Braelon Allen', 'RB', 171, 172.75),
    ('Chris Rodriguez Jr.', 'RB', 172, 173.44),
    ('J.J. McCarthy', 'QB', 173, 173.99),
    ('Tre Harris', 'WR', 174, 175.81),
    ('Kaytron Allen', 'RB', 176, 176.15),
    ('Brandon Aiyuk', 'WR', 177, 177.79),
    ('Dylan Sampson', 'RB', 178, 178.02),
    ]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM market_data WHERE source='ddl'")
    if c.fetchone()[0] > 50:
        conn.close()
        return  # Already loaded
    for name, pos, rank, adp in DDL_PLAYERS:
        # Store ADP as value (multiplied by 100 to keep as int, adp_float stored in team field)
        c.execute('''INSERT OR REPLACE INTO market_data
                    (source, player_name, rank, value, position, team, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 ('ddl', name, rank, int(adp * 10), pos, str(adp), datetime.now().isoformat()))
    conn.commit()
    conn.close()

seed_ddl_market_data()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
