import deepdiff, json, asyncio, time, logging
from logging.handlers import RotatingFileHandler
from peewee import *
from os import environ, path
from dotenv import load_dotenv
from api_models import *
from playhouse.shortcuts import model_to_dict

secret_path = basedir + '/shared/client_secret.json'

# Keys for zipping dicts for entering to database
all_pas_keys = ['Play_No','Inning','Outs','BRC','Play_Type','Pitcher','Pitch_No','Batter','Swing_No','Catcher','Throw_No','Runner','Steal_No','Result','Run_Scored','Ghost_Scored','RBIs','Stolen_Base','Diff','Runs_Scored_On_Play','Off_Team','Def_Team','Game_No','Session_No','Inning_No','Pitcher_ID','Batter_ID','Catcher_ID','Runner_ID','Scored1','Scored2','Scored3','Scored4','Run1','Run2','Run3','Run4','Scored1_ID','Scored2_ID','Scored3_ID','Scored4_ID','Run1_ID','Run2_ID','Run3_ID','Run4_ID']

persons_keys = ['PersonID','Current_Name','Stats_Name','Reddit','Discord','Discord_ID','Team','Player','Captain','GM','Retired','Hiatus','Rookie','Primary','Backup','Hand','CON','EYE','PWR','SPD','MOV','CMD','VEL','AWR']

persons_defaults = { 'Reddit':None,
                 'Discord':None,
                 'Discord_ID':None,
                 'Team':'',
                 'Player':False,
                 'Captain':False,
                 'GM':False,
                 'Retired':False,
                 'Hiatus':False,
                 'Rookie':False,
                 'Primary':'',
                 'Backup':'',
                 'Hand':'R',
                 'CON':0,
                 'EYE':0,
                 'PWR':0,
                 'SPD':0,
                 'MOV':0,
                 'CMD':0,
                 'VEL':0,
                 'AWR':0
                }

teams_keys = ['TID','Abbr','Name','Stadium','League','Division','Logo_URL','Location','Mascot']

schedules_keys = ['Session','Game_No','Away','Home','Game_ID','A_Score','H_Score','Inning','Situation','Win','Loss','WP','LP','SV','POTG','Umpire','Reddit','Duration','Total_Plays','Plays_Per_Day']

lineups_keys = ['Game_No','Team','Player','Play_Entrance','Position','Order','Pitcher_No']

logging.basicConfig(level=logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("baseball")
sheets_handler = RotatingFileHandler(filename='logs/sheets_ref.log', maxBytes=10240, backupCount=10)
sheets_handler.setFormatter(formatter)
logger.addHandler(sheets_handler)

def sleep_dec(func):
    async def inner(sleeptime=60*15):
        while True:
            try: func()
            except Exception as e: 
                msg = func.__name__ + str(e)
                logger.error(msg)
            await asyncio.sleep(sleeptime)
    return inner

def access_sheets():
    gSheet = pygsheets.authorize(service_file=secret_path)
    global prev_pas_sh, cur_pas_sh, persons_sh, teams_sh, schedules_sh, persons_defaults, home_sh, lineups_sh
    p_master_log = gSheet.open_by_key(environ.get('P_MASTER_LOG'))
    prev_pas_sh = p_master_log.worksheet_by_title("All_PAs_1-7")
    cur_pas_sh = p_master_log.worksheet_by_title("All_PAs_8")
    persons_sh = p_master_log.worksheet_by_title("Persons")
    teams_sh = p_master_log.worksheet_by_title("Teams")
    schedules_sh = p_master_log.worksheet_by_title("Schedule")
    ump_central = gSheet.open_by_key('1bnhFwmnuK25NQ29CAeVQlwV-BI_ewlfcnN56H1WNjwM')
    home_sh = ump_central.worksheet_by_title('HOME')
    lineups_sh = ump_central.worksheet_by_title('Lineup Cards')

def generate_db():
    db.connect(reuse_if_open=True)
    db.drop_tables([PAs,Lineups])
    db.create_tables([PAs])
    build_plays_old()
    build_plays_cur()
    persons = build_persons()
    teams = build_teams()
    schedules = build_schedules()
    with db.atomic():
        if persons and teams and schedules:
            db.drop_tables([Persons,Teams,Schedules])
            db.create_tables([Persons,Teams,Schedules])
            Persons.insert_many(persons).execute()
            Teams.insert_many(teams).execute()
            Schedules.insert_many(schedules).execute()
            db.create_tables([Lineups])
    db.close()

def build_meta():
    db.connect(reuse_if_open=True)
    db.drop_tables([Metadata])
    db.create_tables([Metadata])
    home_arr = home_sh.get_values(start='B1',end='B2',include_tailing_empty_rows=False)
    try:
        meta = {'Current_Season':int(home_arr[0][0]), 'Current_Session':int(home_arr[1][0])}
        with db.atomic():
            Metadata.insert(meta).execute()
    except Error as e:
        print(e)

def build_plays_cur():
    pas = []
    cur_pas_val = cur_pas_sh.get_all_values(include_tailing_empty_rows=False)
    for p in cur_pas_val:
        pa = dict(zip(all_pas_keys,p))
        for cat in pa:
            if pa[cat] == '': pa[cat] = None
        pas.append(pa)
    with db.atomic():
        PAs.insert_many(pas).execute()

def build_plays_old():
    ranges = (("A2","AS5000"),("A5001","AS10000"),("A10001","AS15000"),("A15001","AS20000"),("A20001","AS25000"),("A25001","AS30000"),("A30000","AS35000"),("A35001","AS40000"),("A40001","AS41756"))
    for range in ranges:
        pas = []
        prev_pas_val = prev_pas_sh.get_values(start=range[0],end=range[1],include_tailing_empty_rows=False)
        for p in prev_pas_val:
            pa = dict(zip(all_pas_keys,p))
            for cat in pa:
                if pa[cat] == '': pa[cat] = None
            pas.append(pa)
        with db.atomic():
            PAs.insert_many(pas).execute()

def build_persons():
    defaults = { 'Reddit':None,
                 'Discord':None,
                 'Discord_ID':None,
                 'Team':'',
                 'Player':0,
                 'Captain':0,
                 'GM':0,
                 'Retired':0,
                 'Hiatus':0,
                 'Rookie':0,
                 'Primary':'',
                 'Backup':'',
                 'Hand':'R',
                 'CON':0,
                 'EYE':0,
                 'PWR':0,
                 'SPD':0,
                 'MOV':0,
                 'CMD':0,
                 'VEL':0,
                 'AWR':0
               }
    persons = []
    persons_data = persons_sh.get_all_values(include_tailing_empty_rows=False)
    for p in persons_data:
        person = dict(zip(persons_keys,p))
        for cat in person:
            if person[cat] == '' or person[cat] == 'N': person[cat] = defaults[cat]
        persons.append(person)
    persons.pop(0) #header row
    ref_person = []
    for person in persons:
        if person['Discord_ID'] == '136843419321368576': ref_person.append(person)
    try:
        assert len(ref_person) == 1
        assert ref_person[0]['PersonID'] == '1097'
        assert ref_person[0]['Stats_Name'] == 'Jameson Poe'
        return(persons)
    except AssertionError:
        return(None)

def build_teams():
    teams = []
    teams_data = teams_sh.get_all_values(include_tailing_empty_rows=False)
    for t in teams_data:
        team = dict(zip(teams_keys,t))
        teams.append(team)
    teams.pop(0)
    ref_team = []
    for team in teams:
        if team['TID'] == 'T2001': ref_team.append(team)
    try:
        assert len(ref_team) == 1
        assert ref_team[0]['Abbr'] == 'POR'
        return(teams)
    except AssertionError:
        return(None)

def build_schedules():
    schedules = []
    schedules_data = schedules_sh.get_all_values(include_tailing_empty_rows=False)
    for s in schedules_data:
        schedule = dict(zip(schedules_keys,s))
        if schedule['Session'] != 'Session':
            if int(schedule['Session']) != 0 and int(schedule['Session']) < 18:
                for entry in schedule:
                    if schedule[entry] == '':
                        schedule[entry] = None
                schedules.append(schedule)
    ref_sched = []
    for sched in schedules:
        if sched['Game_No'] == '80101': ref_sched.append(sched)
    try:
        assert len(ref_sched) == 1
        assert ref_sched[0]['Game_ID'] == 'ACPOGO1'
        return(schedules)
    except AssertionError:
        return(None)

@sleep_dec
def update_pas():
    pas_list = cur_pas_sh.get_all_values(include_tailing_empty_rows=False)
    cur_session = pas_list[-1][0][0:3]
    int_list = ['Play_No','Outs','BRC','Pitch_No','Swing_No','Throw_No','Steal_No','Run_Scored','Ghost_Scored','RBIs','Stolen_Base','Diff','Runs_Scored_On_Play','Game_No','Session_No','Inning_No','Pitcher_ID','Batter_ID','Catcher_ID','Runner_ID','Scored1_ID','Scored2_ID','Scored3_ID','Scored4_ID','Run1_ID','Run2_ID','Run3_ID','Run4_ID']
    for i in pas_list:
        if i[0].startswith(cur_session):
            sheet_pa_dict = dict(zip(all_pas_keys,i))
            for cat in sheet_pa_dict: 
                if sheet_pa_dict[cat] == '': sheet_pa_dict[cat] = None
                elif cat in int_list: sheet_pa_dict[cat] = int(sheet_pa_dict[cat])
            pa, created = PAs.get_or_create(Play_No=i[0],defaults=sheet_pa_dict)
            if not created:
                diff = deepdiff.DeepDiff(pa.sheets_compare_int(),sheet_pa_dict)
                if bool(diff):
                    changed = {}
                    for diff_type in ['values_changed','type_changes']:
                        if diff_type in diff:
                            for val in diff[diff_type]: changed[val[6:-2]] = diff[diff_type][val]['new_value']
                    PAs.update(changed).where(PAs.Play_No == pa.Play_No).execute()

def validate_persons(persons):
    ref_person = []
    for person in persons:
        if person['Discord_ID'] == '225468192443727873': ref_person.append(person)
    try:
        assert len(ref_person) == 1
        assert ref_person[0]['PersonID'] == 1004
        assert ref_person[0]['Stats_Name'] == 'Pops Dongoria'
        return(persons)
    except AssertionError:
        return(None)

@sleep_dec
def update_persons():
    int_list = ['PersonID','CON','EYE','PWR','SPD','MOV','CMD','VEL','AWR']
    persons = []
    persons_data = persons_sh.get_all_values(include_tailing_empty_rows=False)
    persons_data.pop(0) #header row
    for p in persons_data:
        person = dict(zip(persons_keys,p))
        for cat in person:
            if person[cat] == '': person[cat] = persons_defaults[cat]
            elif person[cat] == 'Y': person[cat] = True
            elif person[cat] == 'N': person[cat] = False
            elif cat in int_list: person[cat] = int(person[cat])
        persons.append(person)
    persons = validate_persons(persons)
    if persons:
        for p in persons:
            person, created = Persons.get_or_create(PersonID = p['PersonID'],defaults=p)
            if not created:
                diff = deepdiff.DeepDiff(person.sheets_compare(),p)
                if p['PersonID'] == '1107': print(diff,person.sheets_compare(),p)
                if bool(diff):
                    changed = {}
                    for diff_type in ['values_changed','type_changes']:
                        if diff_type in diff:
                            for val in diff[diff_type]: 
                                if diff[diff_type][val]['new_value'] != '#REF!':
                                    changed[val[6:-2]] = diff[diff_type][val]['new_value']
                    if bool(changed): Persons.update(changed).where(Persons.PersonID == person.PersonID).execute()

def validate_schedules(schedules):
    ref_sched = []
    for sched in schedules:
        if sched['Game_No'] == 80102: ref_sched.append(sched)
    try:
        assert len(ref_sched) == 1
        assert ref_sched[0]['Game_ID'] == 'PORGHG1'
        return(schedules)
    except AssertionError:
        return(None)

@sleep_dec
def update_schedules():
    int_list = ['Session','Game_No','Total_Plays','H_Score','A_Score']
    flt_list = ['Duration','Plays_Per_Day']
    schedules = []
    schedules_data = schedules_sh.get_all_values(include_tailing_empty_rows=False)
    for s in schedules_data:
        schedule = dict(zip(schedules_keys,s))
        if schedule['Session'] != 'Session':
            if int(schedule['Session']) != 0 and int(schedule['Session']) < 18:
                for cat in schedule:
                    if schedule[cat] == '': schedule[cat] = None
                    elif cat in int_list: schedule[cat] = int(schedule[cat])
                    elif cat in flt_list: schedule[cat] = float(schedule[cat])
                schedules.append(schedule)
    schedules = validate_schedules(schedules)
    if schedules:
        for s in schedules:
            sched = Schedules.get(Schedules.Game_No == s['Game_No'])
            diff = deepdiff.DeepDiff(sched.sheets_compare(),s)
            if bool(diff):
                changed = {}
                for diff_type in ['values_changed','type_changes']:
                    if diff_type in diff:
                        for val in diff[diff_type]: 
                            if diff[diff_type][val]['new_value'] != '#REF!':
                                changed[val[6:-2]] = diff[diff_type][val]['new_value']
                if bool(changed): Schedules.update(changed).where(Schedules.Game_No == sched.Game_No).execute()

def validate_teams(teams):
    ref_team = []
    for team in teams:
        if team['TID'] == 'T2001': ref_team.append(team)
    try:
        assert len(ref_team) == 1
        assert ref_team[0]['Abbr'] == 'POR'
        return(teams)
    except AssertionError:
        return(None)

@sleep_dec
def update_teams():
    teams = []
    teams_data = teams_sh.get_all_values(include_tailing_empty_rows=False)
    for t in teams_data:
        print(t)
        team = dict(zip(teams_keys,t))
        teams.append(team)
    teams.pop(0)
    teams = validate_teams(teams)
    print(teams)
    if teams:
        for t in teams: 
            team = Teams.get(Teams.TID == t['TID'])
            diff = deepdiff.DeepDiff(team.sheets_compare(),t)
            if bool(diff):
                changed = {}
                for val in diff['values_changed']: changed[val[6:-2]] = diff['values_changed'][val]['new_value']
                print(val,changed)
                Teams.update(changed).where(Teams.TID == team.TID).execute()

class lineupCard():
    def __init__(self,num):
        self.num = int(num)
        self.get_lineups()
    def get_lineups(self):
        self.Umpire = None
        self.Game_ID = None
        self.Away = None
        self.Home = None
        start = "C" + str(((self.num - 1) * 43) + 1)
        end = "J" + str(self.num * 43)
        self.whole_card = lineups_sh.get_values(start=start, end=end, include_tailing_empty_rows=True)
        self.Umpire = self.whole_card[0][0]
        self.Game_ID = self.whole_card[2][2]
        self.Away = self.whole_card[2][7]
        self.Home = self.whole_card[3][7]
        self.Game = Schedules.get_or_none(Schedules.Game_ID == self.Game_ID)
        if self.Game == None:
            self.Away_Lineup = None
            self.Home_Lineup = None
            return
        self.Game_No = self.Game.Game_No
        self.Away_Lineup = []
        self.Home_Lineup = []
        for i in self.whole_card[7:23]:
            if i[0] != '':
                entry = lineupEntry(i,self.Game_No,self.Away)
                self.Away_Lineup.append(entry)
        for i in self.whole_card[26:42]:
            if i[0] != '':
                entry = lineupEntry(i,self.Game_No,self.Home)
                self.Home_Lineup.append(entry)

class lineupEntry():
    def __init__(self,line,game_no,team):
        self.game_no = game_no
        self.team = team
        self.name = line[0]
        self.player_id = Persons.get_or_none(Persons.Stats_Name == self.name)
        if self.player_id != None: self.player_id = self.player_id.PersonID
        self.pos = self.conv_none(line[4])
        self.play = self.conv_none_int(line[5])
        self.bat = self.conv_none_int(line[6])
        self.pit = self.conv_none_int(line[7])
    def conv_none(self,data):
        if data == '':
            return(None)
        else:
            return(data)
    def conv_none_int(self,data):
        if data == '':
            return(None)
        else:
            return(int(data))

@sleep_dec
def update_meta():
    home_arr = home_sh.get_values(start='B1',end='B2',include_tailing_empty_rows=False)
    meta = {'Current_Season':int(home_arr[0][0]), 'Current_Session':int(home_arr[1][0])}
    if type(meta['Current_Season']) == int and type(meta['Current_Session']) == int:
        with db.atomic():
            entry = Metadata.get_by_id(1)
            entry.Current_Season = meta['Current_Season']
            entry.Current_Session = meta['Current_Session']
            entry.save()


@sleep_dec
def update_lineups():
    cards = {}
    home_arr = home_sh.get_values(start='A5',end='D12',include_tailing_empty_rows=False)
    for i in range(len(home_arr)):
        if home_arr[i][0] != '':
            cards[i+1] = lineupCard(i+1)
            [ update_entry(line) for line in cards[i+1].Away_Lineup if line_check(line) ]
            [ update_entry(line) for line in cards[i+1].Home_Lineup if line_check(line) ]

def line_check(line):
    if (line.name != '' and 
        line.pos != '' and
        line.play != '' and
        ((line.pos != 'P' and line.bat != '') or 
         (line.pos=='P' and line.pit != ''))):
        return(True)
    else: return(False)

def update_entry(line):
    entry = Lineups.get_or_none(Lineups.Player == line.player_id, Lineups.Game_No == line.game_no)
    z_entry = dict(zip(lineups_keys,[line.game_no,line.team,line.player_id,line.play,line.pos,line.bat,line.pit]))
    if not entry:
        Lineups.insert(z_entry).execute()
    else:
        diff = deepdiff.DeepDiff(entry.sheets_compare(),z_entry)
        if bool(diff):
            changed = {}
            for diff_type in ['values_changed','type_changes']:
                if diff_type in diff:
                    for val in diff[diff_type]: changed[val[6:-2]] = diff[diff_type][val]['new_value']
            Lineups.update(changed).where(Lineups.Player == line.player_id, Lineups.Game_No == line.game_no).execute()

def main():
    access_sheets()
   # generate_db()
    loop = asyncio.get_event_loop()
    cors = asyncio.wait([update_persons(60*60),update_schedules(60*5),update_teams(60*60),update_pas(60*5),update_lineups(60*5),update_meta(60*60)])
    loop.run_until_complete(cors)

if __name__ == "__main__":
    main()
