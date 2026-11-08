import pandas as pd
import chardet
import datetime
from pycountry import countries
import iso4217parse
import re

file_name = r'C:\Users\joshu\Documents\Project Stuff\Convergence Practice\convergence_practice_round2\convergence_practice_round2\tapes\westmere_loan_tape_2026Q3.csv'

with open(file_name,'rb') as f:
     file_encoding = chardet.detect(f.read())

#using chardet to find encoding
df = pd.read_csv(file_name,encoding = file_encoding['encoding'])
pd.set_option('display.max_rows', None)

print(df.loc[:,'drawn_amount'])

#fixing obligor
df['obligor'] = df['obligor'].map(lambda name: name.upper())
# print(df.loc[72:88,:])


#cleaning dates
df['start_date'] = pd.to_datetime(df['start_date'], dayfirst=False, format='mixed')
df['end_date'] = pd.to_datetime(df['end_date'], dayfirst=False, format='mixed')

#domiciles
#worth caching so you don't have to repeatedly use pycountry
domiciles = {}
def get_alpha2(country):
     if country not in domiciles:
          res = countries.search_fuzzy(country)
          best_match = res[0]
          domiciles[country] = best_match.alpha_2
     return domiciles[country]
df['domicile'] = df['domicile'].apply(get_alpha2)

#currencies
currencies = {}
def get_currency(text):
     if text not in currencies:
          res = iso4217parse.parse(text)
          currencies[text] = res[0].alpha3
     return currencies[text]
df['ccy'] = df['ccy'].apply(get_currency)


##limit
# need to multiply by 1000, then convert according to currency
#read in exchange rates, convert limits to GBP

exchange_rates = r'C:\Users\joshu\Documents\Project Stuff\Convergence Practice\convergence_practice_round2\convergence_practice_round2\reference\fx_used.csv'
with open(exchange_rates,'rb') as f:
     file_encoding = chardet.detect(f.read())
fx = pd.read_csv(exchange_rates,encoding = file_encoding['encoding'])


rates_map = fx.set_index('currency')['gbp_per_unit']
df['limit_000s'] = (pd.to_numeric(df['limit_000s']) * 1000 * df['ccy'].map(rates_map)).round(2)

df = df.rename(columns={'limit_000s' : 'limit_gbp'})



##drawn amount
regex = r'[^0-9.]+'
df['drawn_amount'] = df['drawn_amount'].str.replace(regex,'',regex=True)
df['drawn_amount'] = (pd.to_numeric(df['drawn_amount'], errors='coerce') * df['ccy'].map(rates_map)).round(2)


print(df.loc[60:75,:])

# print(df['ccy'].value_counts())

for column in df.columns:
    print(column,':',pd.api.types.infer_dtype(df[column]))

for column in fx.columns:
     print(column,':',pd.api.types.infer_dtype(fx[column]))
