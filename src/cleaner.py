import pandas as pd
import numpy as np
import chardet
import datetime
from pycountry import countries
import iso4217parse
import re
from pathlib import Path
from csv import writer


data_dir = Path(__file__).resolve().parent.parent / 'practice_round2' / 'practice_round2'

file_name = data_dir / 'tapes' / 'westmere_loan_tape_2026Q3.csv'

with open(file_name,'rb') as f:
     file_encoding = chardet.detect(f.read())

#using chardet to find encoding
df = pd.read_csv(file_name,encoding = file_encoding['encoding'])
pd.set_option('display.max_rows', None)

print(df.loc[:,'drawn_amount'])

#fixing obligor
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

exchange_rates = data_dir / 'reference' / 'fx_used.csv'
with open(exchange_rates,'rb') as f:
     file_encoding = chardet.detect(f.read())
fx = pd.read_csv(exchange_rates,encoding = file_encoding['encoding'])


rates_map = fx.set_index('currency')['gbp_per_unit']
df['limit_000s'] = (pd.to_numeric(df['limit_000s']) * 1000 * df['ccy'].map(rates_map)).round(2)

df = df.rename(columns={'limit_000s' : 'limit_gbp'})



##drawn amount
##this needs to be made more robust for negative numbers and to account for european decimals
regex = r'[^0-9.]+'
df['drawn_amount'] = df['drawn_amount'].str.replace(regex,'',regex=True)
df['drawn_amount'] = (pd.to_numeric(df['drawn_amount'], errors='coerce') * df['ccy'].map(rates_map)).round(2)


##loading sectors
# sectors_legend = data_dir / 'reference' / 'lgd_by_sector.csv'
# with open(sectors_legend,'rb') as f:
#      file_encoding = chardet.detect(f.read())
# scdf = pd.read_csv(sectors_legend,encoding = file_encoding['encoding'])
# scdf['sector'] = scdf['sector'].map(lambda x: x.strip().upper())

#normalise names for processing
df['industry'] = df['industry'].str.upper().str.replace(r'\s+', '', regex=True).replace('', np.nan)
df['obligor'] = df['obligor'].str.upper().str.replace(r'\s+', '', regex=True).replace('', np.nan)

alias_to_canon_csv = data_dir / 'aliases' / 'alias_to_canon.csv'
canon_to_display_csv = data_dir / 'aliases' / 'canon_to_display.csv'
canon_to_industry_csv = data_dir / 'aliases' / 'canon_to_industry.csv'



##better to use a database here? and then cache aliases. That way, I can be more efficient if something like hotels & leisure comes up again
##going to use a csv file that I read into sector_aliases at the beginning, then use apply on each row
sector_aliases_csv = data_dir / 'aliases' / 'sector_aliases.csv'
sector_aliases = pd.read_csv(sector_aliases_csv).set_index('alias')['canonical'].to_dict()
def process_sector(name):
     if name not in sector_aliases:
          print(f"input canonical form for {name}")
          canon = input()
          new_row = [name,canon]
          with open(sector_aliases_csv,'a',newline='') as f:
               writer_obj = writer(f)
               writer_obj.writerow(new_row)
          sector_aliases[name] = canon
     return sector_aliases[name] or np.nan
df['industry'] = df['industry'].apply(process_sector)



# print(df.loc[75:120,:])

# print(df['ccy'].value_counts())

for column in df.columns:
    print(column,':',pd.api.types.infer_dtype(df[column]))

for column in fx.columns:
     print(column,':',pd.api.types.infer_dtype(fx[column]))
