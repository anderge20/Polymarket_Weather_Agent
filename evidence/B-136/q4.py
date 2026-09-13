import duckdb
c=duckdb.connect('/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb',read_only=True)
c.execute("""create temp table evb as
select m.event_id, any_value(m.station_identifier) st, strftime(min(m.end_date),'%Y-%m') mo, count(distinct m.market_id) n,
  bool_or(o.lo is null and o.hi is not null) has_below, bool_or(o.hi is null and o.lo is not null) has_higher,
  bool_or(o.band_label ilike '%below%' or o.band_label ilike '%lower%') lbl_below, bool_or(o.band_label ilike '%higher%' or o.band_label ilike '%above%') lbl_higher
from markets m join outcomes o on o.market_id=m.market_id and o.outcome_label='Yes' group by m.event_id""")
print(c.sql("select count(*) events, sum((has_below and not has_higher)::int) open_top, sum((has_below and has_higher)::int) closed_both, sum((not has_below)::int) no_below, sum((lbl_below and not lbl_higher)::int) open_top_by_label from evb"))
print(c.sql("select st, count(*) events, sum((has_below and not has_higher)::int) open_top, round(100.0*sum((has_below and not has_higher)::int)/count(*),1) pct from evb group by 1 order by 3 desc").show(max_rows=100))
print(c.sql("select mo, count(*) events, sum((has_below and not has_higher)::int) open_top, round(100.0*sum((has_below and not has_higher)::int)/count(*),1) pct from evb group by 1 order by 1"))
print(c.sql("select n, count(*) from evb group by 1 order by 1"))
