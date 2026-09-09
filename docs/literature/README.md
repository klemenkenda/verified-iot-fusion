# Reading-list sources

Local copies of the section 4 minimum reading list of [the research plan](../research_plan.md),
one file per row of [the literature matrix](../literature_matrix.csv). Filenames are the
matrix `citation_key`, so a row and its source are always one lookup apart.

**The contents of this directory are gitignored; only this README is committed.** These are
third-party works and not ours to redistribute — every one is openly accessible, but
"openly accessible" is not "redistributable in our Zenodo archive," and the Phase 11
artifact must not ship them. The table below is what makes the directory reproducible
without committing it: re-fetch with the commands at the bottom and compare checksums.

Retrieved **2026-09-09**. Checksums are SHA-256 of the file as retrieved on that date;
publishers do re-typeset papers, so a mismatch on a later fetch means the source changed,
not necessarily that something is wrong.

| File | Title | Source | SHA-256 |
| --- | --- | --- | --- |
| `kenda2019streaming.pdf` | Streaming Data Fusion for the Internet of Things | [MDPI Sensors 19(8):1955](https://doi.org/10.3390/s19081955) (CC BY) | `cc8dc147ec5e70f9a8dcf21c5f30f501f1242b0ef8cfb9c87c522661f9cf1cb0` |
| `hollmann2023caafe.pdf` | CAAFE: Context-Aware Automated Feature Engineering | [NeurIPS 2023](https://papers.nips.cc/paper_files/paper/2023/hash/8c2df4c35cdbee764ebb9e9d0acd5197-Abstract-Conference.html) | `705ecc57acaacb7e263bab5ee63c8c342e65b8d02bd3c39a57d473330ded0823` |
| `nam2024octree.pdf` | Optimized Feature Generation for Tabular Data via LLMs with Decision Tree Reasoning | [NeurIPS 2024](https://papers.nips.cc/paper_files/paper/2024/hash/a7ebe2e8d8cfd2fcec6cd77f9e6fd34d-Abstract-Conference.html) | `a32f043b1c5fea8186ab266939e34072da3bcae54838915cd70d018f7a65c6ab` |
| `abhyankar2025llmfe.pdf` | LLM-FE: Automated Feature Engineering as Evolutionary Program Search | [arXiv:2503.14434](https://arxiv.org/abs/2503.14434) (TMLR 2025) | `6d9b612720ba6c9cd47731966e23d4dae5656188a57a5c68a6e0220b916862ea` |
| `kuken2024simple.pdf` | Large Language Models Engineer Too Many Simple Features For Tabular Data | [arXiv:2410.17787](https://arxiv.org/abs/2410.17787) (TRL @ NeurIPS 2024) | `a86ae5432263a28659e50b02161375f1225cef426cb62bbe6d9a7a6d490b8f27` |
| `karami2026featehr.pdf` | FeatEHR-LLM: LLMs for Feature Engineering in Electronic Health Records | [arXiv:2604.22534](https://arxiv.org/abs/2604.22534) | `18dac84a7f277b044e60a29ad4603840c84931b1244ad71f0c75a11f9f0c1fc1` |
| `patherya2025flashfusion.pdf` | Flash-Fusion: Expressive, Low-Latency Queries on IoT Sensor Streams with LLMs | [arXiv:2511.11885](https://arxiv.org/abs/2511.11885) | `b7637b123a828dc6d0e3b065e1aac2a44aafa2f3d45f10598967f4ba6434724c` |
| `yeh2025dcats.pdf` | Empowering Time Series Forecasting with LLM-Agents (DCATS) | [arXiv:2508.04231](https://arxiv.org/abs/2508.04231) | `76c454524b126eff1ae52cc8553e5de07d7ed4230ed1ff6df2111612cd1f8d0c` |
| `ansari2025chronos2.pdf` | Chronos-2: From Univariate to Universal Forecasting | [arXiv:2510.15821](https://arxiv.org/abs/2510.15821) | `73a0da2cbfafa5eda8e28041249ff889273a386acaffd35be13a688af1364edd` |
| `feast_pit_joins.html` | Feast: point-in-time joins | [docs.feast.dev](https://docs.feast.dev/getting-started/concepts/point-in-time-joins) | `9244e237740ab7d9ba2e1b205c1672999abad3729bf1672fb06cf832934bbdf5` |
| `river_progressive_val.html` | River: `progressive_val_score` | [riverml.xyz](https://riverml.xyz/latest/api/evaluate/progressive-val-score/) | `7d6643c2534b455537e94de30506ffb1c15a1e8b3987db8021cf81da497deb69` |

The two HTML files are living documentation, not versioned publications. They are snapshots
of a page that can change under the same URL, which is exactly why the checksum and the
retrieval date are recorded — if the matrix ever cites a behaviour these pages describe, the
snapshot is the evidence, not the live URL.

## Fetch notes

- **MDPI blocks both `www.mdpi.com/.../pdf` and its landing page** (HTTP 403 to scripted
  requests). The working route is the direct attachment host:
  `https://res.mdpi.com/d_attachment/sensors/sensors-19-01955/article_deploy/sensors-19-01955.pdf`.
  Europe PMC (`PMC6514969`) has the record and the abstract but returned 404 for
  `fullTextPDF`.
- **arXiv and NeurIPS** need no special handling; arXiv PDFs are at `arxiv.org/pdf/<id>` and
  NeurIPS proceedings PDFs swap `/hash/` → `/file/` and `-Abstract-` → `-Paper-` in the
  abstract URL.
- **Identity was verified per file, not assumed.** Six PDFs and both HTML pages carry a
  `/Title` or `<title>` matching the expected work; `kenda2019streaming.pdf` and
  `nam2024octree.pdf` were confirmed by extracting first-page text. `hollmann2023caafe.pdf`
  embeds subsetted fonts with no usable text layer, so its identity rests on URL provenance
  — the proceedings hash matches the abstract page that confirmed the title.

## Re-fetching

```sh
cd docs/literature
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

curl -L -A "$UA" -o kenda2019streaming.pdf       "https://res.mdpi.com/d_attachment/sensors/sensors-19-01955/article_deploy/sensors-19-01955.pdf"
curl -L -A "$UA" -o hollmann2023caafe.pdf        "https://papers.nips.cc/paper_files/paper/2023/file/8c2df4c35cdbee764ebb9e9d0acd5197-Paper-Conference.pdf"
curl -L -A "$UA" -o nam2024octree.pdf            "https://papers.nips.cc/paper_files/paper/2024/file/a7ebe2e8d8cfd2fcec6cd77f9e6fd34d-Paper-Conference.pdf"
curl -L -A "$UA" -o abhyankar2025llmfe.pdf       "https://arxiv.org/pdf/2503.14434"
curl -L -A "$UA" -o kuken2024simple.pdf          "https://arxiv.org/pdf/2410.17787"
curl -L -A "$UA" -o karami2026featehr.pdf        "https://arxiv.org/pdf/2604.22534"
curl -L -A "$UA" -o patherya2025flashfusion.pdf  "https://arxiv.org/pdf/2511.11885"
curl -L -A "$UA" -o yeh2025dcats.pdf             "https://arxiv.org/pdf/2508.04231"
curl -L -A "$UA" -o ansari2025chronos2.pdf       "https://arxiv.org/pdf/2510.15821"
curl -L -A "$UA" -o feast_pit_joins.html         "https://docs.feast.dev/getting-started/concepts/point-in-time-joins"
curl -L -A "$UA" -o river_progressive_val.html   "https://riverml.xyz/latest/api/evaluate/progressive-val-score/"

sha256sum *.pdf *.html
```
