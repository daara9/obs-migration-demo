# Migração on-premises para Huawei Cloud OBS

Demo executável de migração de arquivos para o Huawei Cloud OBS, usando a API compatível com S3. O cenário simula uma origem on-premises, envia os dados para um bucket em AP-Singapore (`ap-southeast-3`) e valida a integridade ao final.

O objetivo é demonstrar um fluxo realista de migração em três etapas:

```text
assessment -> transferencia -> verificacao
```

## Visão geral

A demo cobre:

- Geração de uma origem on-premises simulada com milhares de arquivos.
- Criação de um inventário local com caminho, tamanho e MD5 de cada arquivo.
- Upload paralelo para o OBS, com suporte a multipart, retry e retomada.
- Verificação final comparando origem e destino por contagem, tamanho e MD5.

Scripts principais:

| Script | Função |
|---|---|
| `generate_onprem.py` | Gera a origem simulada e o `inventory.csv` |
| `migrate.py` | Migra os arquivos para o OBS com dashboard de progresso |
| `verify.py` | Valida integridade entre origem e destino |
| `cleanup.py` | Esvazia o bucket para repetir a demo |
| `run_demo.sh` | Executa o fluxo completo |

## Requisitos

- Python 3.9 ou superior
- `pip`
- Acesso ao endpoint OBS de Singapura
- Credenciais Huawei Cloud com permissão de leitura e escrita no OBS

Instale as dependências:

```bash
python3 -m pip install --user --break-system-packages boto3 rich tqdm
```

Pacotes usados:

| Pacote | Uso |
|---|---|
| `boto3` | Cliente S3 compatível com OBS |
| `rich` | Dashboard de progresso |
| `tqdm` | Barra simples no modo `--plain` |

## Configuração

Os scripts procuram as credenciais `HWC_AK` e `HWC_SK` nesta ordem:

1. Variáveis de ambiente.
2. Arquivo `/home/d50055825/mcp-hwc/.env`.
3. Arquivo indicado por `--env-file`.

Exemplo de `.env`:

```dotenv
HWC_AK=SEU_ACCESS_KEY
HWC_SK=SEU_SECRET_KEY
```

Ou via shell:

```bash
export HWC_AK="..."
export HWC_SK="..."
```

Configuração padrão de destino:

| Item | Valor |
|---|---|
| Região | `ap-southeast-3` |
| Nome no console | AP-Singapore |
| Endpoint | `https://obs.ap-southeast-3.myhuaweicloud.com` |
| Bucket | `onprem-migration-demo-sgp` |

Observação: em Huawei Cloud, `ap-southeast-1` é CN-Hong Kong, não Singapura.

## Uso rápido

Execute a demo completa:

```bash
./run_demo.sh
```

Execute uma versão menor:

```bash
./run_demo.sh --quick
```

O fluxo completo gera a origem local, migra os arquivos para o bucket e executa a verificação de integridade.

## Uso passo a passo

Use esta forma quando quiser narrar a demo durante uma apresentação.

Limpe o bucket antes de começar, se necessário:

```bash
python3 cleanup.py
```

Gere a origem simulada e o inventário:

```bash
python3 generate_onprem.py
```

Migre os arquivos para o OBS:

```bash
python3 migrate.py --workers 64 --resume
```

Valide a integridade:

```bash
python3 verify.py
```

Exemplo de resultado esperado:

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

## Dashboard da migração

Durante a transferência, `migrate.py` exibe:

- progresso por quantidade de arquivos;
- progresso por volume transferido;
- vazão instantânea e média;
- tempo estimado para conclusão;
- contadores de sucesso, falha, retry e skip;
- lista de uploads em andamento e eventos recentes.

Exemplo simplificado:

```text
OBS Migration  on-prem  ->  ap-southeast-3  [onprem-migration-demo-sgp]

Arquivos  2504 / 2504  100.0%
Dados     297.0 MB / 297.1 MB  100.0%

OK 2504  Falhas 0  Retry 0  Skip 0
2.3 MB/s agora | media 1.8 MB/s | ETA 00:00:00

em andamento                    progresso
images/asset-001.png            multipart 2/2
logs/logs-00674.log             single put
```

## Opções principais

### `generate_onprem.py`

| Flag | Padrão | Descrição |
|---|---|---|
| `--small` | `2500` | Quantidade de arquivos pequenos |
| `--small-min-kb` | `1` | Tamanho mínimo dos pequenos |
| `--small-max-kb` | `200` | Tamanho máximo dos pequenos |
| `--large` | `3` | Quantidade de arquivos médios |
| `--large-min-mb` | `5` | Tamanho mínimo dos médios |
| `--large-max-mb` | `20` | Tamanho máximo dos médios |
| `--dump-mb` | `15` | Tamanho do dump único |
| `--seed` | `42` | Semente do gerador |

Exemplo com mais volume:

```bash
python3 generate_onprem.py --small 5000 --large 8 --dump-mb 50
```

### `migrate.py`

| Flag | Padrão | Descrição |
|---|---|---|
| `--bucket` | `onprem-migration-demo-sgp` | Bucket de destino |
| `--region` | `ap-southeast-3` | Região OBS |
| `--endpoint` | endpoint de Singapura | Endpoint OBS |
| `--workers` | `8` | Número de uploads paralelos |
| `--part-size` | `16` | Tamanho da parte multipart, em MB |
| `--threshold` | `16` | Tamanho mínimo para usar multipart, em MB |
| `--retries` | `3` | Número de tentativas por arquivo |
| `--resume` | desligado | Pula objetos já enviados com mesmo MD5 |
| `--plain` | desligado | Usa saída simples com `tqdm` |

Para muitos arquivos pequenos, use mais workers:

```bash
python3 migrate.py --workers 64 --resume
```

### `verify.py`

| Flag | Padrão | Descrição |
|---|---|---|
| `--inventory` | `inventory.csv` | Inventário local |
| `--bucket` | `onprem-migration-demo-sgp` | Bucket de destino |
| `--workers` | `16` | Paralelismo das verificações |
| `--report` | `verify_report.csv` | Relatório item a item |

### `cleanup.py`

Remove objetos e multipart uploads pendentes do bucket:

```bash
python3 cleanup.py
```

## Como funciona

### Assessment

`generate_onprem.py` cria uma árvore local semelhante a um file server:

```text
onprem/
  docs/
  logs/
  images/
  db-dumps/
```

Para cada arquivo, calcula o MD5 e grava `inventory.csv`:

```csv
relpath,size,md5
logs/logs-00001.log,183944,9d4...
```

### Transferência

`migrate.py` usa boto3 com endpoint OBS compatível com S3.

- Arquivos pequenos usam `PutObject`.
- Arquivos acima do limiar usam multipart upload.
- O MD5 local é salvo como metadado do objeto.
- `--resume` compara o metadado remoto para pular objetos já migrados.
- Falhas são re-tentadas com backoff.

Configurações importantes do cliente:

- `signature_version = s3v4`
- `addressing_style = virtual`
- `request_checksum_calculation = when_required`
- `response_checksum_validation = when_required`

### Verificação

`verify.py` lista os objetos do bucket e confere:

- existência do objeto;
- tamanho;
- MD5 do metadado salvo durante a migração.

O relatório detalhado é gravado em `verify_report.csv`.

## Artefatos gerados

| Arquivo ou pasta | Descrição |
|---|---|
| `onprem/` | Origem simulada |
| `inventory.csv` | Inventário local com MD5 |
| `verify_report.csv` | Resultado da verificação |
| `mig_dash.log` | Log da última execução |

Esses artefatos não são versionados.

## Ajustes comuns

| Objetivo | Comando |
|---|---|
| Reduzir volume | `python3 generate_onprem.py --small 1200 --large 2 --dump-mb 10` |
| Aumentar volume | `python3 generate_onprem.py --small 5000 --large 8 --dump-mb 50` |
| Aumentar paralelismo | `python3 migrate.py --workers 64 --resume` |
| Usar saída simples | `python3 migrate.py --plain` |
| Repetir a demo do zero | `python3 cleanup.py && ./run_demo.sh` |

Muitos arquivos pequenos tendem a ser limitados por latência por requisição. Nesses casos, aumentar `--workers` costuma ter mais impacto que aumentar o tamanho de multipart.

## Solução de problemas

| Sintoma | Possível causa e correção |
|---|---|
| `VirtualHostDomainRequired` | O OBS exige virtual-hosted style. O script já configura isso. |
| `XAmzContentSHA256Mismatch` | Checksums flexíveis do boto3. O script usa `when_required`. |
| `BucketNotEmpty` ao deletar | Há objetos ou multipart uploads pendentes. Rode `cleanup.py`. |
| Migração lenta | Aumente `--workers`; muitos arquivos pequenos sofrem com latência. |
| Credenciais não encontradas | Defina `HWC_AK`/`HWC_SK` ou use `--env-file`. |

## Segurança

Credenciais não são versionadas. O `.gitignore` exclui `.env`, artefatos gerados, logs e diretórios temporários.

O token ou AK/SK devem ficar fora do repositório. Use variáveis de ambiente ou um arquivo local com permissões restritas.

## Estrutura do repositório

```text
.
├── README.md
├── GUIA.md
├── roteiro_pitch.md
├── generate_onprem.py
├── migrate.py
├── verify.py
├── cleanup.py
├── run_demo.sh
└── .gitignore
```

## Resultado de referência

Execução validada em AP-Singapore:

| Métrica | Valor |
|---|---|
| Objetos | 2.504 |
| Volume | 297 MB |
| Tempo | 02:41 |
| Workers | 64 |
| Falhas | 0 |
| Integridade | 100% |
