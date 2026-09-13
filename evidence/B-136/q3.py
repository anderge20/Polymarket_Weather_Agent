import duckdb
c=duckdb.connect('/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb',read_only=True)
c.execute("ATTACH '/Users/mariaaleu/pmw-catalog-v2/CATALOG_V2.duckdb' AS cat (READ_ONLY)")
print("-- price_history fetch times per market, 4 events")
print(c.sql("""select m.event_id, p.market_id, min(p.fetched_at) f0, max(p.fetched_at) f1, min(p.ingestion_timestamp) i0, count(*) n, any_value(p.source) src, any_value(p.fidelity) fid
  from price_history p join markets m using(market_id) where m.event_id in ('321062','341797','251729','693904') group by all order by 1,2""").show(max_rows=40))
print("-- market ingestion ts in markets for those events")
print(c.sql("""select event_id, min(ingestion_timestamp), max(ingestion_timestamp), min(discovered_at), count(*) from markets where event_id in ('321062','341797','251729','693904') group by 1"""))
# per event: stored count vs catalog count; is stored set == first-k by market_id in catalog; == first-k by lo
c.execute("""create temp table ev as
with catm as (select cast(event_id as varchar) event_id, cast(market_id as varchar) market_id, station_identifier, cast(endDate as date) d, lo, hi,
   row_number() over (partition by event_id order by cast(market_id as varchar)) rk_id,
   row_number() over (partition by event_id order by lo nulls first, hi) rk_lo from cat.mk),
stored as (select market_id from markets)
select c.event_id, any_value(c.station_identifier) st, min(c.d) d, count(*) n_cat, count(s.market_id) n_store,
  bool_and((s.market_id is not null) = (c.rk_id <= (select count(*) from markets m2 where m2.event_id=c.event_id))) prefix_by_id,
  bool_and((s.market_id is not null) = (c.rk_lo <= (select count(*) from markets m2 where m2.event_id=c.event_id))) prefix_by_lo
from catm c left join stored s using(market_id)
where c.event_id in (select distinct event_id from markets)
group by c.event_id""")
print("-- events in store: n_store vs n_cat")
print(c.sql("select (n_store=n_cat) complete, n_store, count(*) events, sum(prefix_by_id::int) prefix_id, sum(prefix_by_lo::int) prefix_lo from ev group by all order by 1,2").show(max_rows=40))
print(c.sql("select st, count(*) ev, sum((n_store<n_cat)::int) truncated, sum((n_store=n_cat)::int) complete from ev where st='EGLC' group by 1"))
print("-- truncated events per (station,date): how many events share the pair and stored per pair")
print(c.sql("""select n_ev_pair, stored_per_pair, count(*) pairs from (select st, d, count(*) n_ev_pair, sum(n_store) stored_per_pair from ev where n_store<n_cat group by 1,2) group by all order by 3 desc limit 15"""))
print("-- stored markets with no price_history?")
print(c.sql("select count(*) from markets m where not exists (select 1 from price_history p where p.market_id=m.market_id)"))
print("-- complete EGLC events vs weather_forecasts pairs; truncated EGLC events vs pairs")
print(c.sql("""select (n_store=n_cat) complete, exists(select 1 from weather_forecasts w where w.station=ev.st and cast(w.target_date as date)=ev.d and w.dataset_version='backfill_2b_v1') has_fc, count(*) from ev group by all order by 1,2"""))
print(c.sql("""select (n_store=n_cat) complete, strftime(d,'%Y-%m') mo, count(*) from ev where st='EGLC' group by all order by 2,1"""))
c.execute("copy ev to '/Users/mariaaleu/.claude/jobs/43deec01/tmp/disc60/ev.csv'")
