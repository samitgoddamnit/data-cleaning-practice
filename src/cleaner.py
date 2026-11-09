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

# print(df.loc[:,'drawn_amount'])

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

##rate types
valid_rate_types = {'FIXED', 'FLOATING'}
rate_types_csv = data_dir / 'aliases' / 'rate_types_dict.csv'
rate_types = pd.read_csv(rate_types_csv).set_index('alias')['canonical'].to_dict()

def process_rate_type(rate_type_alias):
     #blank rate types are left blank for exceptions
     if pd.isna(rate_type_alias):
          return np.nan
     rate_type_alias = normalise(rate_type_alias)
     if rate_type_alias in valid_rate_types:
          return rate_type_alias
     if rate_type_alias not in rate_types:
          #cutoff=0 so there is always a default, whichever of the two is closer
          default = get_close_matches(rate_type_alias, sorted(valid_rate_types), n=1, cutoff=0)[0]
          answer = ''
          while answer not in valid_rate_types and answer != '-':
               print(f"input rate type for {rate_type_alias}, options: {sorted(valid_rate_types)}, enter to use {default}, - to leave empty")
               answer = normalise(input()) or default
          #'-' saves an empty mapping, so the alias stays blank without asking again
          canonical = '' if answer == '-' else answer
          rate_type_mapping = [rate_type_alias,canonical]
          with open(rate_types_csv,'a',newline='',encoding='utf-8') as f:
               writer_obj = writer(f)
               writer_obj.writerow(rate_type_mapping)
          rate_types[rate_type_alias] = canonical or np.nan
     return rate_types[rate_type_alias]
df['rate_type'] = df['rate_type'].apply(process_rate_type)

##statuses
#official statuses, keyed the same way the tape is normalised
valid_statuses = {normalise(status): status for status in ['Active', 'Arrears', 'Defaulted', 'Repaid']}
statuses_csv = data_dir / 'aliases' / 'status_dict.csv'
statuses = pd.read_csv(statuses_csv).set_index('alias')['canonical'].to_dict()

def process_status(status_alias):
     #blank statuses are left blank for exceptions
     if pd.isna(status_alias):
          return np.nan
     status_alias = normalise(status_alias)
     if status_alias in valid_statuses:
          return valid_statuses[status_alias]
     if status_alias not in statuses:
          #cutoff=0 so there is always a default, whichever status is closest
          default = get_close_matches(status_alias, sorted(valid_statuses), n=1, cutoff=0)[0]
          answer = ''
          while answer not in valid_statuses and answer != '-':
               print(f"input status for {status_alias}, options: {sorted(valid_statuses.values())}, enter to use {valid_statuses[default]}, - to leave empty")
               answer = normalise(input()) or default
          #'-' saves an empty mapping, so the alias stays blank without asking again
          canonical = '' if answer == '-' else valid_statuses[answer]
          status_mapping = [status_alias,canonical]
          with open(statuses_csv,'a',newline='',encoding='utf-8') as f:
               writer_obj = writer(f)
               writer_obj.writerow(status_mapping)
          statuses[status_alias] = canonical or np.nan
     return statuses[status_alias]
df['status'] = df['status'].apply(process_status)


##ext_rating
pd_by_rating = data_dir / 'reference' / 'pd_by_rating.csv'
with open(pd_by_rating,'rb') as f:
     file_encoding = chardet.detect(f.read())
pddf = pd.read_csv(pd_by_rating,encoding = file_encoding['encoding'])
sp_scale = list(pddf.sort_values('rating_rank')['sp_rating'])
valid_ratings = set(sp_scale) | {'NR'}
ratings_csv = data_dir / 'aliases' / 'ratings_dict.csv'
ratings = pd.read_csv(ratings_csv).set_index('alias')['canonical'].to_dict()

def process_rating(rating_alias):
     #blank ratings are left blank for exceptions
     if pd.isna(rating_alias):
          return np.nan
     rating_alias = normalise(rating_alias)
     if rating_alias in valid_ratings:
          return rating_alias
     if rating_alias not in ratings:
          default = get_close_matches(rating_alias, sorted(valid_ratings), n=1, cutoff=0)[0]
          answer = ''
          while answer not in valid_ratings and answer != '-':
               print(f"input S&P rating for {rating_alias}, options: {sp_scale + ['NR']}, enter to use {default}, - to leave empty")
               answer = normalise(input()) or default
          canonical = '' if answer == '-' else answer
          rating_mapping = [rating_alias,canonical]
          with open(ratings_csv,'a',newline='',encoding='utf-8') as f:
               writer_obj = writer(f)
               writer_obj.writerow(rating_mapping)
          ratings[rating_alias] = canonical or np.nan
     return ratings[rating_alias]
df['ext_rating'] = df['ext_rating'].apply(process_rating)

#rating bucket, BBB- and above is investment grade
def get_rating_bucket(rating):
     if rating in sp_scale:
          if sp_scale.index(rating) <= sp_scale.index('BBB-'):
               return 'IG'
          return 'SubIG'
     return 'NR'
df['rating_bucket'] = df['ext_rating'].apply(get_rating_bucket)






print(df.loc[75:120,:])

# print(df['ccy'].value_counts())

# for column in df.columns:
#     print(column,':',pd.api.types.infer_dtype(df[column]))

# for column in fx.columns:
#      print(column,':',pd.api.types.infer_dtype(fx[column]))
