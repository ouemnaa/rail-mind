"""Quick Qdrant content analysis"""
import json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import numpy as np

QDRANT_URL = 'https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io'
QDRANT_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM'
ALGORITHM_COLLECTION = 'railway_algorithms'
HISTORICAL_COLLECTION = 'rail_incidents'

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Get all algorithms and group by type
print('='*70)
print('  ALGORITHM KNOWLEDGE BASE - CONFLICT TYPES')
print('='*70)

algos, _ = client.scroll(collection_name=ALGORITHM_COLLECTION, limit=100, with_payload=True)

by_type = {}
for a in algos:
    ctype = a.payload.get('conflict_type', 'Unknown')
    if ctype not in by_type:
        by_type[ctype] = []
    by_type[ctype].append(a.payload)

print(f'\nTotal: {len(algos)} entries across {len(by_type)} conflict types\n')

for ctype, entries in sorted(by_type.items()):
    print(f'📌 {ctype} ({len(entries)} entries)')
    for e in entries[:2]:
        res = e.get('resolution_strategy', 'N/A')[:70]
        print(f'   - {res}...')
    print()

# Historical incident types
print('='*70)
print('  HISTORICAL INCIDENTS - INCIDENT TYPES')
print('='*70)

incidents, _ = client.scroll(collection_name=HISTORICAL_COLLECTION, limit=200, with_payload=True)

inc_types = {}
for inc in incidents:
    itype = inc.payload.get('incident_type', 'Unknown')
    inc_types[itype] = inc_types.get(itype, 0) + 1

print(f'\nTotal: {len(incidents)} incidents\n')
for t, count in sorted(inc_types.items(), key=lambda x: -x[1]):
    bar = '#' * (count // 2)
    print(f'  {t:30s} {count:3d} {bar}')

# Test searches
print('\n' + '='*70)
print('  SEARCH TESTS')
print('='*70)

embedder = SentenceTransformer('all-MiniLM-L6-v2')

test_queries = [
    ('Headway violation', 'headway_violation train entered 50s after previous train minimum 180s'),
    ('Platform congestion', 'platform_congestion 5 trains requesting same platform'),
    ('Track fault/defect', 'track fault defect damage rail infrastructure'),
    ('Edge overflow', 'edge_overflow 4 trains single track segment capacity exceeded'),
]

for name, query in test_queries:
    print(f'\n🔍 TEST: {name}')
    print(f'   Query: "{query[:50]}..."')
    
    vec = embedder.encode(query).tolist()
    results = client.query_points(
        collection_name=ALGORITHM_COLLECTION,
        query=vec,
        limit=3,
        with_payload=True
    )
    
    if results.points:
        print(f'   Top 3 results:')
        for i, p in enumerate(results.points, 1):
            ctype = p.payload.get('conflict_type', 'N/A')
            print(f'   {i}. Score: {p.score:.3f} | Type: {ctype}')
    else:
        print('   No results!')
