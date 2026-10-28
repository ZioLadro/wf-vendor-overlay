"""Market signals for the recommendations and the inventory advice: classic, open techniques from trading, scaled down to
what warframe.market publishes (one point a day per item, a few to a few hundred trades a day, 90 days of history).

From the daily closed-trade statistics (rank 0, or the item itself when it has no ranks):
  EMA 7 / EMA 30    exponential moving averages of the daily (volume-weighted) price; trend = EMA7 / EMA30 - 1.
                    A short average under the long one = prices falling (sell sooner), above = rising.
  Bollinger / z     mean and standard deviation of the last 20 days; z = (price now - mean) / deviation. z >= 1.5: today's
                    price is unusually high for this item (a spike: good moment to sell, bad moment to count on it).
  bid / ask         from the live orders: the best price a buyer online pays right now (bid) and the lowest a seller
                    asks (ask, the "price" everywhere else). The bid is what you get for an instant sale.
  backtest          the estimate below is replayed on the item's own past: for each day of the last weeks it is computed
                    with only the data known that day, and compared with the average price the item really traded at in
                    the 7 days after. The median of actual / estimated is the item's calibration (1.0 = the estimate was
                    right; 0.85 = it was 15 % too optimistic) and corrects the estimate (between 0.75 and 1.15).

expected price  = price, pulled towards the 30-day average when above it (advice_trend_weight, as before)
                  × trend factor (1 + trend / 2, between 0.85 and 1.05)
                  × calibration (when the backtest had at least 5 days)
                  never above the price asked now, and never below the bid (someone pays that now).
signal          = "sell" (sell now: falling, or a spike: z >= 2, or z >= 1.5 and 8 % above the 7-day EMA) /
                  "wait" (rising, not a spike) / "" (nothing special)."""
import statistics
from datetime import datetime, timezone

MIN_DAYS = 10          # fewer days of history: no indicators
BT_MIN = 5             # backtest days needed before the calibration is used


def daily_series(rows, max_rank=0):
    """[(day number, volume-weighted price, volume)] oldest first, from the statistics rows (90days list): rank 0 for
    ranked items, every row otherwise."""
    days = {}
    for r in rows or []:
        try:
            if max_rank and r.get("mod_rank") not in (None, 0):
                continue
            when = datetime.fromisoformat(str(r["datetime"]).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            vol = int(r.get("volume") or 0)
            price = r.get("avg_price") if r.get("avg_price") is not None else r.get("median")
            if vol <= 0 or price is None:
                continue
            d = int(when.timestamp() // 86400)
            acc = days.setdefault(d, [0.0, 0])
            acc[0] += float(price) * vol
            acc[1] += vol
        except (KeyError, ValueError, TypeError):
            continue
    return [(d, s / n, n) for d, (s, n) in sorted(days.items()) if n]


def ema(values, n):
    if not values:
        return None
    k = 2.0 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def _estimate(price, prices_before, weight):
    """The estimate as the program makes it, from a price and the daily prices known before it."""
    last30 = prices_before[-30:]
    mean30 = sum(last30) / len(last30)
    pe = price * (1 - weight) + mean30 * weight if price > mean30 else price
    e7, e30 = ema(prices_before[-60:], 7), ema(prices_before[-60:], 30)
    tr = (e7 / e30 - 1) if e7 and e30 else 0.0
    return pe * max(0.85, min(1.05, 1 + tr / 2))


def backtest(prices, weight):
    """(median of actual next-7-days price / estimate, number of days tested) over the last 30 testable days."""
    ratios = []
    for i in range(max(14, len(prices) - 37), len(prices) - 7):
        est = _estimate(prices[i], prices[:i], weight)
        nxt = prices[i + 1:i + 8]
        if est > 0 and nxt:
            ratios.append((sum(nxt) / len(nxt)) / est)
    return (round(statistics.median(ratios), 3), len(ratios)) if ratios else (None, 0)


def indicators(series, weight=0.5):
    """{"ema7","ema30","trend","mean20","sd20","bt","bt_n","days"} from daily_series (None when too short)."""
    if len(series) < MIN_DAYS:
        return None
    prices = [p for _d, p, _v in series]
    e7, e30 = ema(prices, 7), ema(prices, 30)
    last20 = prices[-20:]
    sd = statistics.pstdev(last20) if len(last20) > 1 else 0.0
    bt, n = backtest(prices, weight)
    return {"ema7": round(e7, 1), "ema30": round(e30, 1), "trend": round(e7 / e30 - 1, 3) if e30 else 0.0,
            "mean20": round(sum(last20) / len(last20), 1), "sd20": round(sd, 2), "bt": bt, "bt_n": n, "days": len(prices)}


def zscore(price, ind):
    if price is None or not ind or not ind.get("sd20"):
        return None
    return (price - ind["mean20"]) / ind["sd20"]


def expected_price(price, avg=None, ind=None, bid=None):
    """What one copy realistically sells for (see the module notes). None without a price."""
    if price is None:
        return None
    from app.trade.advice import eff_price
    e = eff_price(price, avg)
    if ind:
        e *= max(0.85, min(1.05, 1 + (ind.get("trend") or 0) / 2))
        if ind.get("bt") and ind.get("bt_n", 0) >= BT_MIN:
            e *= max(0.75, min(1.15, ind["bt"]))
    e = min(e, float(price))                    # never more than the lowest seller asks
    if bid and bid > e:
        e = min(float(bid), float(price))
    return e


def describe(price, ind, bid, lang_t):
    """Tooltip lines: trend, spike, bid/ask spread, backtest (lang_t = the translation function)."""
    out = []
    if ind:
        out.append(lang_t("sig.trend", e7=ind["ema7"], e30=ind["ema30"], pct=f"{(ind.get('trend') or 0) * 100:+.0f}"))
        z = zscore(price, ind)
        if z is not None:
            out.append(lang_t("sig.z", z=f"{z:+.1f}", mean=ind["mean20"]))
        if ind.get("bt") and ind.get("bt_n", 0) >= BT_MIN:
            out.append(lang_t("sig.bt", pct=f"{ind['bt'] * 100:.0f}", n=ind["bt_n"]))
        else:
            out.append(lang_t("sig.bt.none"))
    else:
        out.append(lang_t("sig.none"))
    if bid:
        out.append(lang_t("sig.bid", bid=bid, ask=price if price is not None else "–"))
    return "\n".join(out)


def arrow(ind):
    tr = (ind or {}).get("trend")
    if tr is None:
        return "–"
    return ("↑ " if tr >= 0.03 else "↓ " if tr <= -0.03 else "→ ") + f"{tr * 100:+.0f}%"


def signal(price, ind):
    """"sell" (falling or a spike: sell now), "wait" (rising and not a spike) or ""."""
    if not ind or price is None:
        return ""
    z, tr = zscore(price, ind), ind.get("trend") or 0
    spike = z is not None and (z >= 2.0 or (z >= 1.5 and price > (ind.get("ema7") or price) * 1.08))
    if spike or tr <= -0.05:
        return "sell"
    if tr >= 0.05:
        return "wait"
    return ""
