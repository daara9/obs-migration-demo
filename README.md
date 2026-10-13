# OBS Migration Demo — on-premises → Huawei Cloud OBS (Singapura)

Demo de migração de um servidor de arquivos on-premises para o **Huawei Cloud OBS**
na região **AP-Singapore (`ap-southeast-3`)**, cobrindo as três fases de um projeto
real de migração: **assessment → transferência → verificação**.

## O que a demo mostra

1. **Assessment** — inventário da origem (nº de objetos, volume, baseline MD5).
2. **Transferência** — upload paralelo com multipart, retomada e retries, com
   **dashboard ao vivo** (objetos, MB/s, ETA, eventos).
3. **Verificação** — confronto origem × destino (contagem, tamanho e MD5),
   provando integridade.

## Estrutura

| Arquivo | Descrição |
|---|---|
| `generate_onprem.py` | Gera a origem on-prem simulada + `inventory.csv` |
| `migrate.py` | Motor de migração (paralelo, multipart, resume, dashboard) |
| `verify.py` | Relatório de integridade origem × destino |
| `cleanup.py` | Remove todos os objetos do bucket (repetir a demo) |
| `run_demo.sh` | Orquestra as 3 fases |
| `GUIA.md` | Guia completo de execução e troubleshooting |
| `roteiro_pitch.md` | Roteiro de slides / talking points |

## Quickstart

Pré-requisitos:

```bash
python3 -m pip install --user --break-system-packages boto3 rich tqdm
```

Credenciais OBS via variáveis de ambiente `HWC_AK` / `HWC_SK` (ou um `.env`).

```bash
./run_demo.sh          # demo completa (~300 MB, ~3 min)
./run_demo.sh --quick  # versão curta

# ou passo a passo:
python3 generate_onprem.py
python3 migrate.py --workers 64 --resume
python3 verify.py
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

## Configuração

- Região: `ap-southeast-3` (AP-Singapore) — observe que `ap-southeast-1` é CN-Hong Kong.
- Endpoint: `https://obs.ap-southeast-3.myhuaweicloud.com`
- API compatível com S3 (boto3), `signature_version=s3v4`, addressing *virtual*.

## Segurança

Nenhum segredo é versionado. As credenciais (`HWC_AK`/`HWC_SK`) são lidas do
ambiente ou de um `.env` local, que **não** faz parte deste repositório.

Detalhes completos em [`GUIA.md`](GUIA.md).
