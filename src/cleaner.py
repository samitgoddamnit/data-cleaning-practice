import pandas as pd
import numpy as np
import chardet
import datetime
from pycountry import countries
import iso4217parse
import re
from pathlib import Path
from csv import writer
from difflib import get_close_matches


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
sectors_legend = data_dir / 'reference' / 'lgd_by_sector.csv'
with open(sectors_legend,'rb') as f:
     file_encoding = chardet.detect(f.read())
scdf = pd.read_csv(sectors_legend,encoding = file_encoding['encoding'])
#upper case and collapse runs of whitespace to single spaces
def normalise(text):
     return ' '.join(text.upper().split())

#official sector names, keyed the same way industry is normalised below
valid_sectors = {normalise(name): name for name in scdf['sector']}

#keep the raw obligor so it can be offered as the display name
df['obligor_raw'] = df['obligor']

#normalise names for processing
df['industry'] = df['industry'].str.upper().str.split().str.join(' ').replace('', np.nan)
df['obligor'] = df['obligor'].str.upper().str.split().str.join(' ').replace('', np.nan)

alias_to_canon_csv = data_dir / 'aliases' / 'alias_to_canon.csv'
canon_to_display_csv = data_dir / 'aliases' / 'canon_to_display.csv'
alias_to_industry_csv = data_dir / 'aliases' / 'alias_to_industry.csv'

a2c = pd.read_csv(alias_to_canon_csv).set_index('alias')['canonical'].to_dict()
c2d = pd.read_csv(canon_to_display_csv).set_index('canon')['display'].to_dict()
a2i = pd.read_csv(alias_to_industry_csv).set_index('alias')['industry'].to_dict()

def process_names(row):
     #blank obligors are left blank for exceptions
     obligor_alias = row['obligor']
     if pd.isna(obligor_alias):
          canon = np.nan
          canon_display = np.nan
     else:
          if obligor_alias not in a2c:
               ##add the alias to canon mapping, suggesting close existing canon names
               suggestions = get_close_matches(obligor_alias, set(a2c.values()), n=3)
               default = suggestions[0] if suggestions else obligor_alias
               print(f"input the canon mapping for {obligor_alias}")
               print(f"suggestions: {suggestions}, enter to use {default}, or type a new canon name")
               canon = normalise(input()) or default
               alias_canon_mapping = [obligor_alias,canon]
               with open(alias_to_canon_csv,'a',newline='',encoding='utf-8') as f:
                    writer_obj = writer(f)
                    writer_obj.writerow(alias_canon_mapping)
               a2c[obligor_alias] = canon
          canon = a2c[obligor_alias]

          if canon not in c2d:
               raw = row['obligor_raw'].strip()
               print(f"input display name for {canon}, enter to use {raw}")
               display = input().strip() or raw
               canon_display_mapping = [canon,display]
               with open(canon_to_display_csv,'a',newline='',encoding='utf-8') as f:
                    writer_obj = writer(f)
                    writer_obj.writerow(canon_display_mapping)
               c2d[canon] = display
          canon_display = c2d[canon]

     #blank industries are left blank for exceptions
     industry_alias = row['industry']
     if pd.isna(industry_alias):
          industry = np.nan
     elif industry_alias in valid_sectors:
          industry = valid_sectors[industry_alias]
     else:
          if industry_alias not in a2i:
               answer = ''
               while answer not in valid_sectors:
                    print(f"input industry for {industry_alias}, options: {sorted(valid_sectors.values())}")
                    answer = normalise(input())
               alias_industry_mapping = [industry_alias,valid_sectors[answer]]
               with open(alias_to_industry_csv,'a',newline='',encoding='utf-8') as f:
                    writer_obj = writer(f)
                    writer_obj.writerow(alias_industry_mapping)
               a2i[industry_alias] = valid_sectors[answer]
          industry = a2i[industry_alias]

     row['obligor'] = canon_display
     row['obligor_canon'] = canon
     row['industry'] = industry

     return row


df = df.apply(process_names,axis=1)
df = df.drop(columns='obligor_raw')

print(df.loc[75:120,:])

# print(df['ccy'].value_counts())

# for column in df.columns:
#     print(column,':',pd.api.types.infer_dtype(df[column]))

# for column in fx.columns:
#      print(column,':',pd.api.types.infer_dtype(fx[column]))
