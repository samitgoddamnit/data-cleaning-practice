used chardet to deducing encoding of csv files

- westmere is using Windows-1252 encoding according to chardet
- westmere is using UK notation for its prices, removing commas shouldn't break any transactions
- rheinland is using different notation, so I'll deal with that seperately
