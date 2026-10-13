# Roteiro de Pitch — Migração on-prem → Huawei Cloud OBS (Singapura)

Demo de ~6 min, com execução real por trás. Região-alvo: **ap-southeast-3 (AP-Singapore)**.

## Mensagem central
"Migrar dados on-premises para a Huawei Cloud OBS sem reescrever aplicação, com
transferência paralela, retomável e **prova de integridade a 100%**."

---

## Slide 1 — O problema (30s)
- Dados críticos presos em servidores/NAS on-premises
- Riscos: hardware no fim da vida, backup frágil, sem elasticidade, custo de ops
- Objetivo: mover tudo para OBS com **zero perda** e **zero downtime**

## Slide 2 — A estratégia (45s)
Projeto de migração em 3 fases:
1. **Assessment** — inventariar origem (nº de objetos, volume, md5 baseline)
2. **Transferência** — upload paralelo, multipart, retomada e retries
3. **Verificação** — confrontar origem × destino (contagem, tamanho, MD5)

## Slide 3 — Demo ao vivo (2–3 min)
Rodar e narrar, com o **dashboard ao vivo** (objetos, MB/s, ETA, eventos):

```bash
cd /tmp/opencode/obs-migration-demo
./run_demo.sh            # demo completa
# ou passo a passo:
python3 generate_onprem.py          # Fase 1: cria a origem + inventory.csv
python3 migrate.py --workers 64 --resume   # Fase 2: dashboard ao vivo
python3 verify.py                   # Fase 3: relatório de integridade
python3 cleanup.py                  # limpeza do bucket (opcional)
```

Pontos para destacar **enquanto roda**:
- Barra de "Arquivos" subindo rápido (milhares de objetos pequenos)
- Barra de "Dados" e o **MB/s** oscilando em tempo real
- Um item mudando para **multipart x/y** (arquivo grande)
- Contadores **OK / Falhas / Retry** sempre visíveis

## Slide 4 — Resultados da execução real (30s)
| Métrica | Valor |
|---|---|
| Objetos migrados | **5.009** (arquivos 1 KB – 20 MB) |
| Volume | **617 MB** |
| Tempo | **05:32** |
| Throughput médio | **~1.9 MB/s** (64 workers) |
| Falhas | **0** |
| Integridade (MD5) | **100% (5.009/5.009)** |

## Slide 5 — Próximos passos (30s)
- **Cutover**: apontar a aplicação para o endpoint OBS (`ap-southeast-3`)
- **Sync incremental** para sincronizar o delta até o corte final
- **Otimização de custo** (fora do escopo desta demo): lifecycle Standard → Archive
- **Cross-Region Replication** para DR

---

## Anexo técnico
- Endpoint: `https://obs.ap-southeast-3.myhuaweicloud.com`
- Bucket: `onprem-migration-demo-sgp`
- Compatibilidade: API S3 (boto3) com `signature_version=s3v4`, addressing virtual
- Credenciais via `HWC_AK`/`HWC_SK` (nunca em código/log)
- Dica de pitch: aumentar `--workers` para acelerar muitos arquivos pequenos
  (latência por requisição domina); multipart automático acima de 16 MB
