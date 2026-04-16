Scopes
Overview
There are two different types of scopes that are used during the authorization flow to receive an Access Token. One set of scopes are related to different areas of access of the TradeStation API. The other relevant scopes are related to obtaining Refresh Tokens and ID Tokens.

TradeStation API Scopes:
TradeStation API Keys are configured by default with MarketData, ReadAccount, Trade, and OptionSpreads. You can contact Client Experience to inquire about adding additional TradeStation API scopes to your API Key.

Scopes	Default/Available by Request	Value
MarketData	Default	Requests access to lookup or stream Market Data.
ReadAccount	Default	Requests access to view Brokerage Accounts belonging to the current user.
Trade	Default	Requests access to execute orders on behalf of the current user's account(s).
OptionSpreads	Default	Request access to execute options related endpoints.
Matrix	Default	Request access to execute market depth related endpoints.
Other Relevant Scopes:
These other scopes are related to the use of Refresh Tokens and ID Tokens.

Scopes	Required/Optional	Value
openid	required	Returns the sub claim, which uniquely identifies the user. In an ID Token, iss, aud, exp, iat, and at_hash claims will also be present.
offline_access	required	Allows for use of Refresh Tokens.
profile	optional	Returns claims in the ID Token that represent basic profile information, including name, family_name, given_name, middle_name, nickname, picture, and updated_at.
email	optional	Returns the email claim in the ID Token, which contains the user's email address, and email_verified, which is a boolean indicating whether the email address was verified by the user.