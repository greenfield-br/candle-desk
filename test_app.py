import tempfile,unittest
from pathlib import Path
import market_data as app
class StorageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=app.DB;app.DB=Path(self.tmp.name)/'test.db'
 def tearDown(self):
  app.DB=self.old;self.tmp.cleanup()
 def test_missing_volume_preserves_long_history(self):
  sid,_=app.save('BTC','a','spot',[dict(date='2020-01-01',open=1,high=3,low=1,close=2),dict(date='2020-01-02',open=2,high=4,low=2,close=3,volume=0)])
  self.assertIsNone(app.bars(sid)[0]['volume']);self.assertEqual(app.bars(sid)[1]['volume'],0)
  app.save('BTC','a','spot',[dict(date='2020-01-02',open=2,high=5,low=2,close=4)])
  self.assertEqual(len(app.bars(sid)),2);self.assertEqual(app.bars(sid)[1]['close'],4);self.assertEqual(app.bars(sid)[1]['volume'],0)
 def test_atomic_validation_and_separate_sources(self):
  app.save('A','one','raw',[dict(date='2020-01-01',close=10)])
  with self.assertRaises(ValueError):app.save('A','one','raw',[dict(date='2020-01-02',close=12),dict(date='2020-01-03',open=3,high=2,low=1,close=3)])
  self.assertEqual(app.catalog()[0]['bars'],1)
  app.save('A','two','raw',[dict(date='2020-01-01',close=99)])
  self.assertEqual(len(app.catalog()),2)
 def test_close_only_and_duplicates(self):
  sid,_=app.save('X','csv','raw',[dict(date='2000-01-01',close=1),dict(date='2000-01-01',close=2)])
  self.assertEqual(len(app.bars(sid)),1);self.assertIsNone(app.bars(sid)[0]['open']);self.assertEqual(app.bars(sid)[0]['close'],2)

class ProviderTests(StorageTests):
 def test_fred_missing_observation_skipped(self):
  from unittest.mock import patch
  with patch.object(app,'fetch',return_value='observation_date,DGS10\n2020-01-01,.\n2020-01-02,1.75\n'):
   sid,n=app.download('fred','DGS10','2020-01-01','2020-01-03')
  self.assertEqual(n,1);self.assertEqual(app.bars(sid)[0]['close'],1.75)
 def test_stablecoin_usd_conversion_not_raw_sum(self):
  from unittest.mock import patch
  import json
  payload=[dict(date='1577923200',totalCirculating={'peggedUSD':100,'peggedEUR':20},totalCirculatingUSD={'peggedUSD':100,'peggedEUR':23})]
  with patch.object(app,'fetch',return_value=json.dumps(payload)):
   sid,n=app.download('defillama','STABLECAP','2020-01-01','2020-01-03')
  self.assertEqual(app.bars(sid)[0]['close'],123)
  payload[0].pop('totalCirculatingUSD')
  with patch.object(app,'fetch',return_value=json.dumps(payload)):
   with self.assertRaises(ValueError):app.download('defillama','STABLECAP','2020-01-01','2020-01-03')
 def test_b3_units_and_share_volume(self):
  from b3_import import parse
  row=list(' '*245)
  def put(a,b,s):row[a:b]=s
  put(0,2,'01');put(2,10,'20200102');put(12,24,'PETR4'.ljust(12));put(24,27,'010');put(52,56,'R$  ')
  for a,b,v in [(56,69,10000),(69,82,12000),(82,95,9000),(108,121,11000)]:put(a,b,str(v).zfill(b-a))
  put(152,170,str(400).zfill(18));put(210,217,str(1000).zfill(7));put(230,242,'BRPETRACNPR6')
  rows=list(parse([''.join(row)],{'PETR4'}).values())[0]
  self.assertEqual(rows[0]['open'],.1);self.assertEqual(rows[0]['volume'],400)

if __name__=='__main__':unittest.main()
