<#
.SYNOPSIS
  Publica (ou atualiza) o painel Kavria no servidor AWS Lightsail, a partir deste PC.

.DESCRIPTION
  Empacota o código, envia por SSH junto com o .env, e sobe com Docker Compose (app + Caddy/HTTPS).
  -Setup        primeira vez: instala Docker, swap e pastas no servidor.
  -SendDatabase migração: envia o banco deste PC (histórico, custos, metas e a conexão com o ML).
                ATENÇÃO: substitui o banco do servidor. Pare o servidor deste PC antes — o token
                do Mercado Livre é de uso único e as duas cópias não podem rodar juntas.

.EXAMPLE
  # primeira publicação (servidor novo) — sem o banco ainda, para testar o HTTPS
  .\deploy\aws\deploy.ps1 -Ip 18.230.10.20 -Key "$HOME\Downloads\LightsailDefaultKey-sa-east-1.pem" -Domain painel.kavria.com.br -Setup

.EXAMPLE
  # migração do banco (depois de parar o servidor deste PC)
  .\deploy\aws\deploy.ps1 -Ip 18.230.10.20 -Key "$HOME\Downloads\LightsailDefaultKey-sa-east-1.pem" -Domain painel.kavria.com.br -SendDatabase

.EXAMPLE
  # atualizações de código depois
  .\deploy\aws\deploy.ps1 -Ip 18.230.10.20 -Key "$HOME\Downloads\LightsailDefaultKey-sa-east-1.pem" -Domain painel.kavria.com.br
#>
param(
  [Parameter(Mandatory = $true)] [string]$Ip,
  [Parameter(Mandatory = $true)] [string]$Key,
  [Parameter(Mandatory = $true)] [string]$Domain,
  [switch]$Setup,
  [switch]$SendDatabase
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Remote = "ubuntu@$Ip"
$Work = Join-Path $env:TEMP "kavria2-deploy"

if (-not (Test-Path (Join-Path $Root ".env"))) { throw "Não encontrei o .env em $Root" }
if ($SendDatabase) {
  $local = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
  if ($local) {
    throw "O servidor deste PC ainda está rodando (porta 8000). Pare-o (Ctrl+C na janela dele) antes de migrar o banco."
  }
}

# Chave com permissão restrita (o ssh recusa chave legível por outros usuários)
$KeyCopy = Join-Path $env:USERPROFILE ".ssh\kavria-lightsail.pem"
New-Item -ItemType Directory -Force (Split-Path $KeyCopy) | Out-Null
if (-not (Test-Path $KeyCopy) -or (Get-FileHash $KeyCopy).Hash -ne (Get-FileHash $Key).Hash) {
  # a cópia anterior fica somente leitura: libera a escrita antes de substituir
  if (Test-Path $KeyCopy) { icacls $KeyCopy /grant:r "$($env:USERNAME):F" | Out-Null }
  Copy-Item $Key $KeyCopy -Force
  icacls $KeyCopy /inheritance:r /grant:r "$($env:USERNAME):R" | Out-Null
}
$SshOpts = @("-i", $KeyCopy, "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30")

function Invoke-Remote([string]$Command) {
  & ssh @SshOpts $Remote $Command
  if ($LASTEXITCODE -ne 0) { throw "Falhou no servidor: $Command" }
}
function Send-Files([string[]]$Files) {
  # Executado de dentro de $Work com nomes relativos: o scp confunde "C:\..." com um nome de host
  & scp @SshOpts @Files "${Remote}:/tmp/"
  if ($LASTEXITCODE -ne 0) { throw "Falha ao enviar $Files" }
}

if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
New-Item -ItemType Directory -Force $Work | Out-Null
Push-Location $Work
try {
  Write-Host "==> Empacotando o código"
  $src = $Root -replace '\\', '/'
  # Lista explícita do que vai para o servidor. Exclusões do tar do Windows valem em qualquer nível
  # (um "--exclude=assets" levaria junto frontend/src/assets, com a logo e os sons).
  $include = @("backend", "frontend", "deploy", "Dockerfile", "docker-compose.yml", ".dockerignore", ".gitattributes", ".env.example", "README.md")
  & tar -czf kavria2.tgz `
    --exclude=backend/.venv --exclude=backend/data --exclude=backend/.pytest_cache `
    --exclude=frontend/node_modules --exclude=frontend/dist --exclude=__pycache__ `
    --exclude=.env --exclude=server.env --exclude=*.db --exclude=*.db-wal --exclude=*.db-shm `
    -C $src @include
  if ($LASTEXITCODE -ne 0) { throw "Falha ao empacotar o código" }
  Copy-Item (Join-Path $Root ".env") "app.env"
  Set-Content -Path "server.env" -Value "DOMAIN=$Domain" -Encoding ascii

  if ($Setup) {
    Write-Host "==> Preparando o servidor (Docker, swap, pastas) — leva alguns minutos"
    Copy-Item (Join-Path $PSScriptRoot "setup-server.sh") "setup-server.sh"
    Send-Files @("setup-server.sh")
    Invoke-Remote "sudo bash /tmp/setup-server.sh && rm -f /tmp/setup-server.sh"
  }

  Write-Host "==> Enviando código e configuração"
  Send-Files @("kavria2.tgz", "app.env", "server.env")
  Invoke-Remote ("sudo mkdir -p /opt/kavria2/data && sudo tar -xzf /tmp/kavria2.tgz -C /opt/kavria2 " +
    "&& sudo install -m 600 /tmp/app.env /opt/kavria2/.env && sudo install -m 644 /tmp/server.env /opt/kavria2/server.env " +
    "&& sudo chown -R 1000:1000 /opt/kavria2/data && rm -f /tmp/kavria2.tgz /tmp/app.env /tmp/server.env")

  if ($SendDatabase) {
    Write-Host "==> Copiando o banco deste PC (cópia consistente)"
    $py = Join-Path $Root "backend\.venv\Scripts\python.exe"
    $db = Join-Path $Root "backend\data\kavria2.db"
    & $py -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $db "kavria2.db"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao copiar o banco" }
    Send-Files @("kavria2.db")
    Invoke-Remote ("cd /opt/kavria2 && (sudo docker compose --env-file server.env stop app || true) " +
      "&& sudo rm -f data/kavria2.db-wal data/kavria2.db-shm && sudo mv /tmp/kavria2.db data/kavria2.db " +
      "&& sudo chown -R 1000:1000 data")
  }

  Write-Host "==> Construindo e subindo (o primeiro build leva ~5 min)"
  Invoke-Remote "cd /opt/kavria2 && sudo docker compose --env-file server.env up -d --build && sudo docker compose --env-file server.env ps"
}
finally {
  Pop-Location
  Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue  # a pasta tinha o .env e o banco
}

Write-Host "==> Testando https://$Domain"
for ($i = 1; $i -le 12; $i++) {
  try {
    $r = Invoke-WebRequest "https://$Domain/healthz" -UseBasicParsing -TimeoutSec 15
    Write-Host "OK: $($r.Content)  ->  admin: https://$Domain/admin   TV: https://$Domain/tv?key=..."
    exit 0
  } catch {
    Start-Sleep -Seconds 10
  }
}
Write-Warning "O HTTPS ainda não respondeu. Confira se o DNS de $Domain aponta para $Ip e se as portas 80/443 estão abertas na Lightsail."
