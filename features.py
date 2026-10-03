from pathlib import Path

import numpy as np
import pandas as pd

# ---- shared vocabulary (the bbb files' line/length vocab is the target; odata is mapped onto it) ----
LINES = ['WIDE_OUTSIDE_OFFSTUMP', 'OUTSIDE_OFFSTUMP', 'ON_THE_STUMPS', 'DOWN_LEG', 'WIDE_DOWN_LEG']
LENGTHS = ['YORKER', 'FULL_TOSS', 'FULL', 'GOOD_LENGTH', 'SHORT_OF_A_GOOD_LENGTH', 'SHORT']
FORMATS = ['T20', 'ODI', 'Test']
MAX_BALLS = {'T20': 120, 'ODI': 300}
# the two sources tag differently (odata calls 68% of balls "length ball"), so source is a feature.
# At predict time use the source that has the most data for that format.
SOURCE_FOR_FORMAT = {'T20': 'odata', 'ODI': 'bbb', 'Test': 'bbb'}

# bbb: 25 raw labels -> 15 shot groups. Unlisted labels become NaN and are dropped from training.
SHOT_MAP = {
    'DEFENDED': 'defend', 'PUSH': 'defend',
    'LEFT_ALONE': 'leave',
    'COVER_DRIVE': 'cover_drive', 'ON_DRIVE': 'on_drive',
    'STRAIGHT_DRIVE': 'straight_drive', 'SQUARE_DRIVE': 'square_drive',
    'FLICK': 'flick', 'LEG_GLANCE': 'leg_glance',
    'CUT_SHOT': 'cut', 'LATE_CUT': 'cut', 'UPPER_CUT': 'cut',
    'STEERED': 'steer_dab', 'DAB': 'steer_dab',
    'PULL': 'pull_hook', 'HOOK': 'pull_hook',
    'SWEEP_SHOT': 'sweep', 'PADDLE_SWEEP': 'sweep', 'SLOG_SWEEP': 'sweep',
    'REVERSE_SWEEP': 'reverse_sweep', 'REVERSE_PULL': 'reverse_sweep', 'REVERSE_SCOOP': 'reverse_sweep',
    'RAMP': 'ramp_scoop', 'PADDLE_AWAY': 'ramp_scoop',
    'SLOG_SHOT': 'slog',
}
BBB_BOWL = {'RF': 'right-arm fast', 'RFM': 'right-arm fast', 'RMF': 'right-arm fast', 'RM': 'right-arm medium',
            'LF': 'left-arm fast', 'LFM': 'left-arm fast', 'LMF': 'left-arm fast', 'LM': 'left-arm medium',
            'OB': 'off spin', 'LB': 'leg spin', 'LBG': 'leg spin', 'SLA': 'left-arm orthodox', 'LS': 'left-arm orthodox',
            'LWS': 'left-arm wrist spin'}

# odata -> shared vocab
O_LINE = {'wide outside off': 'WIDE_OUTSIDE_OFFSTUMP', 'outside off': 'OUTSIDE_OFFSTUMP', 'off': 'ON_THE_STUMPS',
          'middle': 'ON_THE_STUMPS', 'leg': 'ON_THE_STUMPS', 'down leg': 'DOWN_LEG'}
O_LENGTH = {'yorker': 'YORKER', 'full toss': 'FULL_TOSS', 'half volley': 'FULL', 'length ball': 'GOOD_LENGTH',
            'back of a length': 'SHORT_OF_A_GOOD_LENGTH', 'short': 'SHORT', 'bouncer': 'SHORT'}
O_SHOT = {'defending': 'defend', 'pushing': 'defend', 'fended': 'defend', 'dropped': 'defend',
          'leave': 'leave', 'padded': 'leave', 'cutting': 'cut', 'pulling': 'pull_hook', 'hooking': 'pull_hook',
          'flick': 'flick', 'glancing': 'leg_glance', 'steer': 'steer_dab', 'slog': 'slog',
          'sweeping': 'sweep', 'scoop': 'ramp_scoop'}  # driving/working are split by fielding area below
O_FORMAT = {'ODI': 'ODI', 'Test': 'Test', 'T20 International': 'T20', 'T20 Domestic': 'T20'}  # domestic 50-over/FC have no line data
# scoring zones, relative to the batter (cover is cover for a left-hander too). Order = drawing order.
ZONES = ['third_man', 'point', 'cover', 'mid_off', 'mid_on', 'mid_wicket', 'square_leg', 'fine_leg']
# bbb wagonZone is fixed to the ground: 1..8 run fine leg -> third man for a right-hander, mirrored for a left-hander
BBB_ZONE = {'RHB': dict(zip(range(1, 9), ZONES[::-1])), 'LHB': dict(zip(range(1, 9), ZONES))}
O_ZONE = {'cover': 'cover', 'point': 'point', 'gully': 'point', 'third man': 'third_man', 'slip': 'third_man',
          'mid off': 'mid_off', 'long off': 'mid_off', 'mid on': 'mid_on', 'long on': 'mid_on',
          'mid wicket': 'mid_wicket', 'square leg': 'square_leg', 'short leg': 'square_leg', 'fine leg': 'fine_leg'}
SQUARE_OFF = {'point', 'third man', 'slip', 'gully'}
OFF_SIDE = SQUARE_OFF | {'cover', 'mid off', 'long off'}

PREV = [f'p{k}_{c}' for k in range(1, 6) for c in ('line', 'length', 'shot', 'score')]
CAT = ['format', 'source', 'bat', 'bat_hand', 'bowl_style', 'variation', 'line', 'length', 'phase', 'ground', 'daynight'] \
      + [c for c in PREV if not c.endswith('score')]
NUM = ['over', 'ball_no', 'bat_bf', 'bat_runs', 'inns', 'runs', 'wkts', 'balls', 'balls_rem', 'rr', 'rrr'] \
      + [c for c in PREV if c.endswith('score')]
FEATURES = CAT + NUM
# zone / bat_run / bowl_run / bat_out are outcomes (scoring diagrams, runs + wicket models), never model features
KEEP = list(dict.fromkeys(['p_match', 'date', 'inns', 'over', 'shot', 'teams', 'target', 'zone', 'bat_run', 'bowl_run', 'bat_out'] + [c for c in FEATURES if c not in ('phase', 'rr', 'rrr')]))

BBB_COLS = ['p_match', 'inns', 'over', 'ball', 'date', 'bat', 'bat_hand', 'bowl_style', 'line', 'length', 'shot',
            'score', 'out', 'wide', 'noball', 'ballfaced', 'batruns', 'cur_bat_bf', 'cur_bat_runs', 'team_bat', 'team_bowl',
            'inns_runs', 'inns_wkts', 'inns_balls', 'max_balls', 'target', 'ground', 'daynight', 'wagonZone', 'dismissal', 'bowlruns']
# dismissals the bowler earns (run-outs excluded); all of these dismiss the striker
BBB_OUT = {'caught', 'bowled', 'leg before wicket', 'stumped', 'hit wicket'}
O_OUT = {'Caught', 'CaughtAndBowled', 'CaughtSub', 'Bowled', 'Lbw', 'Stumped', 'HitWicket'}
# bowling-plan phases (same boundaries as the 'phase' feature in build_features)
PHASES = {'T20': [('powerplay', 1, 6), ('middle', 7, 15), ('death', 16, 20)],
          'ODI': [('powerplay', 1, 10), ('middle', 11, 40), ('death', 41, 50)]}


def teams_key(a, b):
    return np.where(a.astype(str) < b.astype(str), a.astype(str) + '|' + b.astype(str), b.astype(str) + '|' + a.astype(str))


def add_prev(df, keys):
    g = df.groupby(keys, sort=False)
    df['ball_no'] = g.cumcount() + 1
    for k in range(1, 6):
        for c in ('line', 'length', 'shot', 'score'):
            df[f'p{k}_{c}'] = g[c].shift(k)
    return df


def load_bbb(path, fmt, log):
    """Cricinfo-style ball-by-ball file (odi_bbb / test_bbb). Running totals include the current ball -> subtract it."""
    raw = pd.read_csv(path, low_memory=False)
    n = len(raw)
    raw = raw.drop(columns=raw.columns[0]).drop_duplicates()  # first column is a row index, not data
    log(f'{Path(path).name}: {n:,} rows, dropped {n - len(raw):,} exact duplicates')
    df = raw[[c for c in BBB_COLS if c in raw]].copy()
    blank = df.bat.isna().sum()
    if blank:  # placeholder rows (only match/over/ball filled): kept as gaps in the over, never trained on
        log(f'  {blank:,} blank placeholder deliveries kept as unknown balls')
    assert not df.duplicated(['p_match', 'inns', 'over', 'ball']).any(), f'{path}: conflicting rows for the same delivery'
    df = df.sort_values(['p_match', 'inns', 'over', 'ball'], kind='stable').reset_index(drop=True)  # file is grouped by batter
    df['format'], df['source'] = fmt, 'bbb'
    df['shot'] = df.shot.map(SHOT_MAP)
    df['bowl_style'] = df.bowl_style.str.split('/').str[0].map(BBB_BOWL)
    df['variation'] = np.nan
    df['ground'] = df.ground.str.split(',').str[0].str.strip()
    df['teams'] = teams_key(df.team_bat, df.team_bowl)
    legal = ((df.wide == 0) & (df.noball == 0)).astype(int)
    df['bat_bf'] = df.cur_bat_bf - df.ballfaced
    df['bat_runs'] = df.cur_bat_runs - df.batruns
    df['runs'] = df.inns_runs - df.score
    df['wkts'] = df.inns_wkts - (df.out == True).astype(int)
    df['balls'] = df.inns_balls - legal
    df['balls_rem'] = (df.max_balls if 'max_balls' in df else np.nan) - df.balls
    df['zone'] = [BBB_ZONE.get(h, {}).get(z) for h, z in zip(df.bat_hand, df.wagonZone)]
    df['bat_run'] = df.batruns.clip(lower=0)  # 50 scorer corrections are negative
    df['bat_out'] = df.dismissal.isin(BBB_OUT).astype(int)
    df['bowl_run'] = df.bowlruns.clip(lower=0)  # batter runs + wides + no-balls (byes/leg byes aren't the bowler's)
    df['p_match'] = 'b' + df.p_match.astype(int).astype(str)
    df['date'] = pd.to_datetime(df.date)
    if 'daynight' not in df:
        df['daynight'] = np.nan
    return add_prev(df, ['p_match', 'inns', 'over'])[KEEP]


def load_odata(path, bbb, log):
    """Commentary-derived file covering T20/ODI/Test. Match state is rebuilt from cumulative sums.
    Matches already in the bbb files are dropped (bbb has exact match state)."""
    cols = ['fixtureId', 'team1', 'team2', 'matchDate', 'timestamp', 'format', 'ground', 'inns', 'batsman', 'bowler',
            'batsmanHand', 'bowlerHand', 'bowlerType', 'over', 'ball', 'runs', 'runs_scored', 'extras', 'is_wicket',
            'commentary', 'shot', 'shot_type', 'area', 'line', 'length', 'variation', 'dismissalType', 'runs_conceded']
    o = pd.read_csv(path, low_memory=False, usecols=cols)
    n = len(o)
    o = o.drop_duplicates()
    log(f'{Path(path).name}: {n:,} rows, dropped {n - len(o):,} exact duplicates')
    o = o[o.format.isin(O_FORMAT)].copy()
    o['format'] = o.format.map(O_FORMAT)
    d = pd.to_datetime(o.matchDate.str[:10], errors='coerce').fillna(pd.to_datetime(o.timestamp.str[:10], errors='coerce'))
    o['date'] = d.groupby(o.fixtureId).transform('min')  # Test matchDate is the day of play; use match start
    o['teams'] = teams_key(o.team1, o.team2)
    log(f'  kept formats with line data: {len(o):,} rows; dropping {o.date.isna().sum():,} undated rows (cannot dedupe or time-split)')
    o = o[o.date.notna()]

    # cross-file duplicates: same teams + format, start date within a small window of a bbb match
    fx = o.groupby('fixtureId').agg(date=('date', 'first'), teams=('teams', 'first'), format=('format', 'first')).reset_index()
    bm = bbb.groupby('p_match').agg(date=('date', 'first'), teams=('teams', 'first'), format=('format', 'first'))
    x = fx.merge(bm, on=['teams', 'format'], suffixes=('', '_b'))
    gap = (x.date - x.date_b).dt.days
    lo, hi = -1, np.where(x.format == 'Test', 5, 1)  # timezone slop; Test odata dates can be days 1-5
    dup = set(x.fixtureId[(gap >= lo) & (gap <= hi)])
    log(f'  dropping {len(dup):,} fixtures already in the bbb files ({o.fixtureId.isin(dup).sum():,} rows)')
    o = o[~o.fixtureId.isin(dup)]

    # innings with missing overs would give wrong running totals
    g = o.groupby(['fixtureId', 'inns']).over
    ok = (g.transform('min') == 1) & (g.transform('nunique') == g.transform('max'))
    log(f'  dropping {(~ok).sum():,} rows from innings with missing overs')
    o = o[ok].sort_values(['fixtureId', 'inns', 'over', 'ball', 'timestamp'], kind='stable').reset_index(drop=True)

    wide = o.commentary.str.contains(r'^(?:[A-Z]+! )?Wide\b', na=False)
    noball = o.commentary.str.contains(r'^(?:[A-Z]+! )?No ball\b', na=False)
    legal = (~wide & ~noball).astype(int)
    o['score'] = o.runs
    bat_r = o.runs_scored.fillna(o.runs - o.extras)
    inn = o.groupby(['fixtureId', 'inns'])
    o['runs'] = inn.score.cumsum() - o.score
    o['wkts'] = inn.is_wicket.cumsum() - o.is_wicket
    o['balls'] = legal.groupby([o.fixtureId, o.inns]).cumsum() - legal
    faced = (~wide).astype(int)
    bat = [o.fixtureId, o.inns, o.batsman]
    o['bat_bf'] = faced.groupby(bat).cumsum() - faced
    o['bat_runs'] = bat_r.groupby(bat).cumsum() - bat_r
    first = o[o.inns == 1].groupby('fixtureId').score.sum()
    o['balls_rem'] = o.format.map(MAX_BALLS) - o.balls

    st, area = o.shot_type, o.area
    rev = o.shot.str.contains('reverse', case=False, na=False)
    offline = o.line.isin(['outside off', 'wide outside off'])
    drive = np.select([area == 'back to bowler', area.isin(SQUARE_OFF), area.isin(OFF_SIDE),
                       area.isin(['mid on', 'long on', 'mid wicket', 'square leg', 'fine leg', 'short leg'])],
                      ['straight_drive', 'square_drive', 'cover_drive', 'on_drive'],
                      np.where(offline, 'cover_drive', 'on_drive'))
    o['shot'] = np.select([st == 'driving', st == 'working', rev & st.isin(['sweeping', 'scoop'])],
                          [drive, np.where(area.isin(OFF_SIDE), 'steer_dab', 'flick'), 'reverse_sweep'],
                          st.map(O_SHOT).astype(object))
    o['shot'] = o.shot.replace('nan', np.nan)
    o['line'] = o.line.map(O_LINE)
    o['length'] = o.length.map(O_LENGTH)

    hand = o.bowlerHand.str.lower().map({'right': 'right-arm', 'left': 'left-arm'})
    bt = o.bowlerType
    o['bowl_style'] = np.select(
        [bt.isin(['Fast Seam', 'Fast Medium', 'Medium Fast']), bt == 'Medium', bt == 'Off Spin',
         bt.isin(['Leg Spin', 'Leg break', 'Unorthodox']) & (hand == 'left-arm'), bt.isin(['Leg Spin', 'Leg break', 'Unorthodox']),
         (bt == 'Orthodox') & (hand == 'left-arm'), bt == 'Orthodox'],
        [hand + ' fast', hand + ' medium', 'off spin', 'left-arm wrist spin', 'leg spin', 'left-arm orthodox', 'off spin'],
        None)
    o = o.rename(columns={'batsman': 'bat'})
    o['bat_hand'] = o.batsmanHand.map({'Right': 'RHB', 'Left': 'LHB'})
    o['ground'] = o.ground.str.split(',').str[0].str.strip()
    o['source'], o['daynight'] = 'odata', np.nan
    o['target'] = np.where((o.inns == 2) & o.format.isin(MAX_BALLS), o.fixtureId.map(first) + 1, np.nan)
    o['zone'] = o.area.map(O_ZONE)
    o['bat_run'] = bat_r
    o['bat_out'] = o.dismissalType.isin(O_OUT).astype(int)
    o['bowl_run'] = o.runs_conceded.fillna(bat_r + np.where(wide | noball, o.extras, 0)).clip(lower=0)
    o['p_match'] = 'o' + o.fixtureId.astype(str)
    o = add_prev(o, ['fixtureId', 'inns', 'over'])
    return o[KEEP]


def load_all(data_dir, log=print):
    data_dir = Path(data_dir)
    odi = load_bbb(data_dir / 'odi_bbb-25.csv', 'ODI', log)
    test = load_bbb(data_dir / 'test_bbb - 25.csv', 'Test', log)
    bbb = pd.concat([odi, test], ignore_index=True)
    odata = load_odata(data_dir / 'odata_full.csv', bbb, log)
    return pd.concat([bbb, odata], ignore_index=True)


def build_features(df):
    """Shared by train and serve. Expects the pre-ball columns produced by the loaders (or app.py)."""
    df = df.copy()
    df['phase'] = np.select([df.format == 'Test', df.over <= np.where(df.format == 'T20', 6, 10),
                             df.over > np.where(df.format == 'T20', 15, 40)],
                            ['test', 'powerplay', 'death'], 'middle')
    df['rr'] = np.where(df.balls > 0, df.runs * 6 / df.balls.clip(lower=1), 0.0)
    chase = (df.inns == 2) & df.format.isin(MAX_BALLS) & df.target.notna() & (df.balls_rem > 0)
    df['rrr'] = np.where(chase, (df.target - df.runs) * 6 / df.balls_rem.clip(lower=1), np.nan)
    for c in CAT:
        df[c] = df[c].astype('category')
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df[FEATURES]


def serve_row(format, batter, bat_hand, bowl_style, line, length, over, prev=(), bat_bf=0, bat_runs=0, inns=1,
              runs=0, wkts=0, target=None, variation=None, ground=None, daynight=None):
    """One prediction row in the loaders' pre-ball layout. Used by the app and the bowling plan.
    prev = earlier balls this over (oldest first) as dicts with line/length/shot/runs."""
    source = SOURCE_FOR_FORMAT[format]
    # the ODI/Test data has no variation column, so a variation there would be a combination never seen in training
    variation = (variation or 'stock') if source == 'odata' else None
    max_balls = MAX_BALLS.get(format)
    prev = list(prev)
    balls = (over - 1) * 6 + len(prev)  # ponytail: assumes earlier balls this over were legal
    row = dict(format=format, source=source, bat=batter, bat_hand=bat_hand, bowl_style=bowl_style, variation=variation,
               line=line, length=length, over=over, ball_no=len(prev) + 1, bat_bf=bat_bf, bat_runs=bat_runs, inns=inns,
               runs=runs, wkts=wkts, balls=balls, balls_rem=max_balls - balls if max_balls else None,
               target=target if inns == 2 else None, ground=ground, daynight=daynight)
    for k in range(1, 6):  # p1 = most recent ball
        p = prev[-k] if k <= len(prev) else {}
        row.update({f'p{k}_line': p.get('line'), f'p{k}_length': p.get('length'), f'p{k}_shot': p.get('shot'),
                    f'p{k}_score': p.get('runs')})
    return row


def recency_weight(dates, half_life_years, ref=None):
    """Weight per ball: 1 for the newest, halving every half_life_years. None/0 -> every ball counts the same."""
    dates = pd.to_datetime(pd.Series(dates))
    if not half_life_years:
        return np.ones(len(dates))
    ref = dates.max() if ref is None else pd.Timestamp(ref)
    return 0.5 ** ((ref - dates).dt.days.to_numpy() / 365.25 / half_life_years)
