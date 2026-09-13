import duckdb
c=duckdb.connect('/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb',read_only=True)
c.execute("ATTACH '/Users/mariaaleu/pmw-catalog-v2/CATALOG_V2.duckdb' AS cat (READ_ONLY)")
c.execute("create temp table ev as select * from read_csv_auto('/Users/mariaaleu/.claude/jobs/43deec01/tmp/disc60/ev.csv', all_varchar=true)")
c.execute("""create temp table pm as select m.event_id, p.market_id, min(p.fetched_at) f from price_history p join markets m using(market_id) group by all""")
print("-- reproduce counts")
for e in ('693904','321062','251729','341797'):
    print(e, c.execute(f"""select (select count(*) from cat.mk where cast(event_id as varchar)='{e}'),
      (select count(*) from markets where event_id='{e}'),
      (select count(*) from outcomes o join markets m using(market_id) where m.event_id='{e}' and o.outcome_label='Yes'),
      (select count(distinct p.market_id) from price_history p join markets m using(market_id) where m.event_id='{e}')""").fetchone())
print("-- fetch time windows by class (n_store) ")
print(c.sql("""select ev.n_store, date_trunc('hour', pm.f) h, count(distinct pm.event_id) evs, count(*) mk, min(ev.d) dmin, max(ev.d) dmax
  from pm join ev on ev.event_id=pm.event_id group by all order by h""").show(max_rows=200))
