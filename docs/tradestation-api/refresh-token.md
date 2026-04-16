Refresh Tokens
danger
Refresh Tokens must be stored securely.

danger
Access tokens are valid for 20 minutes. For applications or programs that are running and making a large number of requests, a new access token should not be obtained for each request. A new access token should only be obtained when the current one is approaching expiration or has expired.

danger
Making a Refresh Token revocation request will revoke ALL Refresh Tokens for that API key.

info
The offline_access scope must be included in the authorization request scope parameter to allow for Refresh Tokens.

Refresh Token
Access Tokens have a lifetime of 20 minutes. After an Access Token has expired or it becomes invalid, the Refresh Token grant type is used in order to obtain a new Access Token. By default, Refresh Tokens of TradeStation API Keys will be valid indefinitely. You can request that they are configured to expire and rotate every 30 minutes for increased application security by contacting Client Experience. There is a 24-hour absolute lifetime imposed when using rotating Refresh Tokens, thereby requiring users to re-sign in every 24 hours.

To refresh your Access Token, make a POST request to the /oauth/token endpoint, using grant_type=refresh_token and header content-type:application/x-www-form-urlencoded. If your TradeStation API Key is configured to expiring and rotating Refresh Tokens, you will receive a new Refresh Token in the response, in addition to the new Access Token.

Token URL:

https://signin.tradestation.com/oauth/token
Parameters:

Parameter	Required/Optional	Value
grant_type	required	Set this to refresh_token.
client_id	required	The client application’s API Key.
client_secret	optional	The secret for the client application’s API Key. Required for standard Auth Code Flow. Not required for Auth Code Flow with PKCE.
refresh_token	required	The refresh_token received with the access_token.
Example Request:

curl --request POST \
  --url 'https://signin.tradestation.com/oauth/token' \
  --header 'content-type: application/x-www-form-urlencoded' \
  --data 'grant_type=refresh_token' \
  --data 'client_id=YOUR_CLIENT_ID' \
  --data 'client_secret=YOUR_CLIENT_SECRET' \
  --data 'refresh_token=YOUR_REFRESH_TOKEN'

Example Response:

{
  "access_token": "eGlhc2xv...MHJMaA",
  "expires_in": 1200,
  "scope": "openid offline_access",
  "id_token": "vozT2Ix...wGVFPQ",
  "token_type": "Bearer"
}

Revoking Refresh Tokens
You can revoke Refresh Tokens in case they become compromised. To revoke a Refresh Token, make a POST request to the /oauth/revoke endpoint. Even though the request only passes in one Refresh Token, the request, as noted above, will revoke ALL valid Refresh Tokens for the API key, not just the single Refresh Token passed in with the request.

Read more about the Refresh Token revocation process here.

Token URL:

https://signin.tradestation.com/oauth/revoke
Parameters:

Parameter	Required/Optional	Value
client_id	required	The client application’s API Key.
client_secret	optional	The secret for the client application’s API Key.
refresh_token	required	A valid refresh_token.
Example Request:

curl --request POST \
  --url 'https://signin.tradestation.com/oauth/revoke' \
  --header 'content-type: application/json' \
  --data '{ "client_id": "{YOUR_CLIENT_ID}", "client_secret": "{YOUR_CLIENT_SECRET}", "token": "{YOUR_REFRESH_TOKEN}" }'


Example Response:

200 OK