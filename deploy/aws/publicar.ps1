<#
.SYNOPSIS
  Atualiza o painel em produção (https://painel2.kavria.com.br) com o código e o .env deste PC.

.DESCRIPTION
  1) Salva as mudanças num commit e envia ao GitHub (repositório privado), para o servidor sempre
     rodar uma versão guardada — se algo der errado, dá para voltar à anterior.
     Antes do commit, recusa se algum arquivo sensível (.env, banco, chave .pem) ou valor do .env
     estiver indo junto.
  2) Publica no servidor (deploy.ps1). O banco do servidor não é tocado.

.PARAMETER Mensagem
  Descrição curta da mudança, usada no commit. Se não for informada, o script pergunta.

.EXAMPLE
  .\deploy\aws\publicar.ps1

.EXAMPLE
  .\deploy\aws\publicar.ps1 -Mensagem "TV: card de Ads maior"
#>
param([string]$Mensagem)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Invoke-Git {
  & git -C $Root @args
  if ($LASTEXITCODE -ne 0) { throw "Falhou: git $($args -join ' ')" }
}

# --- 1) Commit + GitHub ------------------------------------------------------
$branch = & git -C $Root rev-parse --abbrev-ref HEAD
if ($LASTEXITCODE -ne 0) { throw "Não encontrei o repositório git em $Root" }
if ($branch -ne "main") { throw "Publique a partir do branch main (atual: $branch)" }

$changes = & git -C $Root status --porcelain
if ($changes) {
  Write-Host "==> Mudanças que vão para o commit:"
  $changes | ForEach-Object { Write-Host "    $_" }
  Invoke-Git add -A

  # Trava 1: arquivos que nunca podem ir para o GitHub
  $staged = & git -C $Root diff --cached --name-only --diff-filter=d
  $forbidden = $staged | Where-Object {
    $_ -match '(^|/)\.env$' -or ($_ -match '(^|/)\.env\.' -and $_ -notmatch '\.env\.example$') -or
    $_ -match '(^|/)server\.env$' -or $_ -match '\.pem$' -or $_ -match '\.db(-wal|-shm)?$' -or
    $_ -match '^backend/data/'
  }
  if ($forbidden) {
    Invoke-Git reset -q
    throw "Commit cancelado: arquivo sensível na lista ($($forbidden -join ', ')). Confira o .gitignore."
  }

  # Trava 2: nenhum valor do .env escrito em arquivo (senha, segredo, chave da TV, credenciais do ML)
  $envFile = Join-Path $Root ".env"
  if (Test-Path $envFile) {
    $secrets = @{}
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
      if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$') {
        $name = $Matches[1]; $value = $Matches[2].Trim('"', "'")
        if ($value.Length -ge 6 -and $name -notin @("DATABASE_URL", "WORKERS_ENABLED")) { $secrets[$name] = $value }
      }
    }
    foreach ($file in $staged) {
      $text = [IO.File]::ReadAllText((Join-Path $Root $file))
      foreach ($name in $secrets.Keys) {
        if ($text.Contains($secrets[$name])) {
          Invoke-Git reset -q
          throw "Commit cancelado: o arquivo $file contém o valor de $name do .env."
        }
      }
    }
  }

  if (-not $Mensagem) {
    try { $Mensagem = Read-Host "Descreva a mudança em poucas palavras (Enter = genérica)" } catch { $Mensagem = "" }
  }
  if (-not $Mensagem) { $Mensagem = "Atualização do painel v2 ($(Get-Date -Format 'dd/MM/yyyy HH:mm'))" }
  Invoke-Git commit -q -m $Mensagem
  Write-Host "==> Commit: $(& git -C $Root log -1 --format='%h %s')"
}
else {
  Write-Host "==> Nenhuma mudança nova no código; publicando a versão $(& git -C $Root log -1 --format='%h')"
}

Write-Host "==> Enviando ao GitHub"
Invoke-Git push -q origin main

# --- 2) Servidor --------------------------------------------------------------
# Usa a cópia protegida da chave (criada na primeira publicação); se não houver, a da pasta Downloads
$Key = Join-Path $env:USERPROFILE ".ssh\kavria-lightsail.pem"
if (-not (Test-Path $Key)) { $Key = Join-Path $HOME "Downloads\LightsailDefaultKey-sa-east-1.pem" }

& (Join-Path $PSScriptRoot "deploy.ps1") -Ip 54.232.124.83 -Key $Key -Domain painel2.kavria.com.br
