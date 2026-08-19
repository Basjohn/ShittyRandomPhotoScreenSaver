# Raw Log Manifest — 2026-08-19 P2 Evidence

Raw logs are not included in this repository-addition pack.

These hashes allow a retained external/conversation copy to be verified.

| Run | Raw ZIP | SHA-256 | Approx log time | Source SHA embedded? |
|---|---|---|---|---|
| Quantized worker rejected | `16bef115-5a8e-40ea-87c1-63437ffc68d7.zip` | `8d4fb94280dddacef25c8e210f913f1e735af1f839ced727cf1f8c133ac70ca0` | 15:15–15:17 | No |
| Pre-dedicated comparison | `21c18ab4-6738-4d89-8b39-d87136f014fb.zip` | `751cc4c10b5caf983fa75f682acd2713ed7efa0b0e95d54c48277dbe5025947a` | 15:27–15:29 | No |
| First repaired-worker installed acceptance | `41f6cf08-f731-4967-8e20-a1a987add126.zip` | `54469e6d8a305e2fa335fa5ac372a86cdca42f4f312274001713146920cd957c` | 17:05–17:10 | No |
| Second installed acceptance | `a497d069-2ff3-4a03-b553-0c160f584e74.zip` | `134f249a92f17b8885f9bf040834dba92156d5ef9b84132b501cf35f4fea6a18` | 19:04–19:08 | No |
| Third installed acceptance | `13490052-c96e-4501-b4cf-a29ba3370aca.zip` | `16f532c43154de207d9ede734b01946a262285de21c12d6b8c88a3fbfb18890c` | 19:59–20:02 | **Yes: `8ac2421e...`** |

## Archival policy

For future runs:

1. Keep the raw ZIP outside Git if desired.
2. Add its SHA-256 and filename here.
3. Add an immutable `Acceptance-*` evidence record.
4. Record `[SOURCE_HEAD]` from the log.
5. Only then proceed to the next production correction if the run changed the engineering conclusion.

If raw logs are ever moved into a durable external archive, preserve the original ZIP bytes so this
manifest remains verifiable.
