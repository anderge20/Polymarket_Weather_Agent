import duckdb
c=duckdb.connect('/Users/mariaaleu/pmw-catalog-v2/CATALOG_V2.duckdb',read_only=True)
print(c.sql('show tables'))
print([r[0] for r in c.execute('describe mk').fetchall()])
for ev in ('321062','341797'):
    print(c.sql(f"select market_id, group_item_title, lo, hi, umaResolutionStatus, closedTime, winning_outcome from mk where cast(event_id as varchar)='{ev}' order by lo nulls first"))
