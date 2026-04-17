Default API Key Configuration
TradeStation API Keys come with a specified set of configurations related to authentication and key usage. Unless you have already communicated your specific application requirements to TradeStation Client Experience, you will receive an API Key with the default configuration. If you need to make any configuration changes to your API Key, please contact Client Experience to request this change.

Default API Key Configuration
Application Type and Authentication Flow: TradeStation API Keys by default are set as Regular Web App type and therefore use the standard Auth Code Flow. If you would like to use the Auth Code Flow with PKCE for a Single Page App (SPA) or Native App, contact Client Experience to request this change. Once changed, you will need to follow the documentation for Auth Code Flow with PKCE for authorization.

Refresh Tokens: Refresh Tokens will be enabled on your default API Key, but they will be set to non-expiring. Navigate to the Refresh Tokens page to learn more about usage and implications of these settings. You can contact Client Experience to change the Refresh Roken setting to expire and rotate every 40 minutes for increased application security.

Scopes: Applications will be configured by default to have access to the following TradeStation API scopes: MarketData, ReadAccount, Trade. Contact Client Experience to inquire about adding additional TradeStation API scopes to your API Key. There are some additional required and optional scopes not related to the Tradestation API. See the Scopes page for more information.

Account Access: Unless you are building an application to be deployed and used by the public as one of TradeStation’s partners, your API access will be restricted to the accounts under your TradeStation login. You should confirm with Client Experience which TradeStation logins can be used with your application. You can contact Client Experience to add or remove a login from your API Key (limit of 15 per application, contact Client Experience if you would like to become a partner to remove this limit).

Application URIs: Applications can be configured with many different URI/URL's for security and special usage purposes. The only required option is the Allowed Callback URLs. The list of configurable URI options is:

Allowed Login URI: In some scenarios, Auth0 will need to redirect to your application’s login page. This URI needs to point to a route in your application that should redirect to your tenant’s /authorize endpoint. Learn More

Allowed Callback URLs: After the user authenticates we will only call back to any of these URLs. You can specify multiple valid URLs to handle different environments like QA or testing. Make sure to specify the protocol (https://) for deployed applications, otherwise the callback may fail in some cases. With the exception of custom URI schemes for native clients, all callbacks should use protocol https://. TradeStation API Keys will be configured by default to the following localhost ports for local development:

http://localhost
http://localhost:80
http://localhost:3000
http://localhost:3001
http://localhost:8080
http://localhost:31022
Allowed Logout URLs: A set of URLs that are valid to redirect to after logout from Auth0. After a user logs out from Auth0, you can redirect them with the returnTo query parameter. The URL that you use in returnTo must be listed here. You can use the star symbol as a wildcard for subdomains ( *.google.com). Query strings and hash information are not taken into account when validating these URLs. Read more about this process in the Logout page. TradeStation API Keys will be configured by default to the following localhost ports for local development:

http://localhost/logout
http://localhost:80/logout
http://localhost:3000/logout
http://localhost:3001/logout
http://localhost:8080/logout
http://localhost:31022/logout
Allowed Web Origins: List of allowed origins for use with Cross-Origin Authentication, Device Flow , and Web Message Response Mode , in the form of {<scheme> "://" <host> [ ":" <port> ]} , such as https://login.mydomain.com or http://localhost:3000. You can use wildcards at the subdomain level (e.g.: https://*.contoso.com). Query strings and hash information are not taken into account when validating these URLs.

Allowed Origins (CORS): Allowed Origins are URLs that will be allowed to make requests from JavaScript to Auth0 API (typically used with CORS). By default, all your callback URLs will be allowed. This field allows you to enter other origins if you need to. You can use wildcards at the subdomain level (e.g.: https://*.contoso.com). Query strings and hash information are not taken into account when validating these URLs.

If you need to add, update, or delete any of these URI/URL options on your API Keys, please contact Client Experience to request these adjustments.

Additional API Key Actions
There are additional API Key actions that you can request by contacting Client Experience:

Disable API Key: Disabling your key prevents users from receiving new Access Tokens through authentication or Refresh Tokens.

Enable API Key: Re-enabling the API Key will allow users to obtain new Access Tokens through authentication or Refresh Tokens. Please note that any non-expiring Refresh Tokens that were generated before an API Key is disabled will be usable once again after the application is enabled. Therefore, disabling and re-enabling API Keys is not a secure way of handling compromised credentials.

Rotate API Key Client Secret: You can request that your API Key Client Secret be rotated. Non-expiring Refresh Tokens that were generated prior to rotating the Client Secret will still be usable after rotating the secret.