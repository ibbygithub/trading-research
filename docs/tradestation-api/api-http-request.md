HTTP Requests
All API access is over HTTPS, and accessed from https://api.tradestation.com or https://sim-api.tradestation.com (sim). All data is sent and received as JSON (this does not include authentication related requests).

Example Request:

curl --request GET \
  --url 'https://api.tradestation.com/v3/marketdata/barcharts/MSFT?interval=1&unit=Daily&barsback=2&startdate=2020-12-05T21:00:00Z' \
  --header 'Authorization: Bearer TOKEN'

{"Bars":[{"High":"216.38","Low":"213.65","Open":"214.61","Close":"214.24","TimeStamp":"2020-12-03T21:00:00Z","TotalVolume":"25120922","DownTicks":114646,"DownVolume":14430027,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":false,"TotalTicks":226992,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":112346,"UpVolume":10690895,"Epoch":1607029200000},{"High":"215.38","Low":"213.18","Open":"214.22","Close":"214.36","TimeStamp":"2020-12-04T21:00:00Z","TotalVolume":"24666039","DownTicks":110196,"DownVolume":13201417,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":true,"TotalTicks":218338,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":108142,"UpVolume":11464622,"Epoch":1607115600000}]}


Common Conventions
Blank fields may either be included as null or omitted, so please support both.