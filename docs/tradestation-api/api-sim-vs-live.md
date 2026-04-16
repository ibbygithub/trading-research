SIM vs. LIVE
We also offer a Simulator(SIM) API for "Paper Trading" that is identical to the Live API in all ways except it uses fake trading accounts seeded with fake money and orders are not actually executed - only simulated executions occur with instant "fills".

:::

To access the SIM environment, you must change your base-url from live url (https://api.tradestation.com/v3) to sim url:

https://sim-api.tradestation.com/v3

danger
TradeStation is not liable for mistakes made by applications that allow users to switch between SIM and Live environments.

Why offer a Simulator?
Transactional API calls such as Order Execution offers users or applications the ability to experiment within a Simulated trading system so that real accounts and money are not affected and trades are not actually executed.

Other potential use-cases:

Learning how to use applications via Paper Trading.
Exploring TradeStation API behavior without financial ramifications
Testing apps and websites before making them Live to customers
Enabling users to "Try-before-they-buy" with apps that use the TradeStation API
Hosting trading competitions or games