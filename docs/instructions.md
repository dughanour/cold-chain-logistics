# Ingesting data

- Download the dataset from 'data\source\data.txt'
- Create EC2 instance > docker container > mcr.microsoft.com/mssql/server:2022-latest
- Spin up the legacy MSSQL Server
```
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=FdeEnterprisePass123!" -p 1433:1433 --name legacy-mssql -d mcr.microsoft.com/mssql/server:2022-latest

# or multi-line in windows 
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=FdeEnterprisePass123!" ^
   -p 1433:1433 --name legacy-mssql ^
   -d mcr.microsoft.com/mssql/server:2022-latest

# or multi-line unix
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=FdeEnterprisePass123!" \
   -p 1433:1433 --name legacy-mssql \
   -d mcr.microsoft.com/mssql/server:2022-latest

# or multi-line with volume inside EC2
docker run -v mssql_data:/var/opt/mssql \
  -e "ACCEPT_EULA=Y" \
  -e "MSSQL_SA_PASSWORD=FdeEnterprisePass123!" \
  -p 1433:1433 \
  --name legacy-mssql \
  -d mcr.microsoft.com/mssql/server:2022-latest
```

- Install the req > uv pip install -r requirements.txt
- python scripts\ingest_legacy_data.py
- Test : docker exec legacy-mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "FdeEnterprisePass123!" -C -Q "SELECT TOP 5 * FROM dbo.TBL_SC_FLEET_HIST_RAW;"



