Limits for Large Minute-Based Historical Bar Requests
In order to provide the best overall experience with bar charts for all of our clients, the bar charts API imposes some limits on requests for large amounts of bar history. These limits apply only to bar requests where the unit is minute, and they are applied in addition to the overall rate limit of 500 bar chart requests per 5 minutes.

A single intraday bars request can return a maximum of 57,600 bars, regardless of the bar interval. This limit applies to both "bars back" and "date range" requests.

A single "bars back" request can request a maximum of 500,000 minutes of bar data, where total minutes = barsback * interval.

A single date range request can request a maximum of three calendar years of minute bar data.

The total amount of history requested per minute is limited by a credits-based system, where each user is provided a periodic allocation of history credits.

These limits are discussed in more detail below.

If you need to request more history than is allowed by the per-request limits, you can divide large requests into smaller requests and save the data locally. If you exceed the limit on total history per minute, you can slow down the pace of requests in order to stay within the limit.

Limit on Bars Back Requests
A single "bars back" request can request a maximum of 500,000 minutes of bar data.

The total number of minutes requested can be calculated by multiplying the bars back by the interval. For example, a request with barsback=3000 and interval=60 will request 180,000 total minutes, which is below the limit. However, a request with barsback=10000 and interval=60 will request 600,000 minutes, which exceeds the limit for a single minute bars request.

If you need more than 500,000 minutes of history, split the request into multiple requests and save the results in memory or a file. You may find that date range requests are more convenient when you need to split a large request into multiple smaller ranges.

Limit on Date Range Requests
When unit=minute, a single date range request can request a maximum of 3 calendar years of bar data.

For example, a request with firstdate=2023-01-01T00:00:00Z and lastdate=2025-07-31T20:00:00Z will request two years and seven months of bar data, which is below the limit. However, a request with firstdate=2021-01-01T00:00:00Z and lastdate=2025-07-31T20:00:00Z will request over four years of data, which exceeds the limit for a single minute bars request.

If you need more than three years of history, split the request into multiple requests and save the results in memory or a file.

Credit-Based History Limit
The total amount of history that each user can request per minute is limited by a periodic allocation of "bar history credits." Each credit is defined as follows:

For bar requests that use the barsback parameter, 1 credit = 100,000 one minute bars. The number of credits used by a request can be calculated as barsback * interval / 100000. Fractional credits greater than 0.25 count toward the rate limit with 1/100th precision, so round the result down to two decimals and discard any remaining decimals. Credits of 0.25 or less are treated as zero.

For bar requests that use the firstdate parameter, 1 credit = 365 calendar days. The number of credits used by a request can be calculated as (days_between(firstdate, lastdate)+1) / 365. If lastdate is omitted from the request, use the current date instead. Round the result down to two decimals, and treat credits of 0.25 or less as zero.

Note: Because credits of 0.25 or less are treated as zero, small history requests will not count toward this rate limit.

A client starts with 200 history credits, and each bar request uses up credits (including fractional credits greater than 0.25) as specified in the calculations above. Credits are replenished at the rate of 200 credits per minute (evenly spaced) but will never exceed the maximum of 200 credits. When all the credits have been used, any additional history requests will return a rate limit error (HTTP status 429) until sufficient credits have been replenished to fulfill the request.

Most applications of the bar charts API are unlikely to be impacted by the historical rate limit. However, if an application makes frequent requests for large amounts of historical data, the rate limit may be hit. The following sections provide information to help you analyze and revise your bar requests if this occurs.

Example
Consider the following requests:

/v3/marketdata/barcharts/AAPL?unit=minute&interval=60&barsback=2000

/v3/marketdata/stream/barcharts/AAPL?unit=minute&interval=120&barsback=500

/v3/marketdata/barcharts/AAPL?unit=minute&interval=5&barsback=3000

/v3/marketdata/barcharts/AAPL?unit=minute&interval=30&firstdate=2023-01-01&lastdate=2024-06-30

The credits used by these requests can be calculated as follows:

2000 * 60 / 100000 = 1.20

500 * 120 / 100000 = 0.60

3000 * 5 / 100000 = 0.15 = 0 since it is less than 0.25

547 / 365 = 1.49 (since there are 547 days from 2023-01-01 to 2024-06-30, inclusive)

Note: Credits are rounded down to two decimals; any decimals after the first two are dropped.

The total credits used by these requests is 3.29, which is far less than the 200 credits allocation for a 1 minute period. Even if an application made all of these requests for every symbol in the Dow 30, the total credits used would be slightly less than 100, so it would not exhaust the credits. However, if an application made these requests for all symbols in the NASDAQ 100, the total credits used would exceed the 1 minute allocation; thus, these requests would need to be spread over a period greater than 1 minute to stay under the rate limit.

How to Avoid Being Rate Limited
For applications that need to request large amounts of bar history, the following recommendations can help them stay below the historical rate limit:

If you need both historical and real-time data, make a streaming bar request and keep the stream open. This allows the application to fetch history and then get real-time bars without needing to repeat the request multiple times.

Avoid repeated requests for the same historical data. Either use a streaming request, or make a non-streaming request and save the data in memory or a file so that it can be reused for the current day.

If the application needs to work with more symbols and historical data than can be fetched during a 1 minute period, add a delay or other mechanism to pace the requests so that they stay within the rate limit. If this data is needed before a specific time (e.g. market open), be sure to schedule the historical data retrieval early enough to fetch all of the required data before that time.