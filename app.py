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
    # KTC-calibrated starting ELO scores based on May 2026 values
    # Maps player/pick name to starting ELO (scaled from KTC values)
    KTC_SEED_ELOS = {
        "Josh Allen": 1980, "Ja Marr Chase": 1978, "Bijan Robinson": 1978,
        "Jaxon Smith-Njigba": 1970, "Jahmyr Gibbs": 1930, "Drake Maye": 1920,
        "Brock Bowers": 1850, "Puka Nacua": 1830, "Trey McBride": 1800,
        "Caleb Williams": 1770, "Malik Nabers": 1760, "Jayden Daniels": 1755,
        "Justin Jefferson": 1750, "Amon-Ra St. Brown": 1742, "Lamar Jackson": 1740,
        "Jeremiyah Love": 1738, "Ashton Jeanty": 1730, "Joe Burrow": 1720,
        "CeeDee Lamb": 1710, "2027 Early 1st": 1705, "De'Von Achane": 1688,
        "Drake London": 1688, "Justin Herbert": 1682, "Patrick Mahomes": 1681,
        "Colston Loveland": 1670, "Omarion Hampton": 1669, "Jaxson Dart": 1667,
        "Tetairoa McMillan": 1655, "Tyler Warren": 1633, "Trevor Lawrence": 1622,
        "Jalen Hurts": 1620, "Emeka Egbuka": 1618, "Bo Nix": 1614,
        "Jonathan Taylor": 1606, "James Cook": 1604, "George Pickens": 1596,
        "Brock Purdy": 1584, "Carnell Tate": 1583, "Garrett Wilson": 1572,
        "2026 Early 1st": 1572, "Fernando Mendoza": 1567, "Nico Collins": 1567,
        "Jordan Love": 1564, "2027 Mid 1st": 1560, "Chris Olave": 1557,
        "Quinshon Judkins": 1547, "Harold Fannin": 1546, "Kenneth Walker": 1546,
        "TreVeyon Henderson": 1540, "Rome Odunze": 1537, "Tucker Kraft": 1536,
        "Breece Hall": 1535, "Jordyn Tyson": 1535, "Ladd McConkey": 1535,
        "Rashee Rice": 1525, "Cam Ward": 1524, "DeVonta Smith": 1521,
        "Luther Burden": 1520, "Marvin Harrison Jr": 1508, "Sam LaPorta": 1504,
        "Christian McCaffrey": 1499, "Makai Lemon": 1499, "Dak Prescott": 1498,
        "2028 Early 1st": 1497, "Brian Thomas Jr": 1493, "Bucky Irving": 1492,
        "Kyle Pitts": 1492, "Saquon Barkley": 1490, "Chase Brown": 1490,
        "Tyler Shough": 1490, "2027 Late 1st": 1489, "Tee Higgins": 1488,
        "AJ Brown": 1487, "CJ Stroud": 1485, "Kyren Williams": 1485,
        "Jaylen Waddle": 1481, "Sam Darnold": 1475, "Baker Mayfield": 1474,
        "Jadarian Price": 1471, "Jameson Williams": 1470, "Zay Flowers": 1469,
        "Jared Goff": 1462, "Kenyon Sadiq": 1462, "2026 Mid 1st": 1460,
        "Cam Skattebo": 1456, "Bryce Young": 1451, "KC Concepcion": 1449,
        "Josh Jacobs": 1446, "Travis Etienne": 1445, "Javonte Williams": 1443,
        "2028 Mid 1st": 1442, "Oronde Gadsden": 1434, "Kyler Murray": 1411,
        "Eli Stowers": 1397, "Isaiah Likely": 1376, "Bhayshul Tuten": 1394,
        "2028 Late 1st": 1392, "2027 Early 2nd": 1391, "2026 Late 1st": 1388,
        "Denzel Boston": 1445, "Trey Benson": 1429, "Tank Bigsby": 1453,
        "2027 Mid 2nd": 1404, "2027 Late 2nd": 1396, "2026 Early 2nd": 1396,
        "2027 Early 3rd": 1345, "2028 Early 2nd": 1362, "Travis Hunter": 1330,
        "Chris Bell": 1346, "Germie Bernard": 1313, "Zachariah Branch": 1314,
        "Antonio Williams": 1298, "Malachi Fields": 1290, "Skyler Bell": 1309,
        "2026 Mid 2nd": 1326, "2027 Mid 3rd": 1271, "2028 Mid 2nd": 1293,
        "2026 Late 2nd": 1277, "Max Klare": 1317, "Kaytron Allen": 1314,
        "Justin Joly": 1131, "Eli Raridon": 934, "Oscar Delp": 1054,
        "2027 Early 4th": 1057, "2026 Early 3rd": 1076, "2027 Mid 4th": 1064,
        "2026 Mid 3rd": 1040, "2026 Late 3rd": 1013, "2026 Early 4th": 998,
    }
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    for name, pos, team in DEFAULT_PLAYERS:
        starting_elo = KTC_SEED_ELOS.get(name, 1500)
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

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": """Generate a dynasty GM dashboard for MJBrutus. Use your knowledge of his rosters plus 1-2 web searches for breaking news. Return ONLY valid JSON with no other text:
{"alerts":[{"type":"warning","league":"Capital Gains","message":"text","action":"what to do"},{"type":"opportunity","league":"Gentleman's","message":"text","action":"what to do"}],
"news":[{"player":"name","team":"team","position":"QB","leagues":["Capital Gains"],"headline":"news item","impact":"dynasty impact","recommendation":"BUY"},{"player":"name2","team":"team2","position":"WR","leagues":["TRS"],"headline":"news item","impact":"dynasty impact","recommendation":"HOLD"}],
"movers":[{"player":"name","direction":"up","change":"+200","reason":"why moving","action":"consider selling"}],
"trade_targets":[{"player":"LaPorta","owner":"c1smith11","league":"Gentleman's","offer":"Njoku and 2027 2nd for LaPorta","rationale":"TE premium upgrade"}],
"weekly_priorities":["Send LaPorta offer to c1smith11 in Gentleman's","Monitor AJ Brown news for TRS impact","Prep Velvet Spade startup strategy"]}"""}]
        )
        assistant_message = "".join(b.text for b in response.content if hasattr(b, 'text'))
        # Clean JSON from response
        text = assistant_message.strip()
        # Find JSON object boundaries
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            text = text[start:end]
        return jsonify({"data": json.loads(text), "success": True})
    except Exception as e:
        # Return fallback dashboard on error
        fallback = {
            "alerts": [
                {"type": "warning", "league": "TRS", "message": "DST currently TB Team Defense — monitor injury reports", "action": "Check waiver wire for streaming options"},
                {"type": "opportunity", "league": "Gentleman's", "message": "LaPorta on trade block at c1smith11", "action": "Send Njoku + 2027 2nd offer today"}
            ],
            "news": [
                {"player": "Sam LaPorta", "team": "DET", "position": "TE", "leagues": ["Capital Gains", "Gentleman's"], "headline": "Back surgery recovery on track for training camp", "impact": "Buy-low window before value returns", "recommendation": "BUY"},
                {"player": "Drake Maye", "team": "NE", "position": "QB", "leagues": ["Capital Gains", "TRS", "Gentleman's"], "headline": "AJ Brown trade expected post June 1", "impact": "Adds elite WR1 — Maye value increases", "recommendation": "HOLD"}
            ],
            "movers": [
                {"player": "Carnell Tate", "direction": "up", "change": "+150", "reason": "Strong NFL pre-draft buzz as WR1 in Tennessee", "action": "Hold — core asset"},
                {"player": "Deshaun Watson", "direction": "down", "change": "-200", "reason": "Sanders expected to win Cleveland starting job", "action": "Sell in TRS if possible"}
            ],
            "trade_targets": [
                {"player": "Sam LaPorta", "owner": "c1smith11", "league": "Gentleman's Dynasty", "offer": "Njoku and 2027 2nd for LaPorta", "rationale": "TE premium league upgrade — #1 offseason priority"},
                {"player": "JJ McCarthy", "owner": "dcatlet", "league": "Gentleman's Dynasty", "offer": "McCarthy for 2027 2nd to SenorHyde", "rationale": "SenorHyde desperate for QB — convert to picks"}
            ],
            "weekly_priorities": [
                "Send LaPorta offer to c1smith11 in Gentleman's Dynasty",
                "Finalize Velvet Spade startup draft strategy before May 15",
                "Sell Deshaun Watson in TRS before value drops further"
            ]
        }
        return jsonify({"data": fallback, "success": True})

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
            model="claude-sonnet-4-5",
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

    # 3. Sleeper ADP from trending
    sleeper_ranks = {}
    try:
        r = requests.get('https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=168&limit=300',
                        timeout=8)
        if r.status_code == 200:
            # Also get player names
            players_r = requests.get('https://api.sleeper.app/v1/players/nfl', timeout=15)
            if players_r.status_code == 200:
                players_db = players_r.json()
                for i, item in enumerate(r.json()):
                    pid = item.get('player_id', '')
                    if pid in players_db:
                        p = players_db[pid]
                        name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                        sleeper_ranks[name] = i + 1
    except:
        pass

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

YOUTUBE_CHANNELS = {
    "Dynasty Domain": {"id": "UCRk2EqEe1iLBdsSBEsZJqkA"},
    "Pure Potential": {"id": "UCJ9EcWZvGWCiD9T-5YGR9sA"},
    "The FF Dynasty": {"id": "UCxdIF1wU7jX-htzVCDmDu8A"},
    "Dynasty Nerds": {"id": "UCyMng_8VKXye0ObmRX7Occw"},
    "Dynasty Points": {"id": "UCpKe4bQ8bFQ5LZlOP1CHKRg"},
    "Dynasty Life": {"id": "UCGW37K5apqmzbVWMEe_TDkg"},
    "Fantasy Football Today": {"id": "UC8UBHgHqjxhDFKvLNYGHbkQ"},
    "Fantasy Footballers": {"id": "UCeHOKbPNIoMaLBxCRl0NJFg"},
    "Matthew Berry": {"id": "UCIRiiqCOpCLlpGTNE0zMDgw"},
    "PFF Fantasy": {"id": "UCOYbSbHGxEMxJePL0dIBm3g"},
}

def init_kb_db():
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS knowledge_base
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 source TEXT NOT NULL, video_id TEXT UNIQUE,
                 title TEXT, summary TEXT, key_insights TEXT,
                 players_mentioned TEXT, fetched_at TEXT NOT NULL,
                 video_date TEXT)''')
    conn.commit()
    conn.close()

init_kb_db()

def get_recent_videos_from_channel(channel_id, max_results=3):
    """Get recent video IDs from a YouTube channel via RSS feed (no API key needed)"""
    try:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; DynastyGM/1.0)'}
        r = requests.get(rss_url, timeout=15, headers=headers)
        if r.status_code != 200:
            return []

        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom',
              'yt': 'http://www.youtube.com/xml/schemas/2015'}

        videos = []
        entries = root.findall('atom:entry', ns)[:max_results]
        for entry in entries:
            vid_id = entry.find('yt:videoId', ns)
            title_el = entry.find('atom:title', ns)
            published = entry.find('atom:published', ns)
            if vid_id is not None and title_el is not None:
                videos.append({
                    'id': vid_id.text,
                    'title': title_el.text,
                    'date': published.text[:10] if published is not None else ''
                })
        return videos
    except Exception as e:
        print(f"RSS error for {channel_id}: {e}")
        return []

def get_youtube_transcript(video_id):
    """Get YouTube transcript - tries multiple methods"""
    # Method 1: youtube-transcript-api (works when not blocked)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, languages=['en', 'en-US', 'en-GB']
        )
        full_text = ' '.join([t['text'] for t in transcript_list])
        if full_text and len(full_text) > 100:
            return full_text[:8000]
    except Exception as e:
        print(f"Transcript API error for {video_id}: {e}")

    # Method 2: YouTube timedtext endpoint
    try:
        for lang in ['en', 'en-US']:
            url = f"https://www.youtube.com/api/timedtext?lang={lang}&v={video_id}&fmt=json3"
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
            r = requests.get(url, timeout=10, headers=headers)
            if r.status_code == 200 and r.text and len(r.text) > 50:
                try:
                    data = r.json()
                    events = data.get('events', [])
                    texts = []
                    for event in events:
                        segs = event.get('segs', [])
                        for seg in segs:
                            t = seg.get('utf8', '').strip()
                            if t and t != '\n':
                                texts.append(t)
                    if texts:
                        return ' '.join(texts)[:8000]
                except Exception:
                    pass
    except Exception as e:
        print(f"Timedtext error for {video_id}: {e}")

    # Method 3: XML timedtext
    try:
        url = f"https://www.youtube.com/api/timedtext?lang=en&v={video_id}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.content and len(r.content) > 50:
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(r.content)
                texts = [el.text for el in root.findall('.//text') if el.text]
                if texts:
                    return ' '.join(texts)[:8000]
            except Exception:
                pass
    except Exception as e:
        print(f"XML timedtext error for {video_id}: {e}")

    return None

def summarize_video_via_search(title, source, video_id):
    """Fallback: use Claude web search to find insights about the video topic"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=600,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
            messages=[{"role": "user", "content": f"""Search for dynasty fantasy football insights related to this video: "{title}" from {source}.

Find the key dynasty topics, player mentions, and advice covered. Return JSON only:
{{"summary": "2-3 sentence summary", "key_insights": ["insight 1", "insight 2", "insight 3"], "players_mentioned": ["player1", "player2"], "trade_signals": ["signal 1"]}}

Return only valid JSON."""}]
        )
        text = "".join(b.text for b in response.content if hasattr(b, 'text'))
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"Search summarize error: {e}")
    return None

def summarize_transcript(title, transcript, source):
    """Use Claude to extract dynasty insights from transcript"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": f"""You are analyzing a dynasty fantasy football video transcript.

Source: {source}
Title: {title}
Transcript (partial): {transcript[:4000]}

Extract and return JSON only:
{{
  "summary": "2-3 sentence summary of main topics",
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "players_mentioned": ["player1", "player2", "player3"],
  "trade_signals": ["buy signal 1", "sell signal 2"],
  "dynasty_themes": ["theme 1", "theme 2"]
}}

Focus on actionable dynasty advice, player values, trade targets, and strategic insights. Return only valid JSON."""}]
        )
        text = response.content[0].text.strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        pass
    return None

@app.route('/api/knowledge/test', methods=['GET'])
def test_knowledge():
    """Test a single channel to diagnose issues"""
    channel_id = request.args.get('channel_id', 'UCJ9EcWZvGWCiD9T-5YGR9sA')
    video_id = request.args.get('video_id', '')

    result = {'channel_id': channel_id, 'steps': []}

    # Step 1: Test RSS
    try:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; DynastyGM/1.0)'}
        r = requests.get(rss_url, timeout=15, headers=headers)
        result['steps'].append({
            'step': 'RSS fetch',
            'status': r.status_code,
            'ok': r.status_code == 200,
            'content_preview': r.text[:200] if r.status_code == 200 else r.text[:100]
        })

        if r.status_code == 200:
            videos = get_recent_videos_from_channel(channel_id, max_results=3)
            result['steps'].append({
                'step': 'Video parsing',
                'ok': len(videos) > 0,
                'videos_found': len(videos),
                'videos': videos
            })

            if videos and not video_id:
                video_id = videos[0]['id']
    except Exception as e:
        result['steps'].append({'step': 'RSS fetch', 'ok': False, 'error': str(e)})

    # Step 2: Test transcript
    if video_id:
        try:
            transcript = get_youtube_transcript(video_id)
            result['steps'].append({
                'step': 'Transcript fetch',
                'video_id': video_id,
                'ok': transcript is not None,
                'length': len(transcript) if transcript else 0,
                'preview': transcript[:200] if transcript else None
            })
        except Exception as e:
            result['steps'].append({'step': 'Transcript fetch', 'ok': False, 'error': str(e)})

    # Step 3: Check youtube-transcript-api installed
    try:
        import youtube_transcript_api
        try:
            ver = youtube_transcript_api.__version__
        except AttributeError:
            ver = "installed (version unknown)"
        result['youtube_transcript_api'] = ver
    except ImportError:
        result['youtube_transcript_api'] = "NOT INSTALLED"

    return jsonify(result)

@app.route('/api/knowledge/refresh', methods=['POST'])
def refresh_knowledge_base():
    """Fetch latest videos and extract insights"""
    results = {'processed': 0, 'errors': 0, 'skipped': 0, 'sources': [], 'error_details': []}

    for source_name, channel in YOUTUBE_CHANNELS.items():
        channel_id = channel['id']
        if not channel_id or len(channel_id) < 10:
            results['error_details'].append(f"{source_name}: invalid channel ID '{channel_id}'")
            results['errors'] += 1
            continue

        videos = get_recent_videos_from_channel(channel_id, max_results=2)

        if not videos:
            results['error_details'].append(f"{source_name}: RSS fetch returned 0 videos (channel_id={channel_id})")
            results['errors'] += 1
            continue

        source_result = {'source': source_name, 'videos': []}

        for video in videos:
            # Check if already processed
            conn = sqlite3.connect('dynasty.db')
            c = conn.cursor()
            c.execute("SELECT id FROM knowledge_base WHERE video_id=?", (video['id'],))
            existing = c.fetchone()
            conn.close()

            if existing:
                results['skipped'] += 1
                continue

            transcript = get_youtube_transcript(video['id'])
            if not transcript:
                # Fallback: use web search to find insights about this video topic
                print(f"No transcript for {video['id']}, trying search fallback...")
                insights = summarize_video_via_search(video['title'], source_name, video['id'])
                if not insights:
                    results['error_details'].append(f"{source_name} - '{video['title'][:40]}': no transcript + search fallback failed")
                    results['errors'] += 1
                    continue
            else:
                insights = summarize_transcript(video['title'], transcript, source_name)
                if not insights:
                    results['error_details'].append(f"{source_name} - '{video['title'][:40]}': summarization failed")
                    results['errors'] += 1
                    continue

            conn = sqlite3.connect('dynasty.db')
            c = conn.cursor()
            c.execute('''INSERT OR IGNORE INTO knowledge_base
                        (source, video_id, title, summary, key_insights, players_mentioned, fetched_at, video_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                     (source_name, video['id'],
                      video['title'],
                      insights.get('summary', ''),
                      json.dumps(insights.get('key_insights', [])),
                      json.dumps(insights.get('players_mentioned', [])),
                      datetime.now().isoformat(),
                      video['date']))
            conn.commit()
            conn.close()

            results['processed'] += 1
            source_result['videos'].append({
                'title': video['title'],
                'insights_count': len(insights.get('key_insights', []))
            })

        if source_result['videos']:
            results['sources'].append(source_result)

    return jsonify({"results": results, "success": True})

@app.route('/api/knowledge/feed', methods=['GET'])
def get_knowledge_feed():
    """Get knowledge base entries organized by source"""
    source_filter = request.args.get('source', None)
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()

    if source_filter:
        c.execute('''SELECT source, video_id, title, summary, key_insights, players_mentioned, fetched_at, video_date
                    FROM knowledge_base WHERE source=? ORDER BY fetched_at DESC LIMIT 20''',
                 (source_filter,))
    else:
        c.execute('''SELECT source, video_id, title, summary, key_insights, players_mentioned, fetched_at, video_date
                    FROM knowledge_base ORDER BY fetched_at DESC LIMIT 50''')

    rows = c.fetchall()
    conn.close()

    entries = []
    for row in rows:
        source, vid_id, title, summary, key_insights, players, fetched_at, vid_date = row
        entries.append({
            'source': source,
            'video_id': vid_id,
            'title': title,
            'summary': summary,
            'key_insights': json.loads(key_insights) if key_insights else [],
            'players_mentioned': json.loads(players) if players else [],
            'fetched_at': fetched_at,
            'video_date': vid_date,
            'url': f'https://youtube.com/watch?v={vid_id}'
        })

    # Group by source
    by_source = {}
    for e in entries:
        src = e['source']
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(e)

    return jsonify({"by_source": by_source, "total": len(entries), "success": True})

@app.route('/api/knowledge/search', methods=['POST'])
def search_knowledge():
    """Search knowledge base for specific player or topic"""
    query = request.json.get('query', '').lower()
    conn = sqlite3.connect('dynasty.db')
    c = conn.cursor()
    c.execute('''SELECT source, title, summary, key_insights, players_mentioned, fetched_at, video_id
                FROM knowledge_base
                WHERE LOWER(summary) LIKE ? OR LOWER(key_insights) LIKE ? OR LOWER(players_mentioned) LIKE ?
                ORDER BY fetched_at DESC LIMIT 20''',
             (f'%{query}%', f'%{query}%', f'%{query}%'))
    rows = c.fetchall()
    conn.close()

    results = []
    for row in rows:
        source, title, summary, key_insights, players, fetched_at, vid_id = row
        results.append({
            'source': source, 'title': title, 'summary': summary,
            'key_insights': json.loads(key_insights) if key_insights else [],
            'players_mentioned': json.loads(players) if players else [],
            'fetched_at': fetched_at,
            'url': f'https://youtube.com/watch?v={vid_id}'
        })

    return jsonify({"results": results, "success": True})

# ============================================================
# STARTUP DRAFT ASSISTANT — VELVET SPADE MODE
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
