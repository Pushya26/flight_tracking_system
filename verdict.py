import urllib.request, json, time, datetime

results = []
for i in range(4):
    r = urllib.request.urlopen('http://localhost:8002/flights/')
    d = json.loads(r.read())
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    results.append((ts, d))
    print(f'[{ts}] snap {i+1}: {len(d)} aircraft', flush=True)
    if i < 3:
        time.sleep(10)

s = [set(a['icao24'] for a in r[1]) for r in results]
counts = [len(r[1]) for r in results]

print()
print('=== FINAL VERDICT ===')
print(f'Snapshots         : {counts}')
print(f'Min / Max         : {min(counts)} / {max(counts)}')
print(f'New aircraft s1->s4  : +{len(s[3]-s[0])}')
print(f'Gone aircraft s1->s4 : -{len(s[0]-s[3])}')
print(f'Stable in all 4 snaps: {len(s[0]&s[1]&s[2]&s[3])}')
print(f'Est. updates/sec  : ~{max(counts)//10} state writes/sec per poll')
