HTTP Streaming
info
Multiple concurrent streams can result in a large amount of data and may pose issues for lower-bandwidth connections.

The TradeStation API offers HTTP Streaming responses for some specialized resources including accounts, positions, barcharts, quote changes, option chains, and option spread quotes (including single options). These streams conform to RFC2616 for HTTP/1.1 Streaming with some slight modifications.

The HTTP streaming mechanism keeps a request open indefinitely. It never terminates the request or closes the connection, even after the server pushes data to the client. This mechanism significantly reduces the network latency because the client and the server do not need to open and close the connection.

The basic life cycle of an application using HTTP streaming is as follows:

The client makes an initial request and then waits for a response.

The server defers the response to a poll request until an update is available, or until a particular status or timeout has occurred.

Whenever an update is available, the server sends it back to the client as a part of the response.

The data sent by the server does not terminate the request or the connection. The server returns to step 3.

The HTTP streaming mechanism is based on the capability of the server to send several pieces of information in the same response, without terminating the request or the connection.

Source: RFC6202, Page 7.

HTTP Streaming resources are identified under in this documentation as such, all other resources conform to the HTTP Request pattern instead.

The HTTP Streaming response is returned with the following headers:

```
Transfer-Encoding: chunked
Content-Type: application/vnd.tradestation.streams.v2+json
```

In case of orders and positions the HTTP Streaming response is returned with the following headers:

```
Transfer-Encoding: chunked
Content-Type: application/vnd.tradestation.streams.v3+json
```

Note: The Content-Length header is typically omitted since the response body size is unknown.

Streams consist of a series of chunks that contain individual JSON objects to be parsed separately rather than as a whole response body.

One unique thing about TradeStation's HTTP Streams is they also can terminate unlike a canonical HTTP/1.1 Stream.

In the case of ERROR, it will often be followed by an error message like:

{"Symbol":"AAPL","Error":"DualLogon"}

In this case, the HTTP client must terminate the HTTP Stream and end the HTTP Request lifetime as a result of this message. The client application may add a delay before re-requesting the HTTP Stream.

In case of vnd.tradestation.streams.v3+json, stream also returns additional Stream Status object. After initial snapshot EndSnapshot status is sent:

{"StreamStatus": "EndSnapshot"}

Before stream is terminated by server GoAway status is sent indicating thta clinet must restart the stream:

{"StreamStatus": "GoAway"}

How to handle HTTP Chunked Encoded Streams
Healthy chunked-encoded streams emit variable length chunks that contain parsable JSON.

For example:

GET https://api.tradestation.com/v3/marketdata/stream/barcharts/MSFT?interval=1&unit=minute

HTTP/1.1 200 OK
Date: Tue, 02 Mar 2021 21:13:00 GMT
Content-Type: application/vnd.tradestation.streams.v2+json
Transfer-Encoding: chunked
Connection: keep-alive

141
{"High":"233.87","Low":"233.75","Open":"233.87","Close":"233.75","TimeStamp":"2021-03-02T22:13:00Z","TotalVolume":"71551","DownTicks":1,"DownVolume":198,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":false,"TotalTicks":2,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":1,"UpVolume":71353,"Epoch":1614723180000}

13a
{"High":"233.88","Low":"233.88","Open":"233.88","Close":"233.88","TimeStamp":"2021-03-02T22:14:00Z","TotalVolume":"100","DownTicks":0,"DownVolume":0,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":true,"TotalTicks":1,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":1,"UpVolume":100,"Epoch":1614723240000}



Typically this will stream forever, unless a network interruption or service disruption occurs. It is up to the client to properly handle stream lifetime and connection closing.

How to parse JSON chunks
In order to process these chunks, API consumers should first read the response buffer, then de-chunk the plain-text strings, and finally identify new JSON objects by applying tokenizing techniques to the resulting text stream using either a streaming JSON parser, Regex, a lexer/parser, or brute-force string indexing logic.

A simple but effective technique is after de-chunking to simply parse based upon the \n (newline character) delimiter written to the end of each JSON object. However, a more robust solution is less likely to break later.

Variable Length JSON Chunking
As a developer, be careful with how you parse HTTP Streams, because the API’s or intermediate proxies may chunk JSON objects many different ways.

Using HTTP streaming, several application messages can be sent within a single HTTP response. The separation of the response stream into application messages needs to be performed at the application level and not at the HTTP level. In particular, it is not possible to use the HTTP chunks as application message delimiters, since intermediate proxies might “re-chunk” the message stream (for example, by combining different chunks into a longer one). This issue does not affect the HTTP long polling technique, which provides a canonical framing technique: each application message can be sent in a different HTTP response.

Source: RFC6202, Section 3.2

Translation: Be prepared for JSON objects that span chunks. You may see chunks with varying numbers of JSON objects, including:

"exactly 1" JSON object per chunk
“at least 1” JSON object per chunk
1 JSON object split across 2 or more chunks
Example of 2 JSON objects in 1 chunk:

GET https://api.tradestation.com/v3/marketdata/stream/barcharts/MSFT?interval=1&unit=minute

HTTP/1.1 200 OK
Date: Tue, 02 Mar 2021 22:06:00 GMT
Content-Type: application/vnd.tradestation.streams.v2+json
Transfer-Encoding: chunked
Connection: keep-alive

27a
{"High":"233.65","Low":"233.64","Open":"233.65","Close":"233.64","TimeStamp":"2021-03-02T22:07:00Z","TotalVolume":"1245","DownTicks":2,"DownVolume":1245,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":false,"TotalTicks":2,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":0,"UpVolume":0,"Epoch":1614722820000}
{"High":"233.98","Low":"233.85","Open":"233.98","Close":"233.85","TimeStamp":"2021-03-02T22:12:00Z","TotalVolume":"920","DownTicks":2,"DownVolume":420,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":false,"TotalTicks":3,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":1,"UpVolume":500,"Epoch":1614723120000}



Example of 1 JSON objects split across 2 chunks:

GET https://api.tradestation.com/v3/marketdata/stream/barcharts/MSFT?interval=1&unit=minute

HTTP/1.1 200 OK
Date: Tue, 03 Mar 2021 16:29:00 GMT
Content-Type: application/vnd.tradestation.streams.v2+json
Transfer-Encoding: chunked
Connection: keep-alive

6c
{"High":"231.49","Low":"231.37","Open":"231.4","Close":"231.46","TimeStamp":"2021-03-03T16:30:00Z","TotalVol
d8
ume":"24059","DownTicks":100,"DownVolume":14560,"OpenInterest":"0","IsRealtime":false,"IsEndOfHistory":false,"TotalTicks":171,"UnchangedTicks":0,"UnchangedVolume":0,"UpTicks":71,"UpVolume":9499,"Epoch":1614789000000}



This is allowed by the HTTP/1.1 specification, but can be confusing or lead to bugs in client applications if you try to depend parsing JSON along the HTTP chunk-boundaries because even if it works during testing, later if users connect from a different network, it may change the chunking behavior.

For example, if you are at a coffee shop with wifi which employs an HTTP Proxy, then it may buffer the stream and change the chunking boundary from 1 JSON object per chunk, to splitting each JSON object across 2 or 3.

In fact, the HTTP/1.1 spec clearly advises developers of proxies to always “re-chunk” HTTP Streams, so this is almost a guarantee to happen in the wild.

HTTP Streaming API consumers should be prepared to support all variations.