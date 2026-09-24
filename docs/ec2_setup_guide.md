# EC2 Database Setup Guide

How to install Docker on an AWS EC2 instance, run a SQL Server container, and ingest the cold-chain dataset.

---

## 1. Install Docker on EC2

SSH into your EC2 instance and run:

```bash
# Update packages & install Docker
sudo apt update && sudo apt install -y docker.io

# Start Docker and enable it on boot
sudo systemctl start docker
sudo systemctl enable docker

# Let your user run Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
```

---

## 2. Run the SQL Server Container

```bash
docker run \
  -v mssql_data:/var/opt/mssql \
  -e "ACCEPT_EULA=Y" \
  -e "MSSQL_SA_PASSWORD=<YOUR_PASSWORD>" \
  -p 1433:1433 \
  --name legacy-mssql \
  --restart unless-stopped \
  -d mcr.microsoft.com/mssql/server:2022-latest
```

| Flag | What it does |
|---|---|
| `-v mssql_data:/var/opt/mssql` | Saves data to a volume so it survives container restarts |
| `-e "MSSQL_SA_PASSWORD=..."` | Sets the admin (`sa`) password |
| `-p 1433:1433` | Maps SQL Server port from container to the EC2 host |
| `--restart unless-stopped` | Auto-restarts the container if EC2 reboots |
| `-d` | Runs the container in the background |

Wait ~15 seconds, then verify it's running:

```bash
docker ps
```

---

## 3. Install ODBC Driver 18

Required for Python to connect to SQL Server.

```bash
# Add Microsoft's signing key & package repo
curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc

# Add repo (use 24.04 for Ubuntu 24.04+)
echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/24.04/prod noble main" \
  | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Install the driver
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18

# Verify
odbcinst -q -d
# Expected output: [ODBC Driver 18 for SQL Server]
```

---

## 4. Open Port 1433 (AWS Security Group)

Your local machine needs to reach the database on EC2.

1. **AWS Console → EC2 → Security Groups** → select your instance's SG
2. **Edit Inbound Rules → Add Rule:**

| Type | Port | Source |
|---|---|---|
| Custom TCP | 1433 | My IP |

3. Save rules.

---

## 5. Configure & Run the Ingestion Script

### Option A: Run from your local machine (easiest)

If port 1433 is open (Step 4), just update `.env` on your local machine:

```env
SQL_ADMIN_USER=sa
SQL_ADMIN_PASSWORD=<YOUR_PASSWORD>
SQL_SERVER_HOST=<EC2_PUBLIC_IP>
SQL_SERVER_PORT=1433
```

Then run:

```bash
python scripts/ingest_legacy_data.py
```

Your local script connects over the internet to the EC2 database. No files need to be on EC2.

---

### Option B: Run directly on EC2 (recommended for production)

The EC2 instance doesn't have your project files. You need to transfer them, install Python, and then run.

#### B.1 — Transfer project files to EC2

From your **local machine** terminal, use `scp` to copy the necessary files:

```bash
# Create a project folder on EC2
ssh -i "your-key.pem" ubuntu@<EC2_PUBLIC_IP> "mkdir -p ~/cold-chain-logistics/scripts ~/cold-chain-logistics/data/raw"

# Copy the ingestion script
scp -i "your-key.pem" scripts/ingest_legacy_data.py ubuntu@<EC2_PUBLIC_IP>:~/cold-chain-logistics/scripts/

# Copy the CSV dataset (~15 MB)
scp -i "your-key.pem" data/raw/dynamic_supply_chain_logistics_dataset.csv ubuntu@<EC2_PUBLIC_IP>:~/cold-chain-logistics/data/raw/

# Copy requirements and .env
scp -i "your-key.pem" requirements.txt ubuntu@<EC2_PUBLIC_IP>:~/cold-chain-logistics/
scp -i "your-key.pem" .env ubuntu@<EC2_PUBLIC_IP>:~/cold-chain-logistics/
```

> **What is `scp`?** Secure Copy — it transfers files over SSH from your local machine to the remote server.

#### B.2 — SSH into EC2

```bash
ssh -i "your-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

#### B.3 — Install Python and pip

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

#### B.4 — Create a virtual environment and install dependencies

```bash
cd ~/cold-chain-logistics

# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install all required packages
pip install -r requirements.txt
```

> **What is a venv?** An isolated Python environment so packages don't conflict with the system Python.

#### B.5 — Update `.env` to point at localhost

Since the script is now running **on the same machine** as the Docker container, the host should be `localhost`:

```bash
nano .env
```

Make sure it reads:

```env
SQL_ADMIN_USER=sa
SQL_ADMIN_PASSWORD=<YOUR_PASSWORD>
SQL_SERVER_HOST=localhost
SQL_SERVER_PORT=1433
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

#### B.6 — Run the ingestion

```bash
python scripts/ingest_legacy_data.py
```

Expected output:

```
Loading CSV from /home/ubuntu/cold-chain-logistics/data/raw/dynamic_supply_chain_logistics_dataset.csv...
Connecting to legacy MSSQL Database...
Ingesting into TBL_SC_FLEET_HIST_RAW. This may take a minute...
[OK] Legacy data ingestion complete!
```

This reads the CSV, maps 9 columns into a legacy-style schema, and writes them to `dbo.TBL_SC_FLEET_HIST_RAW` on the local Docker SQL Server.

---

## 6. Verify

From your local machine or inside EC2:

```bash
# Inside EC2 (via Docker)
docker exec legacy-mssql /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "<YOUR_PASSWORD>" -C \
  -Q "SELECT COUNT(*) AS total_rows FROM dbo.TBL_SC_FLEET_HIST_RAW;"
```

Expected: `32065` rows.
