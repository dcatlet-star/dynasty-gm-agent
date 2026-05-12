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
    ELO scale maps to KTC tiers with proper separation:
    Tier 1 (9000+ KTC):    2800-3000 ELO
    Tier 2 (7500-8999):    2400-2799 ELO
    Tier 3 (6000-7499):    2000-2399 ELO
    Tier 4 (4500-5999):    1600-1999 ELO
    Tier 5 (3000-4499):    1200-1599 ELO
    Tier 6 (1500-2999):     800-1199 ELO
    Tier 7 (under 1500):    400-799  ELO
    """
    KTC_SEED_ELOS = {
        # TIER 1: 9000+ KTC → 2800-3000
        "Josh Allen": 3000, "Ja Marr Chase": 2980, "Bijan Robinson": 2980,
        "Jaxon Smith-Njigba": 2950,
        # TIER 2: 7500-8999 → 2400-2799
        "Jahmyr Gibbs": 2780, "Drake Maye": 2750, "Brock Bowers": 2700,
        "Puka Nacua": 2660, "Trey McBride": 2600, "Caleb Williams": 2560,
        "Malik Nabers": 2530, "Jayden Daniels": 2520, "Justin Jefferson": 2510,
        "Amon-Ra St. Brown": 2490, "Lamar Jackson": 2480, "Jeremiyah Love": 2470,
        "Ashton Jeanty": 2450, "Joe Burrow": 2430,
        # TIER 3: 6000-7499 → 2000-2399
        "CeeDee Lamb": 2380, "2027 Early 1st": 2360, "De'Von Achane": 2340,
        "Drake London": 2340, "Justin Herbert": 2320, "Patrick Mahomes": 2310,
        "Colston Loveland": 2290, "Omarion Hampton": 2280, "Jaxson Dart": 2270,
        "Tetairoa McMillan": 2250, "Tyler Warren": 2220, "Trevor Lawrence": 2200,
        "Jalen Hurts": 2190, "Emeka Egbuka": 2180, "Bo Nix": 2160,
        "Jonathan Taylor": 2150, "James Cook": 2140, "George Pickens": 2110,
        "Brock Purdy": 2080, "Carnell Tate": 2070, "Garrett Wilson": 2040,
        "2026 Early 1st": 2040, "Fernando Mendoza": 2030, "Nico Collins": 2020,
        "Jordan Love": 2010,
        # TIER 4: 4500-5999 → 1600-1999
        "2027 Mid 1st": 1990, "Chris Olave": 1975, "Quinshon Judkins": 1960,
        "Harold Fannin": 1950, "Kenneth Walker": 1950, "TreVeyon Henderson": 1940,
        "Rome Odunze": 1930, "Tucker Kraft": 1920, "Breece Hall": 1910,
        "Jordyn Tyson": 1900, "Ladd McConkey": 1890, "Rashee Rice": 1880,
        "Cam Ward": 1870, "DeVonta Smith": 1860, "Luther Burden": 1850,
        "Marvin Harrison Jr": 1840, "Sam LaPorta": 1820, "Christian McCaffrey": 1810,
        "Makai Lemon": 1800, "Dak Prescott": 1790, "2028 Early 1st": 1780,
        "Brian Thomas Jr": 1770, "Bucky Irving": 1760, "Kyle Pitts": 1750,
        "Saquon Barkley": 1740, "Chase Brown": 1730, "Tyler Shough": 1720,
        "2027 Late 1st": 1710, "Tee Higgins": 1700, "AJ Brown": 1695,
        "CJ Stroud": 1685, "Kyren Williams": 1675, "Jaylen Waddle": 1665,
        "Sam Darnold": 1655, "Baker Mayfield": 1645, "Jadarian Price": 1640,
        "Jameson Williams": 1630, "Zay Flowers": 1620, "Jared Goff": 1615,
        "Kenyon Sadiq": 1610, "2026 Mid 1st": 1605,
        # TIER 5: 3000-4499 → 1200-1599
        "Cam Skattebo": 1595, "Bryce Young": 1580, "KC Concepcion": 1570,
        "Josh Jacobs": 1560, "Travis Etienne": 1550, "Javonte Williams": 1540,
        "2028 Mid 1st": 1530, "Oronde Gadsden": 1510, "Kyler Murray": 1490,
        "Eli Stowers": 1480, "Isaiah Likely": 1460, "Bhayshul Tuten": 1450,
        "2028 Late 1st": 1440, "2027 Early 2nd": 1430, "2026 Late 1st": 1420,
        "Denzel Boston": 1410, "Trey Benson": 1400, "Tank Bigsby": 1390,
        "2027 Mid 2nd": 1380, "2027 Late 2nd": 1370, "2026 Early 2nd": 1360,
        "Travis Hunter": 1340, "Chris Bell": 1330, "Germie Bernard": 1310,
        "Zachariah Branch": 1300, "Antonio Williams": 1290, "Malachi Fields": 1280,
        "Skyler Bell": 1270, "2026 Mid 2nd": 1260, "Max Klare": 1250,
        "Kaytron Allen": 1240, "2027 Early 3rd": 1230, "2028 Early 2nd": 1220,
        "2027 Mid 3rd": 1210,
        # TIER 6: 1500-2999 → 800-1199
        "2028 Mid 2nd": 1190, "2026 Late 2nd": 1170, "2027 Late 3rd": 1150,
        "2028 Late 2nd": 1130, "2026 Early 3rd": 1110, "2027 Early 4th": 1090,
        "2026 Mid 3rd": 1070, "2027 Mid 4th": 1050, "2026 Late 3rd": 1030,
        "2028 Early 3rd": 1010, "Oscar Delp": 990, "2028 Mid 3rd": 970,
        "2026 Early 4th": 950, "2026 Mid 4th": 930, "2028 Late 3rd": 910,
        "2027 Late 4th": 890, "2028 Early 4th": 870,
        # TIER 7: under 1500 → 400-799
        "Justin Joly": 780, "Eli Raridon": 650,
    }
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    for name, pos, team in DEFAULT_PLAYERS:
        starting_elo = KTC_SEED_ELOS.get(name, 1400)  # default to Tier 5 bottom
        c.execute("INSERT OR IGNORE INTO player_rankings (player_name, position, team, elo_score, comparisons, last_updated) VALUES (?, ?, ?, ?, 0, ?)",
                 (name, pos, team, starting_elo, datetime.now().isoformat()))
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
    conn = sqlite3.connect('dynasty.db')
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
            conn = sqlite3.connect('dynasty.db')
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
        conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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

    conn = sqlite3.connect('dynasty.db')
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
            conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    conn = sqlite3.connect('dynasty.db')
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
    Compute positional tier breaks and trade targets by comparing:
    - VS personal rankings
    - KTC stored values
    - DDL rankings (if pasted)
    - Sleeper ADP (if pasted)
    Also identifies draft slots where tier breaks occur.
    """
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()

    # Get VS personal rankings
    c.execute("SELECT player_name, position, elo_score FROM vs_rankings ORDER BY elo_score DESC LIMIT 200")
    vs_rows = c.fetchall()
    vs_rank = {r[0]: {'rank': i+1, 'pos': r[1], 'elo': r[2]} for i, r in enumerate(vs_rows)}

    # Get KTC values
    c.execute("SELECT player_name, ktc_value FROM ktc_values GROUP BY player_name HAVING MAX(synced_at)")
    ktc_rows = c.fetchall()
    ktc_vals = {r[0]: r[1] for r in ktc_rows}

    # Get market data
    c.execute("SELECT source, player_name, rank, value FROM market_data ORDER BY source, rank")
    mkt_rows = c.fetchall()
    mkt_by_source = {}
    for source, name, rank, val in mkt_rows:
        if source not in mkt_by_source:
            mkt_by_source[source] = {}
        mkt_by_source[source][name] = {'rank': rank, 'value': val}

    conn.close()

    # Build position-specific tier analysis
    positions = ['QB', 'RB', 'WR', 'TE']
    tier_data = {}

    for pos in positions:
        pos_players = [(name, d['rank'], d['elo']) for name, d in vs_rank.items() if d['pos'] == pos]
        pos_players.sort(key=lambda x: x[1])

        if len(pos_players) < 2:
            continue

        # Detect tier breaks: ELO drop > 120 between consecutive players
        tiers = []
        current_tier = []
        for i, (name, rank, elo) in enumerate(pos_players):
            current_tier.append({'name': name, 'vs_rank': rank, 'elo': round(elo)})
            if i < len(pos_players) - 1:
                next_elo = pos_players[i+1][2]
                gap = elo - next_elo
                if gap > 120:
                    # Calculate what startup pick this tier break falls at
                    # Rough mapping: overall vs_rank -> startup slot
                    overall_rank = rank
                    est_pick_round = (overall_rank // 12) + 1
                    est_pick_slot = (overall_rank % 12) + 1
                    est_pick = str(est_pick_round) + '.' + str(est_pick_slot).zfill(2)
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
            tiers.append({'tier_num': len(tiers)+1, 'players': current_tier.copy(), 'break_after': None, 'gap': 0, 'est_pick': None, 'last_rank': None})

        tier_data[pos] = tiers

    # Trade up/down targets: players you rank significantly higher/lower than KTC
    trade_targets = []
    for name, vd in vs_rank.items():
        if vd['rank'] > 150:
            continue
        # Get KTC rank for this player
        ktc_v = ktc_vals.get(name, 0)
        if not ktc_v:
            continue
        # Compute KTC rank by sorting all players by KTC value
        # Already have vs_rank — approximate KTC rank from value percentile
        ktc_rank_approx = max(1, 200 - int(ktc_v / 50))
        my_rank = vd['rank']
        delta = ktc_rank_approx - my_rank  # positive = I rank higher than KTC (buy signal)

        if abs(delta) >= 15:
            if delta >= 30:
                signal = 'STRONG BUY'
                signal_color = 'gn'
            elif delta >= 15:
                signal = 'BUY'
                signal_color = 'gn'
            elif delta <= -30:
                signal = 'STRONG SELL'
                signal_color = 'rd'
            else:
                signal = 'SELL'
                signal_color = 'rd'

            # Estimate when this player will be drafted based on KTC rank
            est_draft_round = (ktc_rank_approx // 12) + 1
            est_draft_pick = str(est_draft_round) + '.' + str((ktc_rank_approx % 12 + 1)).zfill(2)

            trade_targets.append({
                'name': name,
                'position': vd['pos'],
                'my_rank': my_rank,
                'ktc_rank': ktc_rank_approx,
                'delta': delta,
                'signal': signal,
                'signal_color': signal_color,
                'ktc_value': ktc_v,
                'est_draft_pick': est_draft_pick,
                'trade_up_note': f"Draft {est_draft_pick} to get him" if delta > 0 else f"Could slide past your next pick",
            })

    trade_targets.sort(key=lambda x: abs(x['delta']), reverse=True)

    return jsonify({
        "tiers": tier_data,
        "trade_targets": trade_targets[:30],
        "sources_available": list(mkt_by_source.keys()),
        "success": True
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
