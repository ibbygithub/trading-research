Overview
The TradeStation API Rate Limits on the number of requests a given user & client can make to the API in order to ensure fairness between users and prevent abuse to our network. Each API Key is allocated quota settings upon creation. These settings are applied on a per-user basis. If the quota is exceeded, an HTTP response of 429 Too Many Requests will be returned. Quotas are reset on a 5-minute interval based on when the user issued the first request.

note
We recommend using streaming services if available.

Rate Limiting Overview
Understanding Rate Limits
Rate limiting is implemented across all TradeStation API endpoints to ensure system stability and fair resource allocation among all users. Each API key receives specific quota allocations that are enforced on a per-user basis across different resource categories.

Default Rate Limit Configuration
TradeStation API Keys come with predefined rate limit configurations that vary by resource type and endpoint category. Unless you have specific application requirements that have been communicated to TradeStation Client Experience, your API key will use the standard rate limiting configuration.

Key Rate Limiting Concepts
Quota Allocation: Each API key is allocated specific request quotas based on the resource category being accessed. These quotas are designed to provide sufficient capacity for typical application usage while preventing system abuse.

Time Windows: Rate limits operate within fixed time intervals (typically 5-minute windows for most resources, 1-minute for others). Once a quota is exceeded, all subsequent requests will return 429 Too Many Requests until the window resets.

Resource Categories: Different API endpoints are grouped into resource categories, each with its own quota and interval settings. This allows for more granular control over different types of API usage.

Concurrent Limits: Some resources, particularly streaming endpoints, have concurrent connection limits in addition to request rate limits.

Best Practices for Rate Limit Management
Use Streaming Services: When available, streaming services provide real-time data without consuming request quotas, making them the preferred option for continuous data feeds.

Implement Exponential Backoff: When receiving 429 responses, implement exponential backoff retry logic to avoid overwhelming the system during high-traffic periods.

Monitor Usage Patterns: Track your application's request patterns to identify potential quota issues before they impact your users.

Cache Responses: Implement appropriate caching strategies to reduce unnecessary API calls and optimize quota usage.

Request Quota Adjustments: If your application consistently exceeds standard quotas, contact Client Experience to discuss potential quota adjustments based on your specific use case.

Rate Limit Response Headers
The TradeStation API includes response headers that provide information about your current rate limit status:

Rate limit remaining: Number of requests remaining in the current window
Rate limit reset: Timestamp when the current window will reset
Rate limit total: Total quota allocated for the resource category
Common Rate Limiting Scenarios
Market Data Applications: Applications requiring frequent market data updates should prioritize streaming endpoints over snapshot requests to optimize quota usage.

Portfolio Management Tools: Applications that need regular account, position, and balance updates should implement efficient polling strategies and consider using streaming services where available.

Algorithmic Trading: High-frequency trading applications may require custom quota configurations and should contact Client Experience to discuss specialized rate limiting arrangements.

Resource Categories
The rate limit applies to the following resource-categories:

Resource-Category	Quota	Interval
Accounts	250	5-minute
Order Details	250	5-minute
Balances	250	5-minute
Positions	250	5-minute
Quote Change Stream	500	5-minute
Barchart Stream	500	5-minute
TickBar Stream	500	5-minute
Each Option Endpoint	90	1-minute
Quote Snapshot	30	1-minute
MarketDepth Stream*	30	1-minute
MarketDepth Stream*	10	concurrent
Option Quote Stream	10	concurrent
Option Chain Stream	10	concurrent
Order Stream	40	concurrent
Order Stream by Order Id	40	concurrent
Positions Stream	40	concurrent
*The MarketDepth rate limit is a combined amount that applies to Quotes and Aggregate streams.

Intervals
Quotas have "Windows" that last for a limited time interval (generally 5-minutes). Once the user has exceeded the maximum request count, all future requests will fail with a 429 error until the interval expires. Rate Limit intervals do not slide based upon the number of requests, they are fixed at a point in time starting from the very first request for that category of resource. After the interval expires, the cycle will start over at zero and the user can make more requests.

Example A
A user logs into the TradeStation WebAPI with their application and issues a request to /v3/brokerage/accounts. As a result, the request quota is incremented by one for the Accounts resource-category. The user then issues 250 more requests immediately to /v3/brokerage/accounts. The last request fails with 429 Too Many Requests. All subsequent requests continue to fail until the 5-minute interval expires from the time of the very first request.

Example B
A user logs into the TradeStation WebAPI with their application and issues a request to /v3/brokerage/accounts/123456782/positions. As a result, the request quota is incremented by one for the Positions resource-category. The user then immediately issues the same request 250 more times. The last request fails with 429 Too Many Requests. All subsequent requests continue to fail until the 5-minute interval expires from the time of the first request.

Example Throttled Request

GET https://api.tradestation.com/v3/brokerage/accounts/123456782/positions HTTP/1.1
Host: api.tradestation.com
Authorization: bearer eE45VkdQSnlBcmI0Q2RqTi82SFdMSVE0SXMyOFo5Z3dzVzdzdk
Accept: application/json

Example Failed Response

HTTP/1.1 429 Too Many Requests
Content-Length: 55
Date: Thu, 04 Feb 2021 21:18:07 GMT

{"Error":"TooManyRequests","Message":"Rate quota exceeded"}