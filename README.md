<div align="center">

# ☁️ Migração on-premises → Huawei Cloud OBS

**Demo executável das três fases de um projeto de migração de dados**

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![OBS](https://img.shields.io/badge/Huawei%20Cloud-OBS-C7000A)
![S3](https://img.shields.io/badge/API-S3--compatible-569A31?logo=amazons3&logoColor=white)
![Região](https://img.shields.io/badge/região-ap--southeast--3%20·%20Singapore-00A1E0)
![Integridade](https://img.shields.io/badge/integridade-100%25-success)

</div>

---

## ⚡ TL;DR

```bash
python3 -m pip install --user --break-system-packages boto3 rich tqdm
./run_demo.sh            # gera ~300 MB, migra para o OBS e valida (≈3 min)
```

Resultado final: `RESULTADO: [OK] migracao 100% integra` — contagem, tamanho e MD5 conferidos.

---

## 🎯 Sobre

Migra um servidor de arquivos **on-premises** para o **Huawei Cloud OBS**
(região **AP-Singapore · `ap-southeast-3`**) sem reescrever a aplicação — a
comunicação usa a **API compatível com S3**.

O roteiro reproduz o ciclo real de uma migração:

```text
   ┌─────────────┐        ┌───────────────┐        ┌──────────────┐
   │  1. ASSESS  │        │ 2. TRANSFER    │        │  3. VERIFY   │
   │  inventário │  ───▶  │ upload paralelo│  ───▶  │ contagem+MD5 │
   │  + baseline │        │ multipart      │        │ origem ×     │
   │    MD5      │        │ resume/retries │        │ destino      │
   └─────────────┘        └───────────────┘        └──────────────┘
     generate_onprem.py        migrate.py               verify.py
```

---

## 📋 Requisitos

| | |
|---|---|
| 🐍 **Python** | 3.9 ou superior |
| 📦 **pip** | disponível |
| 🌐 **Rede** | acesso a `https://obs.ap-southeast-3.myhuaweicloud.com` |
| 🔑 **Credencial** | AK/SK Huawei Cloud com leitura/escrita no OBS |

---

## 🚀 Instalação

```bash
python3 -m pip install --user --break-system-packages boto3 rich tqdm
```

| Pacote | Papel |
|---|---|
| `boto3` | cliente S3 que fala com o OBS |
| `rich` | dashboard ao vivo |
| `tqdm` | barra alternativa (modo `--plain`) |

---

## 🔑 Configuração de credenciais

Os scripts resolvem `HWC_AK` / `HWC_SK` nesta ordem:

1. Variáveis de ambiente
2. Arquivo `.env` — padrão `/home/d50055825/mcp-hwc/.env`
3. Arquivo indicado por `--env-file`

```dotenv
HWC_AK=SEU_ACCESS_KEY
HWC_SK=SEU_SECRET_KEY
```

Ou direto no shell:

```bash
export HWC_AK="..." HWC_SK="..."
```

| Item | Valor padrão |
|---|---|
| 🌎 Região | `ap-southeast-3` · **AP-Singapore** |
| 🔗 Endpoint | `https://obs.ap-southeast-3.myhuaweicloud.com` |
| 🪣 Bucket | `onprem-migration-demo-sgp` |

> [!WARNING]
> Em Huawei Cloud, **`ap-southeast-1` é CN-Hong Kong** (aparece sob "China" no
> console). Singapura é **`ap-southeast-3`**.

---

## ▶️ Como usar

### Modo automático

```bash
./run_demo.sh            # demo completa (~300 MB)
./run_demo.sh --quick    # versão curta
```

### Modo passo a passo (para narrar)

```bash
python3 cleanup.py                        # (opcional) começa com o bucket limpo

python3 generate_onprem.py                # 1️⃣ assessment  → origem + inventory.csv
python3 migrate.py --workers 64 --resume  # 2️⃣ transferência → dashboard ao vivo
python3 verify.py                         # 3️⃣ verificação  → relatório de integridade
```

<details>
<summary><b>Saída esperada da verificação</b></summary>

```text
 RELATORIO DE INTEGRIDADE  (origem  vs  OBS)
  origem (inventory) : 2504 objetos / 297.1 MB
  destino (bucket)   : 2504 objetos / 297.1 MB
  integros           : 2504 (100.00%)
  ausentes           : 0
  tamanho divergente : 0
  hash divergente    : 0
  RESULTADO: [OK] migracao 100% integra
```

</details>

---

## 📊 O dashboard de migração

Durante a **Fase 2**, o terminal mostra progresso em tempo real:

```text
 OBS Migration  on-prem  ->  ap-southeast-3        [onprem-migration-demo-sgp]
    Arquivos  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━╸    2,504/2,504  100.0%
       Dados  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╸  297.0 MB/297.1 MB  100.0%
 OK 2504  Falhas 0  Retry 0  Skip 0  |  2.3 MB/s agora  | media 1.8 MB/s
                                   |  ETA 00:00:41  | decorrido 00:02:00
 ── eventos ──────────────────────────────────────────────────────────────
 em andamento                    progresso
 images/asset-001.png            multipart 2/2
 logs/logs-00674.log             single put
 OK   docs/docs-00441.pdf        183.9 KB
```

- 📁 barra de **arquivos** · 💾 barra de **bytes**
- ⚡ **MB/s** instantâneo e médio · ⏱️ **ETA**
- ✅ contadores **OK / Falhas / Retry / Skip**
- 🔄 uploads em andamento (inclui `multipart x/y`)

---

## 🧩 Referência de opções (flags)

<details open>
<summary><b>generate_onprem.py</b> — assessment</summary>

| Flag | Padrão | Descrição |
|---|---|---|
| `--small` | `2500` | nº de arquivos pequenos (`docs/`, `logs/`) |
| `--small-min-kb` / `--small-max-kb` | `1` / `200` | faixa de tamanho (KB) |
| `--large` | `3` | nº de arquivos médios (`images/`, exercitam multipart) |
| `--large-min-mb` / `--large-max-mb` | `5` / `20` | faixa de tamanho (MB) |
| `--dump-mb` | `15` | dump único em `db-dumps/` (0 desativa) |
| `--out` / `--out-dir` | `<pasta>/onprem` / `<pasta>` | saída |
| `--seed` | `42` | semente (reprodutibilidade) |

</details>

<details open>
<summary><b>migrate.py</b> — transferência</summary>

| Flag | Padrão | Descrição |
|---|---|---|
| `--src` / `--inventory` | `<pasta>/onprem` / `<pasta>/inventory.csv` | entrada |
| `--bucket` | `onprem-migration-demo-sgp` | destino |
| `--region` / `--endpoint` | `ap-southeast-3` / endpoint OBS | destino |
| `--prefix` | *(vazio)* | prefixo das chaves |
| `--workers` | `8` | uploads paralelos (use `64` p/ muitos arquivos) |
| `--part-size` / `--threshold` | `16` / `16` | MB |
| `--retries` | `3` | tentativas por arquivo |
| `--resume` | desligado | pula já migrados (mesmo MD5) |
| `--plain` | desligado | barra tqdm em vez do `rich` |
| `--env-file` | `/home/d50055825/mcp-hwc/.env` | credenciais |

</details>

<details>
<summary><b>verify.py</b> — verificação</summary>

| Flag | Padrão | Descrição |
|---|---|---|
| `--inventory` | `<pasta>/inventory.csv` | baseline |
| `--bucket` / `--region` / `--endpoint` | (idem migração) | destino |
| `--prefix` | *(vazio)* | prefixo |
| `--workers` | `16` | paralelismo das checagens |
| `--report` | `<pasta>/verify_report.csv` | relatório item a item |

</details>

<details>
<summary><b>cleanup.py</b> — limpeza</summary>

| Flag | Padrão | Descrição |
|---|---|---|
| `--bucket` / `--region` / `--endpoint` | (idem migração) | bucket |
| `--env-file` | `/home/d50055825/mcp-hwc/.env` | credenciais |

</details>

---

## 🛠️ Como funciona (por dentro)

| Fase | O que faz |
|---|---|
| **Assessment** | Gera arquivos aleatórios e calcula o **MD5 incremental** de cada um → `inventory.csv` |
| **Transferência** | `PutObject` para pequenos; **multipart** para grandes; grava o **MD5 local nos metadados** (`x-amz-meta-md5`); `--resume` via `HeadObject`; retries com *backoff* |
| **Verificação** | `ListObjectsV2` + `HeadObject`; confere **tamanho** e **MD5** (metadado, com fallback para ETag) |

Cliente S3 compatível com `signature_version=s3v4`, `addressing_style=virtual`
e checksums flexíveis desativados (`when_required`) — exigências do OBS.

---

## ⚙️ Customização e performance

| Objetivo | Comando |
|---|---|
| Mais volume | `generate_onprem.py --small 5000 --large 8 --dump-mb 50` |
| Menos volume | `generate_onprem.py --small 1200 --large 2 --dump-mb 10` |
| Acelerar | `migrate.py --workers 64` (ou `96`) |
| Retomar | `migrate.py --resume` |
| Terminal simples | `migrate.py --plain` |

> [!TIP]
> Muitos arquivos pequenos são limitados por **latência por requisição** — aumentar
> `--workers` escala bem (300 arquivos: ~14s com 16 workers vs ~6s com 64).

---

## 🩺 Solução de problemas

| Erro | Causa / solução |
|---|---|
| `VirtualHostDomainRequired` | OBS exige *virtual-hosted style* — já configurado |
| `XAmzContentSHA256Mismatch` | boto3 novo envia checksum flexível — tratado com `when_required` |
| `BucketNotEmpty` ao deletar | multipart incompleto — o `cleanup.py` já aborta |
| Muito lento | aumente `--workers` |
| Credenciais não encontradas | defina `HWC_AK`/`HWC_SK` ou use `--env-file` |

---

## 🔒 Segurança

- **Nenhum segredo é versionado** — `HWC_AK`/`HWC_SK` vêm do ambiente ou de um `.env` local (fora do repositório).
- O bucket de demo é removível ao final (`cleanup.py` + console).

---

## 📁 Estrutura do repositório

```text
.
├── README.md            ← você está aqui
├── GUIA.md              # guia operacional + troubleshooting
├── roteiro_pitch.md     # roteiro de slides / talking points
├── generate_onprem.py   # Fase 1 — assessment
├── migrate.py           # Fase 2 — transferência
├── verify.py            # Fase 3 — verificação
├── cleanup.py           # limpeza do bucket
├── run_demo.sh          # orquestra as 3 fases
└── .gitignore
```

> Artefatos gerados (`onprem/`, `inventory.csv`, `verify_report.csv`, `mig_dash.log`)
> não são versionados.

---

<div align="center">

### 📈 Resultado de referência (execução real)

| Objetos | Volume | Tempo | Workers | Falhas | Integridade |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **2.504** | **297 MB** | **02:41** | 64 | **0** | **100%** ✅ |

<sub>Feito para demonstrar migração de dados para o Huawei Cloud OBS.</sub>

</div>
