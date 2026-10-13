# OBS Migration Demo — on-premises → Huawei Cloud OBS (Singapura)

Demo **executável** de migração de um servidor de arquivos on-premises para o
**Huawei Cloud OBS** na região **AP-Singapore (`ap-southeast-3`)**, reproduzindo as
três fases de um projeto real de migração de dados:

```
┌───────────────┐      ┌──────────────────────┐      ┌───────────────────┐
│  1. ASSESS    │      │  2. TRANSFER          │      │  3. VERIFY        │
│  inventário   │  →   │  upload paralelo      │  →   │  contagem + MD5   │
│  origem on-prem│     │  multipart / resume   │      │  origem x destino │
│  (baseline MD5)│     │  dashboard ao vivo    │      │  100% íntegro     │
└───────────────┘      └──────────────────────┘      └───────────────────┘
        generate_onprem.py        migrate.py                 verify.py
```

O objetivo é demonstrar, de ponta a ponta e com prova de integridade, como migrar
dados para o OBS **sem reescrever a aplicação** (API compatível com S3).

---

## Índice

- [O que a demo mostra](#o-que-a-demo-mostra)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração de credenciais](#configuração-de-credenciais)
- [Como usar — modo automático](#como-usar--modo-automático)
- [Como usar — passo a passo](#como-usar--passo-a-passo)
- [O dashboard de migração](#o-dashboard-de-migração)
- [Referência de opções (flags)](#referência-de-opções-flags)
- [Artefatos gerados](#artefatos-gerados)
- [Como funciona (por dentro)](#como-funciona-por-dentro)
- [Customização e performance](#customização-e-performance)
- [Solução de problemas](#solução-de-problemas)
- [Segurança](#segurança)
- [Estrutura do repositório](#estrutura-do-repositório)

---

## O que a demo mostra

1. **Assessment** — varre uma origem on-premises simulada, cria uma árvore de
   arquivos realista e gera um `inventory.csv` (path, tamanho, **MD5**) que serve
   de *baseline* para a verificação.
2. **Transferência** — faz upload paralelo para o OBS com **multipart** para
   arquivos grandes, **retomada** (`--resume`) e **retries**, exibindo um
   **dashboard ao vivo** (objetos, MB/s, ETA, eventos).
3. **Verificação** — confronta origem × destino (contagem, tamanho e **MD5**),
   emitindo um relatório de integridade.

---

## Requisitos

- **Python 3.9+** (`python3 --version`)
- **pip** disponível
- Acesso à internet ao endpoint OBS (`https://obs.ap-southeast-3.myhuaweicloud.com`)
- Uma credencial Huawei Cloud (AK/SK) com permissão de leitura/escrita no OBS

---

## Instalação

```bash
python3 -m pip install --user --break-system-packages boto3 rich tqdm
```

- `boto3` — cliente S3 usado para falar com o OBS
- `rich` — dashboard ao vivo
- `tqdm` — barra alternativa (modo `--plain`)

---

## Configuração de credenciais

Os scripts leem a credencial (`HWC_AK` / `HWC_SK`) nesta ordem:

1. **Variáveis de ambiente** do processo
2. **Arquivo `.env`** (padrão: `/home/d50055825/mcp-hwc/.env`)
3. **Arquivo indicado por `--env-file`**

Formato do `.env`:

```dotenv
HWC_AK=SEU_ACCESS_KEY
HWC_SK=SEU_SECRET_KEY
```

Exemplo de uso only com variáveis de ambiente:

```bash
export HWC_AK="..." HWC_SK="..."
```

Região/endpoint usados por padrão:

| Item | Valor |
|---|---|
| Região | `ap-southeast-3` (**AP-Singapore**) |
| Endpoint | `https://obs.ap-southeast-3.myhuaweicloud.com` |
| Bucket | `onprem-migration-demo-sgp` |

> ⚠️ **Atenção ao código de região:** em Huawei Cloud, `ap-southeast-1` é
> **CN-Hong Kong** (aparece sob "China" no console). Singapura é **`ap-southeast-3`**.

---

## Como usar — modo automático

Executa as três fases em sequência:

```bash
cd /mnt/c/Users/d50055825/Documents/PSA/demos/OBS   # ou a pasta onde clonou
./run_demo.sh            # demo completa (~300 MB, ~3 min)
./run_demo.sh --quick    # versão curta (~1.000 arquivos pequenos)
```

Ao final você verá o relatório de integridade com `RESULTADO: [OK]`.

---

## Como usar — passo a passo

Ideal para narrar a demo em uma apresentação:

```bash
# (opcional) começa com o bucket limpo
python3 cleanup.py

# FASE 1 — Assessment: cria a origem simulada + inventário com MD5
python3 generate_onprem.py

# FASE 2 — Transferência: upload paralelo com dashboard ao vivo
python3 migrate.py --workers 64 --resume

# FASE 3 — Verificação: relatório de integridade origem x destino
python3 verify.py
```

Saída esperada da Fase 3:

```
 RELATORIO DE INTEGRIDADE  (origem  vs  OBS)
  origem (inventory) : 2504 objetos / 297.1 MB
  destino (bucket)   : 2504 objetos / 297.1 MB
  integros           : 2504 (100.00%)
  ausentes           : 0
  tamanho divergente : 0
  hash divergente    : 0
  RESULTADO: [OK] migracao 100% integra
```

---

## O dashboard de migração

Durante a Fase 2 (`migrate.py`), o terminal mostra:

```
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

Elementos em tempo real: barras de **arquivos** e **bytes**, **throughput
instantâneo/médio**, **ETA**, contadores **OK/Falhas/Retry/Skip** e a lista de
uploads **em andamento** (com `multipart x/y`) e concluídos.

---

## Referência de opções (flags)

### `generate_onprem.py` — fase de assessment

| Flag | Padrão | Descrição |
|---|---|---|
| `--small` | `2500` | nº de arquivos pequenos (vão para `docs/` e `logs/`) |
| `--small-min-kb` / `--small-max-kb` | `1` / `200` | faixa de tamanho dos pequenos (KB) |
| `--large` | `3` | nº de arquivos médios (vão para `images/`; exercitam multipart) |
| `--large-min-mb` / `--large-max-mb` | `5` / `20` | faixa de tamanho dos médios (MB) |
| `--dump-mb` | `15` | tamanho do dump único em `db-dumps/` (0 desativa) |
| `--out` | `<pasta>/onprem` | diretório de saída da origem |
| `--out-dir` | `<pasta>` | onde gravar o `inventory.csv` |
| `--seed` | `42` | semente do gerador (reprodutibilidade) |

### `migrate.py` — fase de transferência

| Flag | Padrão | Descrição |
|---|---|---|
| `--src` | `<pasta>/onprem` | diretório de origem |
| `--inventory` | `<pasta>/inventory.csv` | inventário (path,size,md5) |
| `--bucket` | `onprem-migration-demo-sgp` | bucket de destino |
| `--region` | `ap-southeast-3` | região OBS |
| `--endpoint` | `https://obs.ap-southeast-3.myhuaweicloud.com` | endpoint OBS |
| `--prefix` | *(vazio)* | prefixo das chaves no bucket |
| `--workers` | `8` | nº de uploads paralelos (use `64` para muitos arquivos) |
| `--part-size` | `16` | tamanho da parte multipart (MB) |
| `--threshold` | `16` | a partir deste tamanho (MB) usa multipart |
| `--retries` | `3` | tentativas por arquivo em caso de erro |
| `--resume` | desligado | pula objetos já migrados (mesmo MD5) |
| `--plain` | desligado | barra simples (tqdm) em vez do dashboard rich |
| `--env-file` | `/home/d50055825/mcp-hwc/.env` | arquivo de credenciais |

### `verify.py` — fase de verificação

| Flag | Padrão | Descrição |
|---|---|---|
| `--inventory` | `<pasta>/inventory.csv` | baseline a conferir |
| `--bucket` / `--region` / `--endpoint` | (idem migração) | destino |
| `--prefix` | *(vazio)* | prefixo das chaves |
| `--workers` | `16` | paralelismo das checagens (`head_object`) |
| `--report` | `<pasta>/verify_report.csv` | relatório item a item |

### `cleanup.py` — limpeza

| Flag | Padrão | Descrição |
|---|---|---|
| `--bucket` / `--region` / `--endpoint` | (idem migração) | bucket a esvaziar |
| `--env-file` | `/home/d50055825/mcp-hwc/.env` | credenciais |

---

## Artefatos gerados

| Arquivo/pasta | Descrição |
|---|---|
| `onprem/` | origem simulada (`docs/`, `logs/`, `images/`, `db-dumps/`) |
| `inventory.csv` | baseline `relpath,size,md5` |
| `verify_report.csv` | resultado item a item da verificação |
| `mig_dash.log` | log do dashboard da última migração |

Todos esses são **ignorados pelo git** (ver `.gitignore`).

---

## Como funciona (por dentro)

- **Assessment** (`generate_onprem.py`): gera arquivos com conteúdo aleatório e
  calcula o **MD5 incremental** de cada um, gravando `inventory.csv`.
- **Transferência** (`migrate.py`):
  - arquivos ≤ `--threshold` vão em **um único `PutObject`**;
  - arquivos maiores usam **multipart** (`CreateMultipartUpload` →
    `UploadPart` → `CompleteMultipartUpload`), com progresso parte a parte;
  - cada objeto recebe o **MD5 local** nos **metadados** (`x-amz-meta-md5`),
    permitindo verificar integridade mesmo em multipart;
  - `--resume` usa `HeadObject` + metadado MD5 para pular o que já subiu;
  - erros são re-tentados com *backoff* exponencial.
- **Verificação** (`verify.py`): lista o bucket (`ListObjectsV2`) e, para cada
  objeto, confere **tamanho** e **MD5** (metadado, com fallback para ETag).

Cliente S3 compatível configurado com `signature_version=s3v4`,
`addressing_style=virtual` e checksums flexíveis desativados
(`when_required`) — exigências do OBS.

---

## Customização e performance

| Objetivo | Comando |
|---|---|
| Mais volume | `python3 generate_onprem.py --small 5000 --large 8 --dump-mb 50` |
| Menos volume | `python3 generate_onprem.py --small 1200 --large 2 --dump-mb 10` |
| Acelerar (muitos arquivos pequenos) | `python3 migrate.py --workers 64` (ou `96`) |
| Retomar após interrupção | `python3 migrate.py --resume` |
| Terminal simples | `python3 migrate.py --plain` |
| Outro bucket/região | `--bucket NOME --region ... --endpoint ...` |

> Muitos arquivos pequenos são limitados por **latência por requisição**;
> aumentar `--workers` escala bem (ex.: 300 arquivos: ~14s com 16 workers
> vs ~6s com 64 workers).

---

## Solução de problemas

| Erro | Causa / solução |
|---|---|
| `VirtualHostDomainRequired` | OBS exige *virtual-hosted style*. Já configurado no cliente. |
| `XAmzContentSHA256Mismatch` | boto3 novo envia checksum flexível que o OBS rejeita. Já tratado com `when_required`. |
| `BucketNotEmpty` ao deletar | Há multipart uploads incompletos. O `cleanup.py` já os aborta; rode-o antes. |
| Muito lento | Aumente `--workers`; considere aumentar o tamanho dos arquivos. |
| Credenciais não encontradas | Defina `HWC_AK`/`HWC_SK` ou passe `--env-file /caminho/.env`. |

---

## Segurança

- **Nenhum segredo é versionado.** As credenciais (`HWC_AK`/`HWC_SK`) são lidas
  do ambiente ou de um `.env` local, fora do repositório.
- O token do OBS fica restrito ao processo que executa os scripts.
- Bucket de demo é facilmente removível ao final (`cleanup.py` + console).

---

## Estrutura do repositório

```
.
├── README.md            # este arquivo
├── GUIA.md              # guia operacional + troubleshooting
├── roteiro_pitch.md     # roteiro de slides / talking points
├── generate_onprem.py   # Fase 1 — assessment
├── migrate.py           # Fase 2 — transferência
├── verify.py            # Fase 3 — verificação
├── cleanup.py           # limpeza do bucket
├── run_demo.sh          # orquestra as 3 fases
└── .gitignore
```

## Resultado de referência (execução real)

| Métrica | Valor |
|---|---|
| Objetos | 2.504 |
| Volume | 297 MB |
| Tempo | 02:41 |
| Workers | 64 |
| Falhas | 0 |
| Integridade (MD5) | 100% (2.504/2.504) |
