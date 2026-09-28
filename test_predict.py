from app import Ball, predict

base = dict(format='ODI', batter='Virat Kohli', bowl_style='right-arm fast', over=20, balls_faced=30, bat_runs=25, runs=110, wkts=2)

short = predict(Ball(**base, line='ON_THE_STUMPS', length='SHORT'))['shots']
assert abs(sum(short.values()) - 100) < 1, short
assert short['pull_hook'] > short['cover_drive'], short

full = predict(Ball(**base, line='OUTSIDE_OFFSTUMP', length='FULL'))['shots']
assert full['cover_drive'] > full['pull_hook'], full

wide = predict(Ball(**base, line='WIDE_OUTSIDE_OFFSTUMP', length='GOOD_LENGTH'))['shots']
assert wide['cut'] > wide['flick'], wide  # wide outside off -> off-side shots

# format matters: same ball, T20 death over vs Test morning
ball = dict(batter='Virat Kohli', bowl_style='right-arm fast', line='OUTSIDE_OFFSTUMP', length='GOOD_LENGTH', balls_faced=30, bat_runs=40)
t20 = predict(Ball(**ball, format='T20', over=19, runs=160, wkts=4))['shots']
test = predict(Ball(**ball, format='Test', over=19, runs=50, wkts=1))['shots']
assert t20['slog'] > test['slog'] and test['leave'] > t20['leave'], (t20, test)

unknown = predict(Ball(**{**base, 'batter': 'Nobody McNoname'}, line='ON_THE_STUMPS', length='GOOD_LENGTH'))
assert unknown['batter_known'] is False

print('ok')
