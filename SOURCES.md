# Primary sources

- CCXT: https://github.com/ccxt/ccxt and its unified OHLCV API documentation.
- Binance XMR delisting: https://www.binance.com/en/support/announcement/detail/f73b083ba6834771b07dbe5319917ae5
- Yahoo downloader: https://github.com/ranaroussi/yfinance
- FRED US10Y definition: https://fred.stlouisfed.org/series/DGS10
- FRED WREPO definition: https://fred.stlouisfed.org/series/WREPO
- ICE DXY formula/weights: https://www.theice.com/publicdocs/futures_us/ICE_Dollar_Index_FAQ.pdf
- DefiLlama stablecoin data: https://github.com/DefiLlama/peggedassets-server

DXY reconstruction uses the official six-currency exponents and constant with FRED FX observations. It is explicitly labelled because observation times differ from ICE index closes. If only the four user-authorized currencies are available, their absolute weights total 0.867; they are renormalized and rebased to 100 at the first shared local observation date. No inferred component highs/lows or volume are created.

US10Y uses the FRED constant-maturity yield. WREPO is the weekly average Fed repurchase-agreement asset series, not reverse repo. Continuous commodity futures use Yahoo's series and do not promise TradingView rollover parity.

- Binance public-data endpoint: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- Binance historical archives: https://github.com/binance/binance-public-data
- Dukascopy historical export: https://www.dukascopy.com/api/data/get/historical-data-export
- Google historical export limits: https://support.google.com/docs/answer/3093281?hl=en
