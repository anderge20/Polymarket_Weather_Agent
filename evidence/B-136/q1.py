import duckdb
c=duckdb.connect('/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb',read_only=True)
print([r[0] for r in c.execute('describe markets').fetchall()])
print(c.sql("select dataset_version, source, count(*) from markets group by all"))
print(c.sql("describe price_history"))
print(c.sql("describe outcomes"))
for ev in ('321062','341797','251729','693904'):
    print('EVENT',ev)
    print(c.sql(f"""select m.market_id, o.band_label, o.lo, o.hi, m.uma_resolution_status, m.winning_outcome, m.dataset_version, m.close_time, m.end_date, m.fees_enabled,
      (select count(*) from price_history p where p.market_id=m.market_id) n_ph
      from markets m left join outcomes o on o.market_id=m.market_id and o.outcome_label='Yes' where m.event_id='{ev}' order by o.lo nulls first, o.hi"""))
