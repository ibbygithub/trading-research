Authorization Code Grant Flow
The authorization code grant type is used to obtain both Access Tokens and Refresh Tokens and is optimized for confidential clients. Since this is a redirection-based flow, the client must be capable of interacting with the resource owner’s user-agent (typically a web browser) and capable of receiving incoming requests (via redirection) from the authorization server.

Implementation Guide
The authorization code grant type allows the end users to authenticate with TradeStation directly and authorize the Client application to make calls on their behalf. Access tokens expire 20 minutes from the time they are issued.

Step-by-Step

1. Redirect user for authentication/authorization
The client application will route the end-user to our authorization URL:

https://signin.tradestation.com/authorize
Query string parameters:

Parameter	Required/Optional	Value
response_type	required	Set this to code.
client_id	required	The client application’s API Key.
audience	required	Set this to https://api.tradestation.com.
redirect_uri	required	The redirect_uri of your application. This must be included in the list of Callback URLs that your API Key is configured with (contact Client Experience if you need to add your URL). Allowed Callback URLs are:
http://localhost
http://localhost:80
http://localhost:3000
http://localhost:3001
http://localhost:8080
http://localhost:31022
scope	required	A space-separated list of scopes (case sensitive). openid scope is always required. offline_access is required for Refresh Tokens. Example: openid profile offline_access MarketData ReadAccount Trade. See Scopes for more information.
state	recommended	An opaque arbitrary alphanumeric string value included in the initial request that we include when redirecting back to your app. This can be used to prevent cross-site request forgery attacks.
prompt	optional	When prompt=login is provided, navigating to the sign-in URL will always display a login screen. Without it, the flow may skip the login screen and redirect to the redirect_uri if browser session data reports a previously authenticated (signed-in) session.
Example Authorization URL:

https://signin.tradestation.com/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8080&audience=https://api.tradestation.com&state=STATE&scope=openid offline_access profile MarketData ReadAccount Trade Matrix OptionSpreads


The URL will take you to a TradeStation login page.

2. Client logs in with TradeStation credentials (TradeStation username and password)
Upon logging in with TradeStation credentials, a dialog is presented for the user to allow or not allow the application to make API requests on their behalf. This dialog will be displayed each time the client logs in.

If a localhost redirect_uri is used (e.g., http://localhost, http://localhost:3000), you may see a 2nd consent dialog if it is the first login or access was previously denied. Once consent is approved with this dialog, it will not be displayed again with subsequent logins (API key/login combination) unless the requested scopes are different.
CCEPT. If authorization is granted, authorization will proceed and the authorization code is returned as part of the redirect_uri (see below).

DECLINE. If authorization is declined, the request is directed back to the redirect_uri with the following error in the browser address bar:

http://localhost:8080/?error=access_denied&error_description=User%20did%20not%20authorize%20the%20request
If the user authorizes the application to make API requests on their behalf, continue following the steps below.

3. Client receives Authorization Code
Upon successful authentication, the user agent (browser) will be redirected to the URL provided, which will include an Authorization Code in the query string.

info
The number of characters in the Authorization Code is variable (not fixed-length).

Example Redirect:

HTTP/1.1 302 Found
Location: http://localhost:8080?code=AUTHORIZATION_CODE&state=xyzABC123

4. Exchange Authorization Code for Access Token, ID Token and Refresh Token
The client uses the Authorization Code to request an Access Token, ID Token and Refresh Token via the /oauth/token endpoint using the authorization_code grant type.

info
The number of characters in the Access Token is variable (not fixed-length).

This exchange is done via a POST request and the content-type header should be set to application/x-www-form-urlencoded.

Token URL:

https://signin.tradestation.com/oauth/token
Parameters:

Parameter	Required/Optional	Value
grant_type	required	Set this to authorization_code.
client_id	required	The client application’s API Key.
client_secret	required	The secret for the client application’s API Key.
code	required	authorization_code from the previous step.
redirect_uri	required	The redirect_uri of your app.
Example Request:

curl --request POST \
  --url 'https://signin.tradestation.com/oauth/token' \
  --header 'content-type: application/x-www-form-urlencoded' \
  --data 'grant_type=authorization_code' \
  --data 'client_id=YOUR_CLIENT_ID' \
  --data 'client_secret=YOUR_CLIENT_SECRET' \
  --data 'code=YOUR_AUTHORIZATION_CODE' \
  --data 'redirect_uri=http://localhost:8080'

Example Response:

{
  "access_token": "eGlhc2xv...MHJMaA",
  "refresh_token": "eGlhc2xv...wGVFPQ",
  "id_token": "vozT2Ix...wGVFPQ",
  "token_type": "Bearer",
  "scope": "openid profile MarketData ReadAccount Trade offline_access",
  "expires_in": 1200
}

ID tokens are used in token-based authentication to cache user profile information and provide it to a client application, thereby providing better performance and experience. The application receives an ID Token after a user successfully authenticates, then consumes the ID token and extracts user information from it, which it can then use to personalize the user's experience. ID Tokens are JSON web tokens (JWT) that will need to be decoded in order to extract the user information for use in your application. Please see the Other Relevant Scopes Table on the Scopes page to learn more about configuring the ID Token.

Access Tokens are set to expire after 20 minutes. Please visit the Refresh Tokens page to learn about using Refresh Tokens to renew your Access Token.