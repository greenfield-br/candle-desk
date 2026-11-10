#!/usr/bin/env python3
"""Import locally downloaded official COTAHIST TXT/ZIP, cash market 010 only.
Layout: https://www.b3.com.br/data/files/65/50/AD/26/29C8B51095EE46B5790D8AA8/HistoricalQuotations_B3.pdf
Prices divided by FATCOT to get per-unit quotations. No corporate-action adjustment.
"""
import argparse, collections, hashlib, io, shutil, zipfile
from pathlib import Path
import market_data as app

def parse(lines, symbols):
    groups=collections.defaultdict(list)
    for n,line in enumerate(lines,1):
        line=line.rstrip('\r\n')
        if not line.startswith('01'): continue
        if len(line)!=245: raise ValueError(f'Line {n}: expected 245 characters, got {len(line)}')
        symbol=line[12:24].strip()
        if line[24:27]!='010' or (symbols and symbol not in symbols):continue
        day=line[2:10];currency=line[52:56].strip();isin=line[230:242].strip()
        factor=int(line[210:217])
        if factor<=0:raise ValueError(f'Line {n}: invalid FATCOT')
        r=dict(date=f'{day[:4]}-{day[4:6]}-{day[6:8]}',open=int(line[56:69])/100/factor,
            high=int(line[69:82])/100/factor,low=int(line[82:95])/100/factor,
            close=int(line[108:121])/100/factor,volume=int(line[152:170]))
        app.normalize(r)
        groups[(symbol,currency,isin)].append(r)
    return groups

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('file');p.add_argument('--symbols',nargs='*',default=[]);a=p.parse_args()
    path=Path(a.file)
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n.lower().endswith('.txt')]
            if len(names)!=1:raise ValueError('Expected exactly one TXT in ZIP')
            with z.open(names[0]) as f:groups=parse(io.TextIOWrapper(f,encoding='latin-1'),set(a.symbols))
    else:
        with path.open(encoding='latin-1') as f:groups=parse(f,set(a.symbols))
    if not groups:raise ValueError('No matching cash-market records')
    archive=app.ROOT/'raw';archive.mkdir(exist_ok=True)
    digest=hashlib.sha256(path.read_bytes()).hexdigest();shutil.copyfile(path,archive/(digest+path.suffix.lower()))
    for (symbol,currency,isin),rows in groups.items():
        basis=f'COTAHIST unadjusted; unit price; {currency}; ISIN={isin}; share/unit volume'
        print(symbol,app.save(symbol,'b3-cotahist',basis,rows))
if __name__=='__main__':main()
