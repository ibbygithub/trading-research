there are two version of tradestation downloader used to download different tradestation historical data. they were orginally setup to download different time frames like 3 minutes or daily.
the need now is just to download 1 minute time frame with the following minium data fields: TimeStamp,High,Low,Open,Close,TotalVolume,DownTicks,DownVolume,TotalTicks,UpTicks,UpVolume
Both of these scripts require a config.py file that holds:
client_id = "xxxx"
client_secret = "xxxx"
refresh_token = "xxx"
These keys should be stored in a .env file instead of a config.py file. 
