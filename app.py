"""The WACC card.

Run from the repo root:   streamlit run app.py

Owner: the product manager. This works today on the FAKE numbers, so you can build
the page before the real numbers exist. When the developer's pull request is merged,
outputs/wacc.csv appears and the app switches to it automatically.

The app only reads files. The what-if sliders redo the WACC arithmetic on the numbers
already in the file; nothing is downloaded or re-estimated here.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title='WACC card', layout='centered')

real = Path('outputs/wacc.csv')
rows = pd.read_csv(real if real.exists() else 'outputs/wacc_FAKE.csv')
card = rows.iloc[0]    # the first row is the client
peers = rows.iloc[1:]  # any extra rows are competitors (optional)
sources = pd.read_csv('inputs/assumptions.csv', index_col='item')['source']

assert abs(card['w_e'] + card['w_d'] - 1) < 1e-6, 'weights must sum to 1'
assert 0 < card['wacc'] < 0.25, 'WACC outside 0-25%: check outputs/wacc.csv'

firm = card['ticker']
rd_after_tax = card['rd'] * (1 - card['tax'])


def compute_wacc(beta, mrp, w_d):
    """Same formula as code/wacc.py, with rf, rd and tax taken from the card."""
    cost_of_equity = card['rf'] + beta * mrp
    return (1 - w_d) * cost_of_equity + w_d * rd_after_tax


def relever(beta, w_d_old, w_d_new):
    """Hamada: remove the effect of today's debt on beta, then apply the new debt level."""
    t = card['tax']
    unlevered = beta / (1 + (1 - t) * w_d_old / (1 - w_d_old))
    return unlevered * (1 + (1 - t) * w_d_new / (1 - w_d_new))


if not real.exists():
    st.warning('Showing FAKE numbers. Run `python code/wacc.py` to make outputs/wacc.csv.')

# --- The answer, in one sentence ---------------------------------------------------
st.title(f"{firm}: new projects must earn at least {card['wacc']:.2%}")
st.markdown(
    f"**{card['wacc']:.2%} is {firm}'s cost of capital (WACC)**: the return its "
    f"shareholders and lenders, together, expect. Use it as the **hurdle rate** for new "
    f"projects of average risk. A project expected to return less than this loses value. "
    f"Riskier projects need a higher bar."
)
st.caption(f"Based on stock returns through {card['asof']}.")

c1, c2, c3 = st.columns(3)
c1.metric('Hurdle rate (WACC)', f"{card['wacc']:.2%}")
c2.metric('Cost of equity', f"{card['cost_of_equity']:.2%}",
          help='The return shareholders expect: risk-free rate + beta × market risk premium.')
c3.metric('Cost of debt, after tax', f"{rd_after_tax:.2%}",
          help='Interest rate on debt, reduced by the tax saving on interest.')

st.markdown(
    f"**How it adds up:** {card['w_e']:.0%} equity at {card['cost_of_equity']:.2%}"
    f" + {card['w_d']:.0%} debt at {rd_after_tax:.2%} = **{card['wacc']:.2%}**"
)

# --- What if --------------------------------------------------------------------
st.subheader('What if?')
s1, s2 = st.columns(2)
w_d_pct = s1.slider('Debt share of funding (%)', 0.0, 80.0,
                    float(round(card['w_d'] * 100)), step=1.0)
mrp_pct = s2.slider('Market risk premium (%)', 3.0, 8.0,
                    float(round(card['mrp'] * 100 * 4) / 4), step=0.25)

w_d_new, mrp_new = w_d_pct / 100, mrp_pct / 100
beta_new = relever(card['beta'], card['w_d'], w_d_new)
wacc_new = compute_wacc(beta_new, mrp_new, w_d_new)
change_bp = (wacc_new - card['wacc']) * 10_000

st.metric('Hurdle rate with these settings', f"{wacc_new:.2%}",
          delta=f"{change_bp:+.0f} bp vs. today", delta_color='inverse')
st.caption(
    'More debt makes the shares riskier, so beta is adjusted as the debt share moves '
    f"(now {beta_new:.2f} vs. {card['beta']:.2f} today). The cost of debt is held at "
    f"{card['rd']:.1%}; in practice lenders charge more at high debt levels, so the "
    'right-hand end of the slider understates the true cost.'
)

# --- Competitors (shown only if outputs/wacc.csv has extra rows) --------------------
if not peers.empty:
    st.subheader(f'How {firm} compares')
    table = rows[['ticker', 'beta', 'cost_of_equity', 'wacc']].copy()
    table['beta'] = table['beta'].map('{:.2f}'.format)
    for col in ['cost_of_equity', 'wacc']:
        table[col] = table[col].map('{:.2%}'.format)
    table.columns = ['Company', 'Beta', 'Cost of equity', 'WACC']
    st.dataframe(table, hide_index=True)

# --- Inputs and sources -----------------------------------------------------------
st.subheader('Inputs and sources')
labels = {
    'rf': 'Risk-free rate', 'mrp': 'Market risk premium', 'beta': 'Beta (vs. S&P 500)',
    'rd': 'Cost of debt, before tax', 'tax': 'Tax rate',
    'w_e': 'Equity share of funding', 'w_d': 'Debt share of funding',
}
source_of = {**sources.to_dict(),
             'beta': f"Estimated from 5 years of daily returns vs. SPY, through {card['asof']}"}
inputs = pd.DataFrame({
    'Input': list(labels.values()),
    'Value': [f"{card[k]:.2f}" if k == 'beta' else f"{card[k]:.2%}" for k in labels],
    'Source': [source_of.get(k, 'missing') for k in labels],
})
st.dataframe(inputs, hide_index=True)

if inputs['Source'].str.startswith(('TODO', 'missing')).any():
    st.warning('Some inputs do not have a source yet (see the Source column).')

st.caption('WACC = equity share × cost of equity + debt share × cost of debt × (1 − tax rate). '
           'Cost of equity = risk-free rate + beta × market risk premium.')
