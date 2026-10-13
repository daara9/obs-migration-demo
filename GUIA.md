# Guia — Demo: Migração On-prem → Huawei Cloud OBS (Singapura)

Guia para rodar a demo no dia da apresentação, nesta pasta:
`C:\Users\d50055825\Documents\PSA\demos\OBS` (no WSL: `/mnt/c/Users/d50055825/Documents/PSA/demos/OBS`).

---

## 1. Pré-requisitos (uma vez)

- Python 3 instalado (`python3 --version`)
- Biblioteca de cliente S3: `boto3`, mais `rich` e `tqdm` (interface):
  ```bash
  python3 -m pip install --user --break-system-packages boto3 rich tqdm
  ```
- Credenciais Huawei Cloud com acesso ao OBS. Os scripts leem, nesta ordem:
  1. Variáveis de ambiente `HWC_AK` / `HWC_SK`
  2. Arquivo `/home/d50055825/mcp-hwc/.env` (padrão)
  3. Um arquivo indicado por `--env-file`

  Formato do `.env`:
  ```
  HWC_AK=SEU_ACCESS_KEY
  HWC_SK=SEU_SECRET_KEY
  ```

> Região-alvo: **`ap-southeast-3` (AP-Singapore)** — endpoint `https://obs.ap-southeast-3.myhuaweicloud.com`, bucket `onprem-migration-demo-sgp`.
> Atenção: `ap-southeast-1` é **CN-Hong Kong**, não Singapura.

---

## 2. Rodar a demo (modo automático — recomendado)

```bash
cd /mnt/c/Users/d50055825/Documents/PSA/demos/OBS
./run_demo.sh            # demo completa (~300 MB, ~3-4 min)
./run_demo.sh --quick    # versão curta (~1.000 arquivos pequenos)
```

O `run_demo.sh` executa as 3 fases em sequência:
1. **Assessment** — gera a origem on-prem e o `inventory.csv`
2. **Transferência** — migra para o OBS com **dashboard ao vivo**
3. **Verificação** — relatório de integridade MD5

---

## 3. Rodar passo a passo (modo narrado — para o pitch)

```bash
cd /mnt/c/Users/d50055825/Documents/PSA/demos/OBS

# limpa o bucket para começar do zero (opcional)
python3 cleanup.py

# FASE 1 — Assessment: cria a origem simulada + inventário (baseline MD5)
python3 generate_onprem.py

# FASE 2 — Transferência: upload paralelo com dashboard ao vivo
python3 migrate.py --workers 64 --resume

# FASE 3 — Verificação: compara origem x destino (contagem, tamanho, MD5)
python3 verify.py
```

### O que aparece na tela durante a Fase 2
- Barra de **Arquivos** (objetos migrados / total)
- Barra de **Dados** (MB migrados / total) e **MB/s** em tempo real
- **ETA** e tempo decorrido
- Contadores **OK / Falhas / Retry / Skip**
- Painel de **eventos**: uploads em andamento (inclui `multipart x/y` para arquivos maiores) e os últimos concluídos

---

## 4. Ajustes rápidos

| Objetivo | Comando |
|---|---|
| Mais volume | `python3 generate_onprem.py --small 5000 --large 8 --dump-mb 50` |
| Menos volume | `python3 generate_onprem.py --small 1200 --large 2 --dump-mb 10` |
| Acelerar (muitos arquivos pequenos) | `python3 migrate.py --workers 64` (ou 96) |
| Retomar após interrupção | `python3 migrate.py --resume` (pula o que já subiu) |
| Terminal simples (sem `rich`) | `python3 migrate.py --plain` |
| Outro bucket/região | `--bucket NOME --region ap-southeast-3 --endpoint https://obs.ap-southeast-3.myhuaweicloud.com` |

Distribuição padrão da origem (~300 MB): 2.500 pequenos (1–200 KB) + 3 médios (5–20 MB) + 1 dump (15 MB) = **2.504 objetos / ~297 MB**.

---

## 5. Arquivos gerados

| Arquivo | Descrição |
|---|---|
| `generate_onprem.py` | Cria a origem on-prem simulada + `inventory.csv` |
| `migrate.py` | Motor de migração (paralelo, multipart, resume, dashboard) |
| `verify.py` | Relatório de integridade origem x destino |
| `cleanup.py` | Remove todos os objetos do bucket (repetir a demo) |
| `run_demo.sh` | Orquestra as 3 fases |
| `roteiro_pitch.md` | Roteiro de slides e talking points |
| `onprem/` | (gerado) árvore de arquivos da origem |
| `inventory.csv` | (gerado) baseline path,size,md5 |
| `verify_report.csv` | (gerado) resultado item a item da verificação |
| `mig_dash.log` | (gerado) log do dashboard da última migração |

---

## 6. Solução de problemas

- **`VirtualHostDomainRequired`** → o cliente precisa usar *virtual-hosted style*. Já configurado (`s3={'addressing_style':'virtual'}`); mantenha a versão atual do script.
- **`XAmzContentSHA256Mismatch`** → boto3 novo envia checksum flexível que o OBS rejeita. Já tratado via `request_checksum_calculation="when_required"`.
- **`BucketNotEmpty` ao deletar** → há multipart uploads incompletos. O `cleanup.py` já aborta multipart; rode-o antes de deletar.
- **Muito lento** → muitos arquivos pequenos são limitados por latência por requisição. Aumente `--workers`.
- **Credenciais não encontradas** → defina `HWC_AK`/`HWC_SK` ou passe `--env-file /caminho/.env`.

---

## 7. Encerramento / limpeza

```bash
cd /mnt/c/Users/d50055825/Documents/PSA/demos/OBS
python3 cleanup.py        # esvazia o bucket de demo
# para remover o bucket, use o console Huawei Cloud (região AP-Singapore) ou a API
```
