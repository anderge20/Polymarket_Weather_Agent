"""
Real gamma /events fixtures for Phase 2B tests (verbatim, verified live 2026-08-21).
Two events chosen to cover BOTH fee epochs + a disputed market + a US 4-segment
Wunderground URL:

  * NYC_EVENT   — 2025-12-30 (legacy): feeType=null, feesEnabled=false (fees_disabled),
                  Fahrenheit, station KLGA (URL .../us/ny/new-york-city/KLGA), legacy
                  'by the Forecast' measurement template; one WINNING band (32-33°F)
                  that was DISPUTED then resolved.
  * ANKARA_EVENT — 2026-08-20 (recent): feeType='weather_fees', feesEnabled=true,
                  Celsius, station LTAC (URL .../tr/%C3%A7ubuk/LTAC), 'Daily
                  Observations' measurement template, orderPriceMinTickSize=0.001,
                  orderMinSize=5, makerBaseFee/takerBaseFee=1000.

outcomes/outcomePrices/clobTokenIds are JSON-encoded strings, exactly as gamma
returns them. Token ids / conditionIds / timestamps are REAL.

R29 (end of file): five VERBATIM descriptions from CATALOG_V2.duckdb, one per
contract source / measurement rule (NOAA TempColumn + WU DailyObservations fallback,
NOAA HourlyData + fallback, HKO, CWA, WU generic). Description-only constants.
"""

_NYC_DESC = (
    "This market will resolve to the temperature range that contains the highest "
    "temperature recorded at the LaGuardia Airport Station in degrees Fahrenheit on "
    "30 Dec '25.\n\nThe resolution source for this market will be information from "
    "Wunderground, specifically the highest temperature recorded for all times on this "
    "day by the Forecast for the LaGuardia Airport Station once information is "
    "finalized, available here: "
    "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA.\n\nTo toggle "
    "between Fahrenheit and Celsius, click the gear icon next to the search bar and "
    "switch the Temperature setting between °F and °C.\n\nThis market can not resolve "
    "to \"Yes\" until all data for this date has been finalized.\n\nThe resolution "
    "source for this market measures temperatures to whole degrees Fahrenheit (eg, "
    "21°F). Thus, this is the level of precision that will be used when resolving the "
    "market.\n\nAny revisions to temperatures recorded after data is finalized for "
    "this market's timeframe will not be considered for this market's resolution."
)

_ANKARA_DESC = (
    "This market will resolve based on the highest temperature recorded in the 'Daily "
    "Observations' table on Weather Underground, not the figure displayed in the 'Day "
    "High & Low' summary section; in the event of any discrepancy between the two, the "
    "Daily Observations table shall be the primary resolution source not the Day High & "
    "Low section.\n\nThis market will resolve to the temperature range that contains the "
    "highest temperature recorded at the Esenboğa Intl Airport Station in degrees "
    "Celsius on 20 Aug '26.\n\nThe resolution source for this market will be information "
    "from Wunderground, specifically the highest temperature recorded for all times on "
    "this day for the Esenboğa Intl Airport Station, available here: "
    "https://www.wunderground.com/history/daily/tr/%C3%A7ubuk/LTAC.\n\nTo toggle between "
    "Fahrenheit and Celsius, click the gear icon next to the search bar and switch the "
    "Temperature setting between °F and °C.\n\nThis market can not resolve until the "
    "first data point for the following date has been published on the resolution "
    "source.\n\nThe resolution source for this market measures temperatures to whole "
    "degrees Celsius (eg, 9°C). Thus, this is the level of precision that will be used "
    "when resolving the market.\n\nRevisions to temperatures recorded within this "
    "market's timeframe will be considered until the first datapoint for the following "
    "date has been published, after which any alterations will not be considered."
)

# ---------------------------------------------------------------- NYC (legacy) ----
NYC_EVENT = {
    "id": "128661",
    "title": "Highest temperature in NYC on December 30?",
    "slug": "highest-temperature-in-nyc-on-december-30",
    "description": _NYC_DESC,
    "resolutionSource": "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA",
    "startDate": "2025-12-28T11:12:28.455294Z",
    "endDate": "2025-12-30T12:00:00Z",
    "createdAt": "2025-12-28T11:00:18.863842Z",
    "closedTime": "2025-12-31T09:12:59Z",
    "tags": [{"id": "104596", "label": "Highest temperature"},
             {"id": "84", "label": "Weather"},
             {"id": "100091", "label": "New York City"}],
    "markets": [
        {
            "id": "1046093",
            "question": "Will the highest temperature in New York City be 27°F or below on December 30?",
            "conditionId": "0x559d4137387516d29a166b6981abbcdab99082e63de2447e520130b6e9994a31",
            "slug": "highest-temperature-in-nyc-on-december-30-27forbelow",
            "resolutionSource": "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA",
            "description": _NYC_DESC,
            "groupItemTitle": "27°F or below",
            "outcomes": "[\"Yes\", \"No\"]",
            "outcomePrices": "[\"0\", \"1\"]",
            "clobTokenIds": "[\"20441148251188620401332586274218271173107693104488329501303237033232879814116\", \"109250546669331625374043040161588840269129722729886008162863754388700213531687\"]",
            "umaResolutionStatus": "resolved",
            "umaResolutionStatuses": "[\"proposed\", \"resolved\"]",
            "umaEndDate": "2025-12-30T09:09:31Z",
            "createdAt": "2025-12-28T11:00:18.867429Z",
            "startDate": "2025-12-28T11:12:03.843068Z",
            "endDate": "2025-12-30T12:00:00Z",
            "closedTime": "2025-12-30 09:09:31+00",
            "orderPriceMinTickSize": 0.001,
            "orderMinSize": 5,
            "feeType": None,
            "feesEnabled": False,
        },
        {
            "id": "1046096",
            "question": "Will the highest temperature in New York City be between 32-33°F on December 30?",
            "conditionId": "0x5b39af473532b8c9cfb73472b7067a9d89796e2e3748e4a82296cdc7b09f2470",
            "slug": "highest-temperature-in-nyc-on-december-30-32-33f",
            "resolutionSource": "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA",
            "description": _NYC_DESC,
            "groupItemTitle": "32-33°F",
            "outcomes": "[\"Yes\", \"No\"]",
            "outcomePrices": "[\"1\", \"0\"]",
            "clobTokenIds": "[\"30283956499373815182757413265134902761575330726851280632860378868487324027066\", \"75665634688417822977685110934578357202582747401124110886532152254563019809930\"]",
            "umaResolutionStatus": "resolved",
            "umaResolutionStatuses": "[\"proposed\", \"disputed\", \"proposed\", \"resolved\"]",
            "umaEndDate": "2025-12-31T09:10:57Z",
            "createdAt": "2025-12-28T11:00:18.892911Z",
            "startDate": "2025-12-28T11:12:05.369086Z",
            "endDate": "2025-12-30T12:00:00Z",
            "closedTime": "2025-12-31 09:10:57+00",
            "orderPriceMinTickSize": 0.001,
            "orderMinSize": 5,
            "feeType": None,
            "feesEnabled": False,
        },
        {
            "id": "1046099",
            "question": "Will the highest temperature in New York City be 38°F or higher on December 30?",
            "conditionId": "0xcd86c7d84201069e141229ddeb77e17b0198e15f80b6eccaa1f12c53f2d422ac",
            "slug": "highest-temperature-in-nyc-on-december-30-38forhigher",
            "resolutionSource": "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA",
            "description": _NYC_DESC,
            "groupItemTitle": "38°F or higher",
            "outcomes": "[\"Yes\", \"No\"]",
            "outcomePrices": "[\"0\", \"1\"]",
            "clobTokenIds": "[\"90130661173815591607810144834591924869368529936987129712947553629513961382507\", \"28588558680763166278030684746466987163158674160712851514386513772687048151710\"]",
            "umaResolutionStatus": "resolved",
            "umaResolutionStatuses": "[\"proposed\", \"resolved\"]",
            "umaEndDate": "2025-12-31T09:12:59Z",
            "createdAt": "2025-12-28T11:00:18.915487Z",
            "startDate": "2025-12-28T11:12:07.377858Z",
            "endDate": "2025-12-30T12:00:00Z",
            "closedTime": "2025-12-31 09:12:59+00",
            "orderPriceMinTickSize": 0.001,
            "orderMinSize": 5,
            "feeType": None,
            "feesEnabled": False,
        },
    ],
}

# ---------------------------------------------------------------- Ankara (recent) --
ANKARA_EVENT = {
    "id": "869074",
    "title": "Highest temperature in Ankara on August 20?",
    "slug": "highest-temperature-in-ankara-on-august-20-2026",
    "description": _ANKARA_DESC,
    "resolutionSource": "https://www.wunderground.com/history/daily/tr/%C3%A7ubuk/LTAC",
    "startDate": "2026-08-18T04:56:35Z",
    "endDate": "2026-08-20T12:00:00Z",
    "createdAt": "2026-08-18T04:56:14.394785Z",
    "closedTime": "2026-08-20T21:42:42Z",
    "tags": [{"id": "104596", "label": "Highest temperature"},
             {"id": "84", "label": "Weather"}],
    "markets": [
        {
            "id": "3688897",
            "question": "Will the highest temperature in Ankara be 25°C or below on August 20?",
            "conditionId": "0x3b85cb86dd0289b54a7413d653ed905ae16dd3938ef3f253b351cf3abeffcb3d",
            "slug": "highest-temperature-in-ankara-on-august-20-2026-25corbelow",
            "description": _ANKARA_DESC,
            "groupItemTitle": "25°C or below",
            "outcomes": "[\"Yes\", \"No\"]",
            "outcomePrices": "[\"0\", \"1\"]",
            "clobTokenIds": "[\"62969480000050131544837056739564346329736524326331023424743901654295773795637\", \"20157474636387479032651749148648546643295187274674415506281922004851026450653\"]",
            "umaResolutionStatus": "resolved",
            "umaResolutionStatuses": "[\"proposed\"]",
            "umaEndDate": "2026-08-20T21:42:42Z",
            "createdAt": "2026-08-18T04:56:24.504607Z",
            "startDate": "2026-08-18T04:56:35Z",
            "endDate": "2026-08-20T12:00:00Z",
            "closedTime": "2026-08-20 12:21:43+00",
            "orderPriceMinTickSize": 0.001,
            "orderMinSize": 5,
            "makerBaseFee": 1000,
            "takerBaseFee": 1000,
            "feesEnabled": True,
            "feeType": "weather_fees",
            "feeSchedule": {"exponent": 1, "rate": 0.05, "takerOnly": True, "rebateRate": 0.25},
        },
    ],
}


# ---------------------------------------------------------------- OPEN (R26) --------
def _make_open_event() -> dict:
    """An OPEN temperature event (R26 open-market discovery), DERIVED from the real
    ANKARA_EVENT so the resolution chain / fee epoch / station parsing stay real:
      * endDate in the FUTURE (2030-08-20T12:00:00Z), closed=false, active=true;
      * NO winning outcome: outcomePrices are mid-market ("0.5"/"0.5"), no
        umaResolutionStatus / umaEndDate / closedTime (not yet resolved);
      * distinct event/market/condition/token ids and slugs (synthetic, prefixed
        'open-') so it can coexist with ANKARA_EVENT in one dataset_version;
      * same feeType='weather_fees' + feeSchedule as Ankara -> NO fee-schedule
        conflict when both are ingested under one dataset_version.
    The date inside title/description is shifted to '30 to keep the text honest.
    Built with deepcopy at import time — never mutates ANKARA_EVENT."""
    import copy
    ev = copy.deepcopy(ANKARA_EVENT)
    ev.update({
        "id": "9990001",
        "title": "Highest temperature in Ankara on August 20?",
        "slug": "highest-temperature-in-ankara-on-august-20-2030",
        "description": _ANKARA_DESC.replace("20 Aug '26", "20 Aug '30"),
        "startDate": "2030-08-18T04:56:35Z",
        "endDate": "2030-08-20T12:00:00Z",
        "createdAt": "2030-08-18T04:56:14.394785Z",
        "closed": False,
        "active": True,
    })
    ev.pop("closedTime", None)
    m = ev["markets"][0]
    m.update({
        "id": "9990101",
        "question": "Will the highest temperature in Ankara be 25°C or below on August 20?",
        "conditionId": "0x0000000000000000000000000000000000000000000000000000000000099901",
        "slug": "highest-temperature-in-ankara-on-august-20-2030-25corbelow",
        "description": _ANKARA_DESC.replace("20 Aug '26", "20 Aug '30"),
        "outcomePrices": "[\"0.5\", \"0.5\"]",
        "clobTokenIds": "[\"99901000000000000000000000000000000000000000000000000000000000000000000001\", \"99901000000000000000000000000000000000000000000000000000000000000000000002\"]",
        "createdAt": "2030-08-18T04:56:24.504607Z",
        "startDate": "2030-08-18T04:56:35Z",
        "endDate": "2030-08-20T12:00:00Z",
        "closed": False,
        "active": True,
    })
    for k in ("umaResolutionStatus", "umaResolutionStatuses", "umaEndDate", "closedTime"):
        m.pop(k, None)
    return ev


OPEN_EVENT = _make_open_event()


# ---------------------------------------------------------------- R29 fixtures ----
# VERBATIM descriptions copied from CATALOG_V2.duckdb (dsc.desc, byte-identical to
# v3.descr), one per contract source / rule the R29 classifier must tell apart.
# market_id and the round-9 v3 labels are given so the fixture is traceable.
# market_id=3942167 city='Sao Paulo' v3.primary_source='NOAA' v3.primary_rule='P_NOAA_TempColumn' has_secondary_WU=True
NOAA_FALLBACK_DAILYOBS_DESC = 'This market will resolve to the temperature range that contains the highest temperature recorded by NOAA at the Sao Paulo-Guarulhos International Airport Station in degrees Celsius on 29 Aug \'26.\n\nThe resolution source for this market will be information from NOAA, specifically the highest reading under the "Temp" column for all times on this day, available here: https://www.weather.gov/wrh/timeseries?site=sbgr\n\nIf NOAA data for the observation date is unavailable by 11:59 PM ET on the day following the observation date, the Weather Underground Daily Observations table will be used as the resolution source.\n\nTo toggle between Fahrenheit and Celsius, click the "Switch to Metric Units" button until the relevant table displays °C.\n\nThis market can not resolve until the first data point for the following date has been published on the resolution source.\n\nThe resolution source for this market measures temperatures to whole degrees Celsius (eg, 9°C). Thus, this is the level of precision that will be used when resolving the market.\n\nRevisions to temperatures recorded within this market\'s timeframe will be considered until the first datapoint for the following date has been published, after which any alterations will not be considered.'

# market_id=3942200 city='Seattle' v3.primary_source='NOAA' v3.primary_rule='P_NOAA_HourlyData' has_secondary_WU=True
NOAA_HOURLY_FALLBACK_DESC = 'This market will resolve to the temperature range that contains the highest temperature recorded by NOAA at the Seattle-Tacoma International Airport Station in degrees Fahrenheit on 29 Aug \'26.\n\nThe resolution source for this market will be information from NOAA, specifically the highest reading under the "Temp" column for all times on this day, available here: https://www.weather.gov/wrh/timeseries?site=ksea\n\nThis market will resolve off of the Hourly Data provided using the "Show Hourly Data" button.\n\nIf NOAA data for the observation date is unavailable by 11:59 PM ET on the day following the observation date, the Weather Underground Daily Observations table will be used as the resolution source.\n\nTo toggle between Fahrenheit and Celsius, click the "Switch to US Units w/ kts" button until the relevant table displays °F.\n\nThis market can not resolve until the first data point for the following date has been published on the resolution source.\n\nThe resolution source for this market measures temperatures to whole degrees Fahrenheit (eg, 21°F). Thus, this is the level of precision that will be used when resolving the market.\n\nRevisions to temperatures recorded within this market\'s timeframe will be considered until the first datapoint for the following date has been published, after which any alterations will not be considered.'

# market_id=1609036 city='Hong Kong' v3.primary_source='HKO' v3.primary_rule='P_HKO_AbsDailyMax' has_secondary_WU=False
HKO_DESC = 'This market will resolve to the temperature range that contains the highest temperature recorded by the Hong Kong Observatory in degrees Celsius on 16 Mar \'26.\n\nThe resolution source for this market will be information from the Hong Kong Observatory, specifically the "Absolute Daily Max (deg. C)" the specified date once information is finalized in the relevant "Daily Extract", available here: https://www.weather.gov.hk/en/cis/climat.htm\n\nThis market can not resolve to "Yes" until data for this date has been finalized.\n\nThe resolution source for this market measures temperatures in Celsius to one decimal place (eg, 9.1°C). Thus, this is the level of precision that will be used when resolving the market.\n\nAny revisions to temperatures recorded after data is finalized for this market\'s timeframe will not be considered for this market\'s resolution.'

# market_id=1609210 city='Taipei' v3.primary_source='SIN_CLAUSULA' v3.primary_rule='P_UNKNOWN' has_secondary_WU=False
CWA_DESC = 'This market will resolve to the temperature range that contains the highest temperature recorded by Taipei\'s Central Weather Administration in degrees Celsius on 16 Mar \'26.\n\nThe resolution source for this market will be information from the Taipei Central Weather Administration, specifically the highest reading under the "Temperature" column on the specified date once information is finalized for all hours on that date, available here: https://www.cwa.gov.tw/V8/C/W/OBS_Station.html?ID=46692\n\nThis market can not resolve to "Yes" until data for this date has been finalized.\n\nThe resolution source for this market measures temperatures in Celsius to one decimal place (eg, 9.1°C). Thus, this is the level of precision that will be used when resolving the market.\n\nAny revisions to temperatures recorded after data is finalized for this market\'s timeframe will not be considered for this market\'s resolution.'

# market_id=2350603 city='London' v3.primary_source='WU' v3.primary_rule='P_WU_GENERIC_sin_calificador' has_secondary_WU=False
WU_GENERIC_DESC = "This market will resolve to the temperature range that contains the highest temperature recorded at the London City Airport Station in degrees Celsius on 27 May '26.\n\nThe resolution source for this market will be information from Wunderground, specifically the highest temperature recorded for all times on this day for the London City Airport Station, available here: https://www.wunderground.com/history/daily/gb/london/EGLC.\n\nTo toggle between Fahrenheit and Celsius, click the gear icon next to the search bar and switch the Temperature setting between °F and °C.\n\nThis market can not resolve until the first data point for the following date has been published on the resolution source.\n\nThe resolution source for this market measures temperatures to whole degrees Celsius (eg, 9°C). Thus, this is the level of precision that will be used when resolving the market.\n\nAny revisions to temperatures recorded after data is finalized for this market's timeframe will not be considered for this market's resolution."
