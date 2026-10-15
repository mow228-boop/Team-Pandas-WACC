"""Estimate the client's WACC.

Run from the repo root:   python code/wacc.py
Reads:  inputs/assumptions.csv
Writes: outputs/wacc.csv (one row; the columns are listed in README.md)

Owner: the developer.
"""
import math

import pandas as pd
import yfinance as yf

CLIENT = 'FLEX'
MKT = 'SPY'
YEARS = 5


def get_returns(ticker, mkt=MKT, years=YEARS):
    """Daily returns for the client and the market over the last `years` years.
    Returns a DataFrame with two columns, named ticker and mkt, and no missing values."""
    if years <= 0:
        raise ValueError('years must be positive')
    if ticker == mkt:
        raise ValueError('ticker and market benchmark must be different')

    prices = yf.download(
        tickers=[ticker, mkt],
        period=f'{years}y',
        interval='1d',
        auto_adjust=True,
        progress=False,
    )
    if prices.empty:
        raise ValueError(f'No price data returned for {ticker} and {mkt}')

    # yfinance returns a MultiIndex for multiple tickers. The level order has
    # varied across releases, so locate the "Close" level rather than assume it.
    if isinstance(prices.columns, pd.MultiIndex):
        close = None
        for level in range(prices.columns.nlevels):
            if 'Close' in prices.columns.get_level_values(level):
                close = prices.xs('Close', axis=1, level=level)
                break
        if close is None:
            raise ValueError('Downloaded price data has no Close prices')
    else:
        if 'Close' not in prices.columns:
            raise ValueError('Downloaded price data has no Close prices')
        close = prices[['Close']]

    missing = [symbol for symbol in (ticker, mkt) if symbol not in close.columns]
    if missing:
        raise ValueError(f'Close prices missing for: {", ".join(missing)}')

    close = close[[ticker, mkt]].apply(pd.to_numeric, errors='coerce')
    returns = close.pct_change(fill_method=None).dropna()
    returns.columns = [ticker, mkt]
    if returns.empty:
        raise ValueError(f'No aligned daily returns available for {ticker} and {mkt}')
    return returns


def estimate_beta(rets, ticker, mkt=MKT):
    """Equity beta: cov(stock, market) / var(market)."""
    if ticker not in rets.columns or mkt not in rets.columns:
        raise ValueError(f'Returns must contain {ticker} and {mkt} columns')
    paired = rets[[ticker, mkt]].dropna()
    if paired.empty:
        raise ValueError('Cannot estimate beta without paired returns')
    market_variance = paired[mkt].var(ddof=1)
    if not math.isfinite(market_variance) or market_variance <= 0:
        raise ValueError('Market returns must have positive, finite variance')
    beta = paired[ticker].cov(paired[mkt]) / market_variance
    if not math.isfinite(beta):
        raise ValueError('Estimated beta is not finite')
    return float(beta)


def compute_wacc(beta, a):
    """a is a dict of assumptions: rf, mrp, rd, tax, w_e, w_d.
    Returns a dict with cost_of_equity and wacc (and the inputs), matching the README's columns."""
    required = ('rf', 'mrp', 'rd', 'tax', 'w_e', 'w_d')
    missing = [key for key in required if key not in a]
    if missing:
        raise ValueError(f'Missing WACC assumptions: {", ".join(missing)}')
    assumptions = {key: float(a[key]) for key in required}
    if not all(math.isfinite(value) for value in assumptions.values()):
        raise ValueError('WACC assumptions must all be finite numbers')
    if not math.isfinite(beta):
        raise ValueError('Beta must be finite')
    if not 0 <= assumptions['tax'] <= 1:
        raise ValueError('Tax rate must be between 0 and 1')
    if assumptions['w_e'] < 0 or assumptions['w_d'] < 0:
        raise ValueError('Capital weights cannot be negative')
    assert abs(assumptions['w_e'] + assumptions['w_d'] - 1) < 1e-6, \
        'weights must sum to 1'

    cost_of_equity = assumptions['rf'] + beta * assumptions['mrp']
    wacc = (assumptions['w_e'] * cost_of_equity
            + assumptions['w_d'] * assumptions['rd'] * (1 - assumptions['tax']))
    return {
        **assumptions,
        'cost_of_equity': cost_of_equity,
        'wacc': wacc,
    }


if __name__ == '__main__':
    a = pd.read_csv('inputs/assumptions.csv', index_col='item')['value'].to_dict()
    assert abs(a['w_e'] + a['w_d'] - 1) < 1e-6, 'weights must sum to 1'

    rets = get_returns(CLIENT)
    assert not rets.isna().any().any(), 'returns must not contain missing values'
    assert len(rets) > 1000, 'expected about 5 years of daily returns'

    beta = estimate_beta(rets, CLIENT)
    out = compute_wacc(beta, a)
    out = {'ticker': CLIENT, 'asof': rets.index.max().date(), 'beta': beta, **out}

    assert 0 < out['wacc'] < 0.25, 'WACC outside 0-25%: check the inputs'
    cols = ['ticker', 'asof', 'beta', 'rf', 'mrp', 'cost_of_equity', 'rd', 'tax', 'w_e', 'w_d', 'wacc']
    pd.DataFrame([out])[cols].to_csv('outputs/wacc.csv', index=False)
    print(pd.DataFrame([out])[cols].T)
