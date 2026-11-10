import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import market_data as m
class StablecoinTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=m.DB;m.DB=Path(self.tmp.name)/'history.db'
 def tearDown(self):m.DB=self.old;self.tmp.cleanup()
 def test_individual_usdt_cap_not_token_price_or_total_supply(self):
  listing={'peggedAssets':[dict(id='1',symbol='USDT',pegType='peggedUSD',name='Tether')]}
  history=[dict(date=1577923200,totalCirculating={'peggedUSD':100},totalCirculatingUSD={'peggedUSD':98})]
  with patch.object(m,'fetch',side_effect=[json.dumps(listing),json.dumps(history)]) as fetch:
   sid,n=m.download('defillama','USDT_MCAP','2020-01-01','2020-01-03')
  self.assertTrue(fetch.call_args.args[0].endswith('?stablecoin=1'))
  self.assertEqual(m.bars(sid)[0]['close'],98)
  self.assertIsNone(m.bars(sid)[0]['volume']);self.assertIn('USD market cap',m.catalog()[0]['basis'])
 def test_usdc_uses_its_own_verified_id(self):
  listing={'peggedAssets':[dict(id='2',symbol='USDC',pegType='peggedUSD')]}
  history=[dict(date=1577923200,totalCirculatingUSD={'peggedUSD':70})]
  with patch.object(m,'fetch',side_effect=[json.dumps(listing),json.dumps(history)]) as fetch:
   m.download('defillama','USDC_MCAP','2020-01-01','2020-01-03')
  self.assertTrue(fetch.call_args.args[0].endswith('?stablecoin=2'))
 def test_open_usd_selected_instead_of_origin_dollar(self):
  listing={'peggedAssets':[dict(id='443',symbol='OUSD',pegType='peggedUSD',name='Open USD',gecko_id='open-usd'),dict(id='23',symbol='OUSD',pegType='peggedUSD',name='Origin Dollar',gecko_id='origin-dollar')]}
  history=[dict(date=1577923200,totalCirculatingUSD={'peggedUSD':80})]
  with patch.object(m,'fetch',side_effect=[json.dumps(listing),json.dumps(history)]) as fetch:
   sid,n=m.download('defillama','OUSD_MCAP','2020-01-01','2020-01-03')
  self.assertTrue(fetch.call_args.args[0].endswith('?stablecoin=443'))
  self.assertEqual(m.bars(sid)[0]['close'],80)
 def test_origin_dollar_does_not_satisfy_open_usd(self):
  listing={'peggedAssets':[dict(id='23',symbol='OUSD',pegType='peggedUSD',name='Origin Dollar',gecko_id='origin-dollar')]}
  with patch.object(m,'fetch',return_value=json.dumps(listing)):
   with self.assertRaisesRegex(ValueError,'identity'):m.download('defillama','OUSD_MCAP','2020-01-01','2020-01-03')
 def test_wrong_stablecoin_identity_rejected(self):
  with patch.object(m,'fetch',return_value=json.dumps({'peggedAssets':[dict(id='99',symbol='USDC',pegType='peggedUSD')]})):
   with self.assertRaisesRegex(ValueError,'identity'):m.download('defillama','USDC_MCAP','2020-01-01','2020-01-03')
if __name__=='__main__':unittest.main()
