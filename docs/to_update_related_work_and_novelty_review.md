# Related work and novelty review: LLM-guided streaming data fusion

**Research cutoff:** 10 September 2026  
**Purpose:** Evidence and drafting material for a paper's related-work section, with a reassessment of the supplied novelty statement.  
**Inputs reviewed:** The supplied 11-entry literature matrix and Phase 0 novelty statement. The implementation, original-system audit, problem statement, and other documents linked inside those attachments were not supplied.

**Scope clarification:** The system under development is a data-fusion system; feature generation is one possible capability and output. The assessment below has been revised accordingly. Section 13 develops the fusion contribution and adds directly relevant integration literature.

## 1. Recommendation

**Update the novelty statement substantially before treating it as frozen.** The research direction remains plausible, but the current argument understates earlier temporal reasoning and omits several close competitors.

Kenda's work should be presented as a substantive foundation. The 2019 paper already discusses availability and forecast timing, and the 2022 WMAP paper is a direct continuation. The latter is the most important addition for answering the specific question about subsequent Kenda work. [Kenda et al., 2019](https://doi.org/10.3390/s19081955); [Kenda et al., 2022](https://doi.org/10.3390/su14052886).

The broader search also changes the novelty assessment. LLM-generated temporal configurations, explicit leakage control, restricted temporal computation, and verification of generated data transformations already have relevant precedents. In particular, add [Najafabadi et al., 2026](https://doi.org/10.3390/ai7070245), [ELATE](https://arxiv.org/abs/2508.14667), [Veena G, 2026](https://doi.org/10.36948/ijfmr.2026.v08i03.81173), [Featuretools](https://docs.featuretools.com/en/stable/getting_started/handling_time.html), and [Temporian](https://temporian.readthedocs.io/en/stable/reference/temporian/has_leak/).

**There are two complementary contribution candidates: synthesis of useful streaming fusion pipelines, and enforcement of their semantic and temporal contracts.** The first concerns how heterogeneous sources are combined into coherent outputs; the second concerns whether the resulting compositions preserve the specified meaning, availability, and execution constraints. Feature generation is one application of this broader system. The case for a paper can therefore include fusion quality, reduced configuration effort, robustness, and execution performance as well as forecasting accuracy. Formal guarantees strengthen that case where actually established, but are not the only possible scientific contribution.

This review does **not** establish a universal first-in-literature claim. It identifies a narrower contribution worth developing and the comparisons needed to substantiate it.

## 2. Evidence and reading conventions

This was a targeted review: primary-source checks of the matrix, citation and author-line searches around Kenda 2019, and searches for temporal AutoFE, leakage prevention, stream languages, and verification of generated transformations. Following the clarification of scope, it also includes a focused search for LLM-assisted integration and fusion-pipeline construction. It is not an exhaustive systematic review or a reproduction study.

Each annotated entry supplies a reusable citation key, bibliographic information, a source link, and its relevance. Existing matrix keys are preserved. For new entries, the keys are suggestions. Bibliographic records are integrated with the annotations so that the assessment stays next to its source.

Evidence labels used below:

- **Text:** Relevant sections of a primary paper were inspected. This does not mean its software or empirical results were independently reproduced.
- **Indexed text:** Relevant publisher-hosted sections were available through search indexing, although direct page or PDF retrieval was unreliable.
- **Documentation:** Official software documentation, release information, or repository material was inspected. Capabilities can depend on version and backend.
- **Abstract:** Suitable for identifying scope and citation relevance; insufficient for strong claims about omitted mechanisms.

Throughout, **“not established in the reviewed description” means that the evidence inspected does not substantiate a capability; it does not prove that the authors' implementation lacks it.**

## 3. Kenda 2019 and its continuation

### 3.1 The original paper needs a more accurate contrast

**`kenda2019streaming` — Klemen Kenda, Blaž Kažič, Erik Novak, Dunja Mladenić. “Streaming Data Fusion for the Internet of Things.” Sensors 19(8), 1955, 2019. Evidence: Text.**

The paper defines heterogeneous stream fusion with configured aggregates, history, and contextual sources. Section 3.1 and Figure 1 distinguish current time, an available-data horizon, and a prediction horizon. Section 3.7 represents forecasts using generation and forecasted timestamps and accommodates updated forecasts. Section 4.5 checks whether required streams and history are available; Algorithm 2 specifies an error for inadequate history. Section 6 includes predictive and processing-performance evaluation. [Primary PDF](https://mdpi-res.com/d_attachment/sensors/sensors-19-01955/article_deploy/sensors-19-01955-v2.pdf).

**Implication:** It is inaccurate to describe this predecessor as concerned only with what to compute. The defensible extension concerns explicit decision-cutoff eligibility for individual records and revisions, and compositional enforcement across generated programs. Its mathematical description and practical buffering are not, by themselves, a proof of that stronger contract.

### 3.2 A direct application and evaluation continuation, 2020

**`kenda2020waterprediction` — Klemen Kenda, Jože Peternelj, Nikos Mellios, Dimitris Kofinas, Matej Čerin, Jože Rožanec. “Usage of statistical modeling techniques in surface and groundwater level prediction.” Journal of Water Supply: Research and Technology—AQUA 69(3), 248–265, 2020. Evidence: Text.**

This paper cites the 2019 fusion work and studies feature generation, selection, heterogeneous data fusion, tuning, and evaluation in water-level prediction. It compares 21 regression and classification techniques and develops historical and weather-derived predictors. Its results distinguish predictive accuracy from the lower update cost of incremental models. [DOI](https://doi.org/10.2166/aqua.2020.143); [author-hosted PDF](https://ailab.ijs.si/wp-content/uploads/2021/04/usage.pdf).

**Use in the paper:** Cite for the practical value of enriched stream-derived features and for a credible expert-designed baseline. It does not establish LLM synthesis or a verifier for arbitrary generated feature programs.

### 3.3 FASTENER: an associated feature-selection branch, 2020

**`koprivec2020fastener` — Filip Koprivec, Klemen Kenda, Beno Šircelj. “FASTENER Feature Selection for Inference from Earth Observation Data.” Entropy 22(11), 1198, 2020. Evidence: Indexed text.**

FASTENER cites the fusion paper and supplies a multiobjective genetic feature-selection method. It balances predictive quality and feature count, using information-theoretic measures during search. Evaluation includes Sentinel-2 land-cover data and additional selection benchmarks. [Publisher article](https://www.mdpi.com/1099-4300/22/11/1198).

**Use in the paper:** This is a selection method, rather than a temporal program generator. It nevertheless shows that the surrounding research programme includes automatic search, not only fixed expert configurations. If selection is part of the proposed method, distinguish selecting existing candidates from synthesizing their computations.

### 3.4 NAIADES: project-level continuation and operational lessons

**`naiades2020d55` — NAIADES consortium, responsible authors including Klemen Kenda and Georgia Lytra. “NAIADES Water demand prediction toolkit – Mid-term,” deliverable D5.5, final draft dated 30 November 2020. Evidence: Text; project report.**

The report describes feature engineering and selection within a streaming prediction pipeline. Its discussion of in-memory fusion buffers explicitly considers different source frequencies and delays, and reliability problems when an unstable component loses buffered data. A dedicated streaming database is discussed as a planned improvement; that passage should not be cited as evidence that the improvement was already deployed. [Project PDF, especially Sections 4.5 and 5](https://naiades-project.eu/sites/default/files/2021-06/naiades_water_demand_prediction.pdf).

The [CORDIS results page](https://cordis.europa.eu/project/id/820985/results) also lists final prediction-toolkit and data-fusion-middleware deliverables. Their full contents were not retrieved successfully in this review. They remain relevant follow-up material, rather than evidence for an additional verified capability.

### 3.5 The central missing successor: WMAP, 2022

**`kenda2022architectures` — Klemen Kenda, Nikolaos Mellios, Matej Senožetnik, Petra Pergar. “Computer Architectures for Incremental Learning in Water Management.” Sustainability 14(5), 2886, 2022. Evidence: Indexed text.**

WMAP incorporates the 2019 fusion methodology into an architecture with streaming and batch components. Section 3.3 discusses systematic delays, differing source frequencies, regularly updated weather forecasts, and consolidation to a master time. Section 3.4 describes configurable historical aggregates and derivatives, feature analysis, and selection; the article connects to the water-prediction and FASTENER work. It also evaluates operational processing performance. [Publisher article, Sections 2.3–2.4 and 3.3–3.4](https://www.mdpi.com/2071-1050/14/5/2886).

**Implication:** Use this as the main continuation citation and as part of the expert-baseline specification. A plausible advance is enforcing a richer eligibility contract during synthesis and compilation. Claiming the introduction of temporal fusion or deployable stream feature engineering would be untenable.

### 3.6 A later author-line branch: causal temporal features, 2025

**`hosseini2025causalfeatures` — Seyed Iman Hosseini, Klemen Kenda, Dunja Mladenič. “Temporal Dynamics and Causal Feature Integration for Predictive Maintenance in Manufacturing Systems: A Causality-Informed Framework.” SiKDD / Information Society 2025. Evidence: Text.**

The study constructs temporal features through lag analysis and causal modelling, with a chronological evaluation on a manufacturing predictive-maintenance task. Its engineered causal features did not improve on the raw-feature baseline in the reported experiment. [Author-hosted paper](https://aile3.ijs.si/dunja/SiKDD2025/Papers/IS2024_-_SIKDD_2025_paper_12.pdf).

**Use in the paper:** Cite as a related later research branch, not as a demonstrated new version of the 2019 implementation. It is also useful evidence that additional domain-informed temporal features need empirical justification. Causal discovery and availability correctness are separate questions.

### 3.7 Adjacent streaming-integration work

**`tu2020isdi` — Doan Quang Tu, A. S. M. Kayes, Wenny Rahayu, Kinh Nguyen. “IoT streaming data integration from multiple sources.” Computing 102, 2299–2329, 2020. Evidence: Publisher abstract and bibliographic record.**

The ISDI line develops window-based integration, time alignment, and deduplication of heterogeneous streams. Its 2019 conference predecessor appears in the surrounding fusion literature. [Publisher article](https://link.springer.com/article/10.1007/s00607-020-00830-9).

**Use in the paper:** Include if positioning against data-integration systems. It is a distinct research line and should not be labelled a Kenda-authored continuation.

### 3.8 What the continuation changes

The related-work argument should progress from **expert-configured fusion**, through **operational prediction and selection**, to the proposed **constrained synthesis and enforcement**. This makes the scientific extension assessable without relying on alleged defects in a predecessor's code.

The supplied novelty statement refers to an audit of a particular revision. That audit was not available here. A revision-specific defect may motivate a regression test, but it cannot establish that a published method lacks temporal semantics. Likewise, the matrix's broad characterization of QMiner as closed source needs correction or version-specific evidence: there is a [public QMiner source repository](https://github.com/qminer/qminer).

## 4. Missing work that directly affects novelty

### 4.1 LLM feature engineering with explicit temporal leakage control

**`najafabadi2026temporalleakage` — Maryam Khanian Najafabadi, Bushra Naeem, Touraj Khodadadi, Saman Shojae Chaeikar, Zawar Shah. “LLM-Guided Automated Feature Engineering for Time Series Data with Temporal Leakage Control.” AI 7(7), 245, published 1 July 2026. Evidence: Indexed text.**

The framework uses task descriptions and a user-specified temporal configuration to generate structured feature configurations. It separates antecedent variables from consequent variables and routes the latter through strictly historical, entity-grouped aggregation. Configurations include output types, transformations, and aggregation windows. Temporal splitting and validation-based selection are explicit. [Publisher article, Sections 3.5–3.8](https://www.mdpi.com/2673-2688/7/7/245).

**Novelty consequence:** This directly overlaps with LLM generation plus enforced temporal constraints. The reviewed mechanism assumes that relevant past observations are available before the current prediction; it does not establish a general contract for arbitrary publication delays, revised records, and bounded streaming execution. Compare against those precise assumptions. Do not describe this work as merely prompting the LLM to avoid leakage.

### 4.2 ELATE: direct time-series AutoFE competition

**`murray2025elate` — Andrew Murray, Danial Dervovic, Michael Cashmore. “ELATE: Evolutionary Language model for Automated Time-series Engineering.” arXiv:2508.14667, 2025. Evidence: Text, v1.**

ELATE combines an LLM with evolutionary feature search, time-series statistical context, and feature-importance pruning. It restricts generated Python expressions through AST validation. Its evaluation uses walk-forward forecasting on seven datasets; the formulation explicitly identifies a lagged target available at prediction time. [Paper, Sections 4–5](https://arxiv.org/html/2508.14667v1).

**Novelty consequence:** This is a closer general forecasting comparator than Flash-Fusion or DCATS. It already combines time-series context, search, restricted expressions, and chronological evaluation. A general arrival/revision-aware stream semantics is not established in the inspected description. The proposed work should explain what additional cases its contract admits or rejects.

### 4.3 Verification of generated data transformations

**`veenag2026pipelineverification` — Veena G. “Verifying LLM-Generated Data-Pipeline Transformations: A Hybrid Static–Semantic Approach for Leakage and Data-Quality Faults.” International Journal for Multidisciplinary Research 8(3), 2026, article 81173. Evidence: Text.**

This paper combines static analysis of SQL transformations with executed invariants and metamorphic checks. Its fault taxonomy includes temporal and target leakage, grain mismatch, join fanout, row loss, and quality faults. A temporal check compares historical outputs with outputs after removing future rows. Evaluation uses a small fault-injection study on synthetic and Rossmann-derived data; naturally generated LLM transformations remain future work. [Primary PDF](https://www.ijfmr.com/papers/2026/3/81173.pdf); [DOI](https://doi.org/10.36948/ijfmr.2026.v08i03.81173).

**Novelty consequence:** Deterministic diagnostics and semantic checks for LLM-related data pipelines are not standalone novelty. The meaningful distinction would be a sound restricted language and an explicit availability/revision contract, rather than an empirical detector for selected faults. Its modest evaluation limits the strength of empirical comparisons, but not the relevance of the conceptual overlap.

### 4.4 Featuretools: time-aware automatic feature computation

**`featuretools_handling_time` — Featuretools documentation, “Handling Time.” Evidence: Documentation; current and historical versioned pages.**

Featuretools applies cutoff times when computing automatically synthesized features. Its secondary time index can represent columns that become known later than a row's primary timestamp, such as information recorded after an event begins. Cutoff-boundary inclusion is configurable. These mechanisms go beyond retrieving precomputed features. [Current guide](https://docs.featuretools.com/en/stable/getting_started/handling_time.html); [version 0.19.0 guide](https://docs.featuretools.com/en/v0.19.0/automated_feature_engineering/handling_time.html).

**Novelty consequence:** Availability-aware automatic computation has substantial prior art. An adequate comparison must consider whether existing cutoff and secondary-index mechanisms can encode the proposed benchmark, and identify specific revision, lineage, or execution guarantees that they do not establish.

### 4.5 Temporian: restrictions on temporal computation

**`temporian_leak_detection` — Temporian documentation, user guide and `has_leak`. Evidence: Documentation.**

Temporian documents temporal operators designed to avoid future leakage except through an explicit `leak` operator. `has_leak` checks a computation graph for dependence on that operator. Its inputs also carry schemas and types. [User guide](https://temporian.readthedocs.io/en/stable/user_guide/); [graph check](https://temporian.readthedocs.io/en/stable/reference/temporian/has_leak/).

**Novelty consequence:** Restricting a temporal language and checking its graph is not new in itself. The comparison must explain what the input timestamps mean and how late publications and forecast revisions are represented. A graph can be causal relative to its declared timestamps while its inputs were backdated incorrectly. That is an input-contract issue, not evidence that the graph checker fails its documented purpose.

### 4.6 Formal stream languages and bounded resources

**`faymonville2019rtlola` — Peter Faymonville, Bernd Finkbeiner, Maximilian Schwenger, Hazem Torfah. “Real-time Stream-based Monitoring.” arXiv:1711.03829, first submitted 2017; revised version 2019. Evidence: Primary abstract.**

RTLola supplies a formal stream language with real-time sliding windows. Its analysis makes memory guarantees under stated output-rate and aggregation assumptions; it explicitly recognizes that a finite time window can contain arbitrarily many events. [Primary record](https://arxiv.org/abs/1711.03829).

**`convent2018tessla` — Lukas Convent, Sebastian Hungerecker, Martin Leucker, Torben Scheffel, Malte Schmitz, Daniel Thoma. “TeSSLa: Temporal Stream-Based Specification Language.” SBMF 2018, pp. 144–162. Evidence: Text.**

TeSSLa formalizes computation over asynchronous timestamped streams and proves properties of the language and monitor implementation. [Publisher chapter](https://link.springer.com/chapter/10.1007/978-3-030-03044-5_10).

**Novelty consequence:** Formal stream semantics, temporal restrictions, and resource reasoning should be cited as foundations. They are not specific to LLM feature engineering. The new contribution must lie in the prediction-information contract, its realization in the admitted language, and its connection to synthesis and evaluation.

### 4.7 General verifiable code generation

**`sun2024clover` — Chuyue Sun, Ying Sheng, Oded Padon, Clark Barrett. “Clover: Closed-Loop Verifiable Code Generation.” SAIV 2024, pp. 134–155. Evidence: Author abstract and bibliographic record.**

Clover combines LLMs and formal tools to check consistency between code, documentation, and formal annotations, with evaluation on annotated Dafny programs. [Author publication page](https://theory.stanford.edu/~barrett/pubs/SSP%2B24-abstract.html).

**Novelty consequence:** A generate–verify architecture is established. Cite this family when explaining why the generator can remain untrusted while acceptance is governed by independently specified checks.

## 5. Reassessment of the existing matrix

### 5.1 CAAFE

**`hollmann2023caafe` — Hollmann et al. “Large Language Models for Automated Data Science: Introducing CAAFE for Context-Aware Automated Feature Engineering.” NeurIPS 2023. Evidence: Text.**

CAAFE generates feature transformations from dataset context and uses execution/error and predictive feedback. Its implementation restricts operations; its technical evaluation setup describes ten random splits and an accuracy/AUC criterion. The paper does not establish the proposed record-availability contract. [Conference paper](https://papers.nips.cc/paper_files/paper/2023/hash/8c2df4c35cdbee764ebb9e9d0acd5197-Abstract-Conference.html).

**Correction:** Retain the distinction between operational validity and temporal admissibility, but acknowledge the checks it actually performs. Random-split tabular evaluation does not imply that leakage is conceptually impossible in tabular tasks: target proxies and information unavailable at the intended prediction moment remain relevant.

### 5.2 OCTree and Enefit

**`nam2024octree` — Nam et al. “Optimized Feature Generation for Tabular Data via LLMs with Decision Tree Reasoning.” NeurIPS 2024. Evidence: Text.**

OCTree is important because it includes Enefit with time-index splitting. Appendix B.1 lists flattened model inputs, and Table 13 reports Enefit relative improvements of 2.3% for GPT-4o OCTree and 0.4% for CAAFE. [Conference paper and supplement](https://papers.nips.cc/paper_files/paper/2024/hash/a7ebe2e8d8cfd2fcec6cd77f9e6fd34d-Abstract-Conference.html).

**Correction:** Absence of release/version keys from the listed model inputs does not prove that preprocessing discarded their information or selected ineligible values. The reviewed description does not establish record-level release/revision verification; a stronger claim requires auditing the joins and preprocessing. Published percentage improvements are context, not a fixed threshold that H1 must beat. Different splits, preprocessing, tuning, and starting feature sets prevent that interpretation. Rerun comparable methods under a shared protocol.

### 5.3 LLM-FE

**`abhyankar2025llmfe` — Nikhil Abhyankar, Parshin Shojaee, Chandan K. Reddy. “LLM-FE: Automated Feature Engineering for Tabular Data with LLMs as Evolutionary Optimizers.” TMLR 2026; arXiv first submitted 2025. Evidence: Text, v3; author project/repository publication status.**

The evolutionary program-search comparison remains relevant. The paper uses execution filtering and constrains its experimental generation budget by LLM samples. [Paper](https://arxiv.org/html/2503.14434v3); [authors' repository](https://github.com/nikhilsab/llmfe).

**Correction:** An LLM-sample budget is a legitimate, incomplete resource normalization, not evidence by itself of a concealed compute advantage. Report candidate evaluations, model fits, tokens, elapsed time, and cost separately. Keep the existing citation key if convenient, but use 2026 for the journal version; the matrix's exact publication month was not confirmed here.

### 5.4 Simple-feature criticism

**`kuken2024simple` — Küken et al. “Large Language Models Engineer Too Many Simple Features For Tabular Data.” Table Representation Learning Workshop at NeurIPS 2024. Evidence: Primary abstract/record.**

This is relevant critical evidence about the complexity and value of LLM-generated tabular features. [Primary record](https://arxiv.org/abs/2410.17787).

**Correction:** It motivates strong simple baselines and analysis of operator usage. It does not establish that this project's M3 baseline will be strong, or predict the result of H1 on Enefit. Those remain empirical questions.

### 5.5 FeatEHR-LLM

**`karami2026featehr` — Hojjat Karami, David Atienza, Jean-Philippe Thiran, Anisoara Ionescu. “FeatEHR-LLM: Leveraging Large Language Models for Feature Engineering in Electronic Health Records.” arXiv:2604.22534, 2026. Evidence: Text, v1.**

The paper generates executable features from irregular clinical histories using task/schema context and specialized temporal tools, with iterative validation. Section 3.2's metadata also includes units and summary statistics. [Paper](https://arxiv.org/html/2604.22534v1).

**Correction:** Describe this as avoiding raw patient records in the LLM interface, rather than equating it with a strictly data-independent schema-only interface. It remains a useful irregular-time comparator, but the new temporal papers in Section 4 are more direct tests of the leakage-control claim. A separate publication/arrival contract was not established in the inspected description.

### 5.6 Feast

**`feast_pit_joins` — Feast point-in-time join documentation and release v0.66.0. Evidence: Documentation and repository change records.**

The supplied statement about `filter_by_created_timestamp` is supported by current repository documentation and the change included in v0.66.0. It adds a created-timestamp eligibility condition, with opt-in behavior and backend constraints. [Repository documentation](https://github.com/feast-dev/feast/blob/master/docs/getting-started/concepts/point-in-time-joins.md); [implementation PR](https://github.com/feast-dev/feast/pull/6617); [release](https://github.com/feast-dev/feast/releases/tag/v0.66.0).

**Correction:** Pin the version; do not imply this option existed throughout Feast's history. Being disabled by default is not a strong scientific distinction: a comparator can enable it. Also state the metadata assumption—creation time must appropriately represent availability for the intended reconstruction. Compare the scope of protected computations and version semantics, not just the default setting.

### 5.7 River

**`river_progressive_val` — River documentation, `evaluate.progressive_val_score`. Evidence: Documentation.**

The `moment` and `delay` parameters support prediction followed by later evaluation/learning when a label arrives. [API documentation](https://riverml.xyz/latest/api/evaluate/progressive-val-score/).

**Correction:** Keep this as protocol infrastructure. Delayed-label evaluation does not automatically establish the eligibility of every input feature. Label availability and covariate availability need separate contracts.

### 5.8 Peripheral sources and the numerical-forecaster boundary

| Existing citation key | Verified identity and scope | Recommended treatment |
| --- | --- | --- |
| `patherya2025flashfusion` | Patherya et al., **Flash-Fusion: Enabling Expressive Low-Latency Queries on IoT Sensor Streams with LLMs**, arXiv:2511.11885, 2025. Telemetry-query infrastructure. [Record](https://arxiv.org/abs/2511.11885). Evidence: Abstract. | Optional context for LLM/IoT systems; not a principal predictive-feature baseline. |
| `yeh2025dcats` | Yeh et al., **Empowering Time Series Forecasting with LLM-Agents**, arXiv:2508.04231, 2025. Agent-driven data preparation for forecasting. [Record](https://arxiv.org/abs/2508.04231). Evidence: Abstract. | Cite for the broader data-preparation setting. Avoid strong claims about unsupported operations based only on this scope check. |
| `ansari2025chronos2` | Ansari et al., **Chronos-2: From Univariate to Universal Forecasting**, arXiv:2510.15821, 2025. A pretrained time-series forecasting model. [Record](https://arxiv.org/abs/2510.15821). Evidence: Abstract. | Optional predictor comparator. It is not an example of a general-purpose conversational LLM directly forecasting raw telemetry. Correct that scope argument. |

## 6. Additional foundations worth citing

These sources prevent the related-work section from implying that feature construction, units, and temporal data processing started with LLMs.

| Suggested citation key | Source and contribution relevant here | Use |
| --- | --- | --- |
| `kanter2015dfs` | James Max Kanter and Kalyan Veeramachaneni, **Deep Feature Synthesis: Towards Automating Data Science Endeavors**, DSAA 2015. Compositional feature construction over relational data. [Author PDF](https://groups.csail.mit.edu/EVO-DesignOpt/groupWebSite/uploads/Site/DSAA_DSM_2015.pdf). | Non-LLM feature-synthesis foundation. Do not retroactively attribute every modern Featuretools facility to this paper. |
| `horn2020autofeat` | Franziska Horn, Robert Pack, Michael Rieger, **The autofeat Python Library for Automated Feature Engineering and Selection**, arXiv:1901.07329, first submitted 2019, revised 2020. Section 2.1 uses physical units to retain legal combinations and derive dimensionless quantities. [Paper](https://arxiv.org/pdf/1901.07329). | Unit-aware AutoFE already exists. State the new unit rules precisely instead of claiming the first physically valid feature generation. |
| `cerqueira2024vest` | Vitor Cerqueira, Nuno Moniz, Carlos Soares, **VEST: automatic feature engineering for forecasting**, Machine Learning 113, 4523–4545, 2024; first online 2021. [Publisher article](https://link.springer.com/article/10.1007/s10994-021-05959-y). | Traditional automated forecasting-feature baseline. Keep online and issue dates distinct. |
| `costa2021autofits` | Pedro Costa, Vitor Cerqueira, João Vinagre, **AutoFITS: Automatic Feature Engineering for Irregular Time Series**, arXiv:2112.14806, 2021. [Record](https://arxiv.org/abs/2112.14806). | Optional precedent for irregular-time feature construction without LLMs. |
| `akidau2015dataflow` | Tyler Akidau et al., **The Dataflow Model: A Practical Approach to Balancing Correctness, Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing**, PVLDB 8, 1792–1803, 2015. [Google Research publication](https://research.google/pubs/the-dataflow-model-a-practical-approach-to-balancing-correctness-latency-and-cost-in-massive-scale-unbounded-out-of-order-data-processing/). | Event/processing time, windows, and handling late data are established stream-processing concerns. Application availability still needs an explicit interpretation. |
| `kaufman2012leakage` | Shachar Kaufman, Saharon Rosset, Claudia Perlich, Ori Stitelman, **Leakage in data mining: Formulation, detection, and avoidance**, ACM TKDD 6(4), article 15, 2012. [Journal DOI](https://doi.org/10.1145/2382577.2382579); [earlier KDD 2011 paper inspected](https://www.cs.umb.edu/~ding/history/470_670_fall_2011/papers/cs670_Tran_PreferredPaper_LeakingInDataMining.pdf). | Information legitimacy and separation of learning/prediction are longstanding concerns. Do not conflate the earlier three-author version with the journal bibliography. |
| `li2026topofe` | Sha Li and Naren Ramakrishnan, **Adaptive Graph-of-Islands Evolution for Automatic Feature Engineering with LLMs**, arXiv:2607.23286, v2 dated 2 September 2026; the earlier title used TOPOFE. [Record](https://arxiv.org/abs/2607.23286). | Recent evolutionary tabular AutoFE. Prevents presenting LLM-FE as the uncontested endpoint of the search literature. Temporal-verification capabilities were not established by this abstract-level check. |

## 7. Specific edits to the novelty statement

The following recommendations concern the supplied text, not an inspected implementation.

| Current wording or argument | Recommended change | Basis |
| --- | --- | --- |
| The predecessor names delayed data as an open issue and “did not solve it.” | Separate the published method, the reported implementation revision, and the stronger contract proposed now. Remove the categorical dismissal. | Sections 3.1–3.5. |
| “Nothing in the matrix does any part of this.” | Replace with a capability-by-capability comparison that includes the missing sources. The matrix is a search result, not a boundary on prior art. | Sections 4 and 6. |
| All generators accept candidates through exactly two tests. | Describe the actual checks of each method and distinguish syntax, permitted operations, task-specific temporal rules, dynamic invariants, and formal guarantees. | Sections 4–5. |
| OCTree has “no correctness check of any kind” and discards Enefit's availability structure. | State that the inspected paper does not establish the proposed release/revision contract; reserve code-level accusations for a reproducible audit. | Section 5.2. |
| Stable verifier diagnostic codes are the novel part of feedback. | Treat diagnostic feedback as established practice. Test whether this particular taxonomy and feedback improve valid-program yield, search efficiency, or predictive quality. | Section 4.3. |
| Feast's default setting is a key distinction. | Enable relevant existing protections in the comparator. Focus on semantic coverage and guarantees. | Section 5.6. |
| The compiler “proves” correctness and batch equivalence. | Use this verb only for a stated theorem with assumptions and a proof, or a sound proof-producing procedure. Differential tests support tested agreement, not universal equivalence. | Required distinction between proposed claims and available evidence. |
| A restricted DSL prevents all temporal leakage. | Scope the guarantee to admitted programs, trusted source metadata, approved operators, and the specified feature-computation boundary. | Section 8 below. |
| “Evaluation under recorded availability” is already cheaply defensible. | Audit what the dataset records. Distinguish actual arrival logs, publisher release blocks, issue times, and assumed lags. | Section 9.1. |
| Published Enefit gains are the bar H1 must clear. | Define H1 using matched reruns and uncertainty under one evaluation protocol. | Section 5.2. |

Also remove the claim that leakage is irrelevant to i.i.d. tabular tasks. The data structure and split strategy do not determine whether a predictor uses information unavailable at its intended deployment decision.

## 8. Proposed replacement novelty statement

### 8.1 Central statement suitable for the project memo

> The proposed work investigates LLM-guided construction of executable data-fusion pipelines for heterogeneous streams. From source metadata and task requirements, the system proposes compositions of supported alignment, combination, and transformation operations that produce coherent fused outputs, including feature streams for predictive models. A restricted typed language and deterministic checks govern the semantic, temporal, and resource constraints of these compositions, including information availability and forecast-version selection where applicable. The research will evaluate whether this approach reduces manual configuration effort and improves fusion quality and robustness, while measuring downstream predictive usefulness as one application. Guarantees are stated only for properties established for the admitted language and are conditional on source metadata and operator implementations.

This wording deliberately states a proposed contribution. Once implemented, replace future-oriented language with the exact properties proved and results observed; do not upgrade it solely because tests pass.

### 8.2 Contributions that could support the paper

1. **Synthesis of streaming fusion pipelines.** Define which source-combination decisions the system constructs or configures, such as alignment, resampling, joins, normalization, and source/version selection. Evaluate the quality and effort of producing a complete supported pipeline from task and source descriptions. Claim only the decisions actually automated; neither automatic source discovery nor entity resolution is a prerequisite for a scoped fusion contribution.
2. **A precise fusion and eligibility semantics.** Specify how supported compositions preserve entity identity, temporal meaning, units, provenance, and information eligibility. Include late observations, future-valid forecasts, revised values, and contextual sources where supported. Show which interactions require more than independently correct single-source operators.
3. **An enforcement and execution result.** Define the admitted language and trusted components. Establish soundness of the checks and, if claimed, correctness of the batch implementation relative to the reference semantics. State restrictions on missing values, numerical behavior, and state.
4. **An empirical study of constrained search.** Separate the value of LLM proposals from the value of the grammar, expert operators, verification, and feedback. Measure accepted-pipeline yield, fusion correctness, configuration effort, and downstream usefulness under explicit budgets.
5. **A reproducible fusion benchmark protocol.** Release source-level inputs, expected alignments or fused outputs, record-selection rules, replay cases, baselines, and diagnostics. Availability-sensitive forecasting can supply one application, with direct fusion tests supplying evidence independent of a predictor.

Each contribution needs evidence independently. A positive accuracy result does not prove soundness; a sound language does not establish that an LLM improves feature search.

### 8.3 What must remain explicitly outside the claim

The method does not establish that external metadata is truthful, that an LLM has no memorized benchmark knowledge, that observational features identify causal effects, or that every mathematically meaningful temporal feature is expressible. It also cannot guarantee a global memory bound merely by requiring finite windows.

“Invalid unit operations” should mean violations of specified dimensional rules, not all scientific nonsense. For example, dimensional consistency alone cannot determine whether aggregating a variable is meaningful for a domain task. Affine units such as absolute temperatures may require rules beyond multiplying unit exponents.

## 9. Make the proposed distinction concrete

The following is this review's suggested formalization, not a claim copied from a prior paper or an assessment that the supplied project already implements it.

### 9.1 Define the information available to each prediction

For a prediction made at decision time `d`, distinguish:

- `event_time`: when an observation describes the world;
- `available_time`: when that particular record/version becomes eligible for the deployed predictor;
- `issue_time`: when a forecast is generated;
- `valid_time`: the time the forecast describes;
- `revision_id`: the identity or order of updates to a logical value;
- `target_time`: the outcome time being predicted.

Define an eligible input view `E_d` using `available_time <= d`, together with an explicit policy for equality, versions, source precedence, and any additional forecast-horizon constraints. A feature program must read only through that view. Forecast issue time may precede dissemination; do not silently equate the two.

The important property is information noninterference: **changing records that are ineligible at `d` must not change the feature vector emitted for that decision.** More formally, for a fixed admitted program and fixed eligible learned state, inputs with identical eligible views must produce identical decision-time features. If ingestion order is semantically relevant, the eligible view must include that order; otherwise specify canonical ordering.

This formulation protects the actual information boundary. An event-time lag or a chronological train/test split alone does not define that boundary.

### 9.2 Minimal distinguishing examples

| Situation at an 11:00 decision | Correct treatment | Why a simpler rule can be insufficient |
| --- | --- | --- |
| A measurement describes 09:00 but is first released at 12:00. | Exclude it from the 11:00 prediction. | A past event timestamp does not imply availability. |
| A weather forecast issued at 08:00 and released at 08:10 describes tomorrow at 14:00. | It may be eligible, subject to the task's forecast-selection policy. | Banning all future valid timestamps rejects legitimate information. |
| Yesterday's reading was published then, but corrected today at 13:00. | Use the version available by 11:00. | A latest-value historical table can silently rewrite the past. |
| A prior target has occurred but its label is released at 12:00. | Exclude it from target-derived features and learning at 11:00. | A one-row shift is unsafe if label delay exceeds one interval. |
| A source update and prediction share the timestamp 11:00. | Apply the declared tie/order policy. | Timestamp equality alone cannot determine whether publication preceded the decision. |

These examples are suitable for contrasting contracts. They should not be presented as discovered bugs in a named baseline unless reproduced against that baseline's stated assumptions.

### 9.3 Separate four kinds of evidence

| Evidence | What it can establish | What it cannot establish by itself |
| --- | --- | --- |
| Static checking with a proved soundness result | Every accepted program satisfies specified properties under the stated model. | Correct external metadata or correctness beyond the model. |
| Runtime guards | A checked condition held or a violation was caught in the observed execution. | Universal program correctness. |
| Metamorphic and adversarial tests | The implementation passes or fails selected semantic challenges. | That all possible violations are excluded. |
| Batch/stream differential tests | The two implementations agree on tested cases within stated numerical tolerances. | Universal equivalence, or correctness if both share the same faulty input construction. |

For a state bound, account for event density, distinct entities, revision history, joins, and buffers waiting for late sources. A finite-duration window does not bound the number of retained records if rate is unrestricted. A per-entity bound does not imply a global bound when entities can grow indefinitely. Declare cardinality/rate assumptions, supported constant-state summaries, approximation, or rejection/eviction policies as appropriate.

Finally, enforce cutoffs for fitted transformations, selection statistics, prompt summaries, model training, and labels. Feature-level dependency checking alone cannot prevent a feature generator from being guided by test-period target statistics.

## 10. Evaluation changes suggested by the literature

### 10.1 Ground the Enefit availability claim in the actual release mechanism

The official dataset documentation states that records sharing a `data_block_id` become available at the same forecast time, 11 a.m. each morning. It distinguishes forecast origin and valid timestamps, describes delayed historical-weather and revealed-target availability, and notes timezone conventions and unit differences. [Official Enefit data description](https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/data).

Therefore, prefer **“evaluation reconstructed from documented release blocks and forecast metadata”** unless actual arrival/dissemination logs are available. Preserve the original release and version information during joins. Document how block identifiers map to cutoffs, how timezone changes are handled, which versions are retained, and what is assumed rather than observed. Unit conversions also need checking; the documentation, for example, distinguishes some forecast and historical precipitation/snow units.

The dataset files themselves were not supplied for this review. The proposal should not claim that they retain a complete arbitrary revision history until that has been checked.

### 10.2 Separate fusion quality, downstream performance, and correctness

**Fusion track:** Start competing fusion systems from the same heterogeneous source streams and the same documented task requirements. Measure correctness of source alignment and fused values, coverage, provenance, treatment of missing or revised data, configuration effort, and resource use. Use expert-labelled cases or independently specified reference outputs where possible. Supplying a prejoined table would remove much of the problem the proposed system claims to solve.

**Performance track:** Give every method the same eligible information, train/validation/test cutoffs, prediction horizons, target definition, downstream learner, and comparable tuning budget. Freeze the test period before feature search. Keep feature selection, prompt-derived data summaries, and learned preprocessing inside the development period. Report multiple search seeds and uncertainty that respects temporal dependence, for example paired evaluation over forecast blocks rather than pretending adjacent observations are independent.

For a controlled feature-generation comparison, a fixed fused input view is appropriate. Label this separately from the source-to-output fusion experiment. These two setups isolate different parts of the system.

**Correctness track:** Use independently specified cases covering late arrivals, revised history, duplicate timestamps, missing sources, changing entities, future-valid forecasts, delayed labels, and illegal operator compositions. Include valid difficult cases to measure false rejection, not just detection of deliberately invalid programs. Expand the fault corpus beyond examples used to design the verifier. Report whether a result comes from proof, static rejection, runtime detection, or testing.

These tracks answer different questions. Making an unsafe pipeline safer can lower an inflated offline score. That is evidence of corrected evaluation, not necessarily poorer forecasting from legitimate information.

### 10.3 Baseline roles and priorities

The table retains the comparisons needed for the forecasting and feature-search experiments. For the broader fusion claim, the primary comparison is expert-configured and automatically configured fusion on source-level inputs; see Section 13. AutoFE methods need not all be full-system baselines.

| Baseline or comparison | Question it answers | Priority |
| --- | --- | --- |
| Expert features informed by the Kenda 2019–2022 line | Does synthesis improve on a credible configured fusion pipeline? | Essential; update M2's definition. |
| Random/enumerative or evolutionary search over the identical admitted DSL | Does the LLM improve proposal quality beyond the language and operators? | Essential; a central M3 comparison. |
| Same LLM and grammar, with and without structured verifier feedback | Does feedback improve valid-program yield, efficiency, or forecast quality? | Essential ablation for the proposed loop. |
| A Featuretools/Temporian implementation of overlapping feature families | How much of the contract and useful computation already comes from established tools? | Essential semantic comparison; implement matched cases where feasible. |
| Najafabadi et al.'s temporal-configuration approach | What is gained beyond feature-class restrictions and historical aggregation? | High priority. |
| ELATE | What is gained beyond direct LLM time-series feature search? | High priority predictive comparator. |
| OCTree | How does the method compare with a published LLM feature generator already evaluated on Enefit? | High priority, using matched reruns. |
| LLM-FE and a traditional method such as VEST | How competitive is the search against broader AutoFE alternatives? | Useful breadth, subject to reproduction budget. |
| Dynamic invariant/metamorphic checking inspired by Veena G | What does static enforcement add beyond an empirical fault detector? | Useful correctness comparison. |

An adaptation should be labelled as such. For example, wrapping a baseline in the new DSL changes what is being compared. Separate an original-method reproduction from a controlled same-language proposer comparison.

If resources are limited, prioritize M2, same-DSL non-LLM search, feedback ablations, and one strong temporal LLM comparator. Retain the remaining methods in the conceptual comparison even when a fair reproduction is unavailable.

### 10.4 Measure search cost without conflating budgets

Record attempted programs, distinct accepted programs, feature-set evaluations, downstream model fits, generated feature counts, LLM tokens/calls, wall time, and monetary cost. Candidate evaluations alone can hide differing feature-set sizes and fitting costs; LLM samples alone can hide differing amounts of local search. State which dimension is held fixed and report the others.

To assess benchmark familiarity, include an ablation with anonymized metadata where meaningful, retain prompts and outputs, and consider an additional less-public dataset. Anonymization is a diagnostic, not proof against contamination; it also removes semantic context and can affect legitimate performance.

## 11. Suggested related-work structure for the paper

1. **Streaming fusion and automated integration:** Introduce the practical problem, cite the Kenda lineage and optionally ISDI, then compare LLM-assisted integration and constrained ingestion from Section 13. Explain which fusion decisions the system automates and verifies.
2. **Automatic and LLM-guided feature engineering:** Position feature construction as a supported application or subsystem. Establish traditional synthesis and unit-aware construction, then the relevant LLM AutoFE and temporal methods. Allocate space according to the experiments rather than treating every AutoFE paper as a direct full-system competitor.
3. **Information availability and leakage control:** Relate the prediction cutoff to Featuretools, Feast, Temporian, classical leakage work, and delayed-label evaluation. Explain where the proposed source/version contract is stricter or more expressive.
4. **Verification and constrained execution:** Cite formal stream languages, Clover, and generated-pipeline checking. State exactly which guarantee is new in this application and which machinery is inherited.
5. **Empirical gap:** Identify the common release-aware evaluation and the controlled test of verifier feedback that the paper will provide. Keep expected results separate from demonstrated results.

For a short related-work section centred on fusion, prioritize `kenda2022architectures`, `steiner2026integration`, `riehle2025grammarintegration`, and the most relevant temporal-contract and verification sources. The forecasting subsection should additionally consider `najafabadi2026temporalleakage` and `murray2025elate`. Include formal-language references if proof or bounded-state claims remain central. FASTENER becomes especially important when discussing feature selection or evolutionary search in the predecessor line.

## 12. Remaining verification before submission

- **Project evidence:** Inspect the actual DSL, verifier, batch engine, and original-system audit. This review cannot confirm that the proposed guarantees are implemented, nor whether the original audit's allegations are reproducible.
- **Closest new competitor:** Obtain an archived full text and implementation, if available, of the July 2026 temporal-leakage paper. Its indexed Sections 3.5–3.8 were inspected, including the leakage-control explanation, but the implementation was not audited.
- **Operational continuation:** Retrieve the final NAIADES prediction and fusion deliverables before claiming that the whole continuation lacks a particular mechanism. Mid-term plans do not establish final implementation status.
- **Comparator preprocessing:** Audit OCTree's Enefit joins and cutoff construction before alleging that availability information was discarded or that its features leaked.
- **Software versions:** Pin Featuretools, Temporian, Feast, and River versions and relevant backend settings in any empirical comparison. Current documentation is not a substitute for versioned experimental artifacts.
- **Publication status:** Recheck recent preprints immediately before submission. This report's coverage ends on 10 September 2026; abstract-level entries support scope comparisons only.

**Decision for the project:** Replace the current novelty memo's categorical absence claims with the fusion-centred statement in Section 8, expand the matrix with the priority sources, and assess both pipeline-construction capability and semantic enforcement. The contribution need not depend exclusively on improved forecasting or a novel verifier. It does require a clear account of what is automated, what is preserved, and how the resulting fusion improves on relevant alternatives.

## 13. Data fusion as a contribution in its own right

### 13.1 Why this changes the assessment

The earlier feature-generation emphasis was too narrow for the clarified system scope. A fusion pipeline may output a feature vector, a synchronized stream, or an integrated dataset. Outputting features does not make the preceding source-integration problem disappear. Conversely, renaming a transformation over an already fused table would not establish a broader contribution.

The useful distinction is **which decisions the system makes before the output exists**. For example, combining electricity measurements, weather forecasts, prices, and asset metadata may require choosing compatible temporal and entity relationships, resampling conventions, unit conversions, eligible forecast versions, and behavior when a source is missing. Synthesizing or validating those compositions is a broader problem than proposing additional arithmetic columns. This is an illustrative scope analysis, not a claim that all these capabilities have been inspected in the project.

Kenda's fusion methodology is therefore a closer conceptual foundation than an AutoFE-only comparison suggests. The candidate advance is automating and checking supported fusion decisions that otherwise require configuration. The cited 2019–2022 work still needs full credit; the new contribution would concern how a valid, useful pipeline is obtained and what guarantees its execution provides.

### 13.2 Contribution levels and their evidence

| Possible contribution | Evidence needed | Suitable outcome measures |
| --- | --- | --- |
| Automatic configuration of an existing fusion framework | Clear task-to-configuration procedure and comparison against competent manual configuration and simpler automation. | Engineer time, corrections required, successful tasks, fused-output quality. |
| A fusion language or planner with additional expressive capability | Concrete cases and operator compositions that the comparison systems cannot represent directly, or require substantial extra machinery to represent. | Coverage of supported tasks and semantic fidelity. |
| Enforcement of cross-source constraints | Explicit rules covering interactions between joins, alignment, units, versions, and provenance, with proof or appropriately scoped tests. | Violations prevented, valid cases accepted, preservation of required semantics. |
| Reusable deterministic stream execution | Defined runtime behavior across supported source rates, delays, failures, and changes. | Latency, memory, throughput, recovery behavior, reproducibility. |

The first can be a useful systems or empirical research contribution even when the underlying fusion operations are established. Stronger novelty comes from a substantive new method, demonstrated generality, or a meaningful reliability/effort improvement. A novel theorem is not the only route; mere assembly without a demonstrated advance is insufficient.

### 13.3 Additional direct comparisons

**`steiner2026integration` — Aaron Steiner and Christian Bizer. “Automatic End-to-End Data Integration using Large Language Models.” arXiv:2603.10547, 2026. Evidence: Text, v1, particularly Sections I and III–VII.**

The method uses an LLM to configure schema matching, normalization, entity matching, and conflict-resolution-based data fusion. It compares generated and human-configured pipelines on three multi-source integration cases. The fusion evaluation identifies temporal mismatches when an LLM supplies current values for historical source records. [Paper](https://arxiv.org/html/2603.10547v1).

**Relevance:** This prevents claiming the first LLM-configured fusion pipeline. Its inspected setting does not establish a general availability-aware streaming execution contract. It is a direct comparison for automation scope and configuration effort, with a useful warning about preserving the temporal meaning of fused values. Here “data fusion” specifically includes resolving conflicting entity attributes; define the proposed system's usage explicitly.

**`riehle2025grammarintegration` — Dennis M. Riehle, Arnold F. Arz von Straussenburg, Timon T. Aldenhoff. “Designing Grammar-Guided LLM Outputs for Open Data Integration – A DSR Approach to IoT Data Platforms.” DESRIST 2025, pp. 178–195. Evidence: Publisher abstract and introductory text.**

The system uses formal grammars to convert heterogeneous open data into SensorThings-API-compliant JSON. Its reported focus is structural output validity; domain-level validation remains future work. [Publisher chapter](https://link.springer.com/chapter/10.1007/978-3-031-93976-1_12).

**Relevance:** Constrained LLM output in IoT ingestion is established. Distinguish validity of the exchanged representation from correctness of a composed fusion pipeline. This source supports an ingestion/conformance comparison, not a negative implementation claim about every possible temporal capability.

**`ovcharenko2026sempipes` — Olga Ovcharenko, Matthias Boehm, Sebastian Schelter. “SemPipes -- Optimizable Semantic Data Operators for Tabular Machine Learning Pipelines.” arXiv:2602.05134, 2026. Evidence: Abstract.**

SemPipes introduces declarative semantic operators whose implementations are synthesized using LLMs and evolutionary optimization within data-preparation pipelines. [Primary record](https://arxiv.org/abs/2602.05134).

**Relevance:** This broadens the comparison from isolated feature expressions to pipeline operators. Inspect its full implementation before making claims about differences in supported fusion or streaming semantics.

### 13.4 How to distinguish the contribution experimentally

Use source-level fusion tasks with different combinations of temporal frequency, delay, entity relationships, units, and forecast updates. Do not make the test set consist solely of new columns on a shared prejoined table. Compare a competent expert configuration, simpler automatic configuration or search, and the proposed LLM-assisted method using the same raw sources and requirements.

Then hold the fused representation fixed to evaluate optional feature generation separately. This separates improvements caused by better source combination from improvements caused by downstream feature search. Measure predictive performance where useful, but also test the fused output against independent expected records, lineage, and temporal eligibility. A reliable fusion system can be valuable even if a strong downstream predictor achieves similar accuracy from several competing pipelines.

For uses without a prediction target, replace the prediction-specific cutoff with the application's declared output or query semantics. A retrospective analysis may legitimately use later revisions, while a reconstruction of what was known at an earlier time may not. A general fusion system should express that policy rather than universally banning later information.

**Recommended framing:** LLM-guided construction and validation of heterogeneous streaming data-fusion pipelines, with feature generation and forecasting as applications. This is a plausible broader contribution whose strength depends on the supported fusion decisions and the evidence above.

## 14. Publication strategy: intermediate papers and the final fusion system

**Added at the researcher's request. Venue information checked on 10 September 2026.** This is a prospective publication plan, not an assessment that the current implementation is ready for any submission. Effort estimates below are planning judgements; acceptance probabilities, institutional publication credit, and actual development progress are unknown.

### 14.1 Overall recommendation

**The conservative plan is three independently useful papers, with additional papers possible if the planned components support separate contributions.** A substantial dataset or deployment study is one expansion route, but it is not the only one: the fusion engine, verification method, and synthesis method may themselves justify separate papers. Section 14.10 develops this more granular strategy. Publication counts remain conditional on the evidence, rather than a forecast of acceptances.

The most efficient sequence is:

1. **A focused empirical or protocol paper** about constructing and evaluating temporally correct fused streams. This can precede the LLM component.
2. **A research-software paper** about a reusable fusion/replay engine, once it is sufficiently complete and useful.
3. **The main method/system paper** on LLM-guided fusion construction, including the strongest verification and search results.
4. **An optional resource or application paper**, justified by evidence beyond the first three.

This sequence turns necessary project work into publications: establishing trustworthy evaluation, building the engine, and developing the automated method. It also reduces dependence on the hypothesis that an LLM will improve prediction accuracy.

For a less demanding first publication, reduce the breadth of the claim and choose an appropriate article type. A careful measurement study, documented method adaptation, software contribution, or domain-specific validation may require less algorithmic novelty than the eventual main paper. Each should still answer a complete question. Elsevier explicitly provides distinct outlets for methods, software, and data, while Informatica's author guidance recognizes technical papers and rigorous empirical contributions. [Research Elements overview](https://www.elsevier.com/researcher/author/tools-and-resources/research-elements-journals); [Informatica submission guidance](https://www.informatica.si/index.php/informatica/about/submissions).

### 14.2 Candidate papers, ranked by practical value

The titles are provisional descriptions, not claims of completed results. The approximate effort bands refer to **additional focused researcher-weeks after the stated prerequisites exist**, excluding editorial waiting time and major unexpected implementation work.

| Candidate | Independent question and contribution | Minimum evidence I would recommend | Effort and priority |
| --- | --- | --- | --- |
| **P1. Temporal Alignment and Availability Policies in Heterogeneous Stream Fusion: A Reproducible Evaluation** | How do alignment, availability, and version-selection choices affect the correctness and usefulness of fused outputs? A controlled study can contribute without inventing a new fusion algorithm. | One thoroughly documented real multi-source task plus controlled cases; several reasonable fusion policies; independently checked expected outputs; analysis of coverage, errors, and downstream effects. Add a second real setting for a broader journal claim. | **First choice.** Roughly 4–6 weeks after access to suitable source data and a basic replay implementation. No LLM or general proof required. |
| **P2. A Reusable Engine for Availability-Aware Streaming Data Fusion and Replay** | Can researchers reproducibly configure, execute, and inspect fusion across heterogeneous sources? The contribution is the usable research software and its design. | Installable package, documented contracts and examples, appropriate tests, benchmark scripts, a versioned release, research use, and a comparison explaining why existing tools do not already meet the same need. | **High priority.** Roughly 3–6 weeks of packaging, documentation, and evaluation after a functional core exists; software maturity may require much longer elapsed time. |
| **P3. LLM-Guided Construction and Validation of Heterogeneous Streaming Fusion Pipelines** | Does the proposed construction method produce useful valid pipelines with less configuration effort or better search efficiency? This is the main scientific contribution. | Expert and non-LLM comparisons, direct temporal/integration comparators, held-out fusion tasks, feedback ablations, execution evidence, and clearly scoped guarantees. Predictive evaluation is one application. | **Reserve as the main paper.** Usually the largest remaining research block; plan in months, not as a quick derivative submission. |
| **P4a. An Availability- and Revision-Aware Benchmark for Streaming Data Fusion** | Does the released resource enable reliable comparisons that existing datasets or benchmarks do not? | A substantial independently reusable corpus of source streams, tasks, availability/version annotations, reference outputs, validation, provenance, and access instructions. | **Conditional fourth paper.** Roughly 4–8 additional weeks if the resource is already being built and still needs curation and validation. |
| **P4b. Operational Evaluation of Streaming Fusion in an Energy, Water, or Industrial Deployment** | What changes when the system is used under real operating conditions? | A new deployment or independently meaningful operational dataset, domain-specific outcomes, comparisons, real failure/maintenance evidence, and analysis beyond the main paper's demonstration. | **Alternative or later fourth paper.** Duration depends on data collection and deployment; cannot be promised from existing Enefit experiments. |
| **P5. Formal Semantics or Verification of Versioned Stream Fusion** | Is there a substantial new semantic or verification result that stands independently of the LLM study? | Precisely stated properties, proofs, a meaningful comparison with formal stream languages, and demonstrated relevance to the implementation. | **Optional later branch.** This is not a lower-novelty shortcut; keep it within P3 unless it becomes a substantial research project. |

**Do not automatically add P4a and P4b to the expected count.** They are opportunities triggered by actual new work. Similarly, a short preliminary paper and an extended journal version are a publication route with venue-specific requirements, not automatically two independent contributions.

An alternative early paper is a narrowly scoped comparison of manual, template-based, and LLM-assisted fusion configuration. Choose it only if that experiment is already more mature than P1. It overlaps directly with P3's construction claim, so it creates more pressure to deliver substantial new results in the final paper. P1 generally preserves more room for the main contribution.

### 14.3 The best first paper: a concrete small study

**Recommended first target: P1, framed as empirical knowledge about fusion policies rather than a claim that existing systems are universally unsafe.** It can be a complete intermediate result while the ultimate system remains unfinished.

Use a single main research question: *Under documented source-release constraints, which fusion-policy choices change output correctness, coverage, and downstream evaluation, and by how much?*

A manageable study would contain:

1. **A precise task and source inventory.** Start from the separate measurement, forecast, price, and contextual streams. Document the target/output times, entity relationships, units, and available release metadata.
2. **A small, controlled set of policies.** For example: event-time alignment alone; alignment plus an availability cutoff; availability plus eligible revision/forecast selection; and a competent expert configuration. Make the intentionally simplified policies explicit experimental conditions.
3. **Independent reference cases.** Hand-check a compact set of representative examples and add controlled late-arrival, update, duplicate, and missing-source cases. Distinguish genuine recorded delays from synthetically injected perturbations.
4. **Direct fusion measures.** Count wrong source/version selections, missing or extra outputs, entity/time misalignment, and discrepancies from reference values. Measure coverage alongside correctness so a policy cannot appear successful by rejecting everything.
5. **A secondary downstream experiment.** Keep the learner, tuning, and split fixed while changing only the fusion policy. Report uncertainty and the information available to each condition.
6. **A reproducible artifact.** Release reconstruction scripts, permitted metadata, configurations, expected outputs, and an exact version of the execution environment.

**Useful results need not show a large performance gain.** The paper might identify when a simple policy is sufficient, when more careful selection materially changes outcomes, or the cost of ensuring correct reconstruction. If all policies are equivalent on the available real data, report that boundary honestly and evaluate whether the controlled cases and protocol constitute enough new evidence for the selected venue. Do not manufacture significance by presenting deliberately invalid baselines as representative deployed practice.

For a short conference paper, keep one real case and a narrow conclusion. For a methods article, emphasize the executable reconstruction procedure and its validation. For a regular journal article, broaden the empirical coverage and analysis. These are alternative packages for the same initial work; select one primary submission route.

**Suggested figures/tables:** source and release timeline; fusion-policy comparison; representative failure cases; correctness/coverage results; runtime and downstream sensitivity. The expensive LLM search loop can remain future work.

### 14.4 Venue shortlist and realistic positioning

“More accessible” below means a potentially better fit for a bounded empirical, technical, or artifact contribution. It is **not** a verified ranking, acceptance prediction, or claim that the venue relaxes scientific standards. Current quartiles and institutional credit depend on the database, category, year, and local rules; those were not assessed here.

| Venue / article type | Best fit in this project | Practical assessment and verified constraints |
| --- | --- | --- |
| **MIPRO 2027 — BIS-BDP, DC-CPS, or AIS** | P1; a bounded fusion implementation/evaluation; possibly a later construction pilot. | A concrete regional/international conference option. The official call lists these data-processing, distributed-systems, and AI tracks. It currently gives **19 October 2026** for abstracts and **30 November 2026** for full papers. Acceptance notification is listed as **1 February 2027**. [Official call](https://www.mipro.hr/CallForPapers/tabid/176/language/en-US/Default.aspx). |
| **SiKDD / Information Society** | A compact P1 or focused preliminary study, with an audience connected to the predecessor literature. | Worth considering for feedback and a modestly scoped contribution. The IS2026 site lists SiKDD, but its linked call retrieved in this review leads to **SiKDD2025**. A usable 2026 submission deadline was therefore **not verified**. Do not plan a current submission from the year in the page heading alone. [Conference listing](https://is.ijs.si/?page_id=34); [linked call](https://ailab.ijs.si/dunja/SiKDD2025/). |
| **MethodsX** | P1 packaged as a validated reconstruction/fusion protocol or useful adaptation of existing methods. | Particularly relevant to the request for a less algorithmically novel intermediate paper. Publisher guidance explicitly includes methodological advances and protocols. A clear operational procedure and validation are essential to the proposed fit. Current journal-specific fees were not verified. [Publisher overview](https://www.elsevier.com/researcher/author/tools-and-resources/research-elements-journals). |
| **SoftwareX or Software Impacts** | P2, once the software is reusable and its research value is demonstrated. | The publisher distinguishes detailed software/application articles in SoftwareX from short reusable-software contributions in Software Impacts. Choose one outlet for the same software contribution. Direct current author-guide retrieval was blocked; confirm detailed format and APC before committing. [Publisher overview](https://www.elsevier.com/researcher/author/tools-and-resources/research-elements-journals). |
| **Journal of Open Source Software — JOSS** | P2 after sustained public development and demonstrated research use. | No submission/publication fees. Current screening requires **more than six months of active public development**, substantial research software, documentation/tests, and evidence of research use. It is not an immediate outlet for a newly released prototype. Related method/software publications must be disclosed. [Submission and screening rules](https://joss.readthedocs.io/en/latest/submitting.html). |
| **Informatica — the journal at informatica.si** | P1 as a substantial empirical/technical article, or P3 with a defensible computing contribution. | Technical articles and empirical advances are within the stated guidance; regular articles still require a clear contribution. Standard publication has no mandatory APC. Its current fee page lists a normal first-decision target of **6–12 months**, with other processing tiers available. A free route therefore should not be assumed fast. [Article guidance](https://www.informatica.si/index.php/informatica/about/submissions); [fees and timing](https://www.informatica.si/index.php/informatica/fees). |
| **Data — Data Descriptor; alternatively Data in Brief** | P4a when the benchmark resource itself is substantial. | Data Descriptors require a documented dataset, methods, access information, and licensing information. Data in Brief offers a data-article route. Reformatting a pre-existing public dataset is not a strong proposal without significant new curation, annotations, or reusable evidence. [Data instructions](https://www.mdpi.com/journal/data/instructions); [Data scope](https://www.mdpi.com/journal/data/about); [Elsevier data-article overview](https://www.elsevier.com/researcher/author/tools-and-resources/research-elements-journals). |
| **IoT — research article or short communication** | A fusion architecture or a convincing domain application, especially P4b; possibly a bounded P1. | Its scope includes IoT architectures, platforms, applications, and practical issues, with short communications among its article types. This is a subject-fit option, not an acceptance forecast. [Journal scope](https://www.mdpi.com/journal/IoT/about). |
| **Sensors — research article** | A sensor-centred P3 or substantial P4b. | Sensor-system data fusion is explicitly in scope. It is a natural continuation venue for the Kenda foundation, but that alone does not establish publishability or make it the easiest early outlet. [Journal scope](https://www.mdpi.com/journal/sensors/about). |
| **IEEE Access — research article** | A mature, broad P3 or substantial systems/application study. | Treat as an option for the completed contribution, not a low-bar fallback. Its published review criteria require a clear advance and high technical standards. [Acceptance requirements](https://ieeeaccess.ieee.org/authors/preparing-your-article/); [review process](https://ieeeaccess.ieee.org/authors/stages-of-peer-review/). |

**Conference publication status matters:** MIPRO's announcement gives the event dates as **31 May–4 June 2027** and says IEEE technical co-sponsorship is still being arranged. Prior editions' IEEE Xplore publication should not be treated as a guarantee for the 2027 paper. [Organizer announcement](https://mipro.hr/Default.aspx?TabId=200&language=en-US&newspage=1).

**Indicative fees:** The publisher's current basic list gives **Data CHF 1,600; IoT CHF 1,400; Sensors CHF 2,600**, before applicable discounts and other adjustments. Check the applicable amount before choosing a paid route. [MDPI APC list](https://www.mdpi.com/apc). The fee is separate from fit, acceptance, and the value assigned by the institution. Conference registration/travel and unverified Elsevier/IEEE charges are not included in these figures.

**My immediate shortlist:** MIPRO for a focused P1; MethodsX if the result is primarily a reusable protocol; SoftwareX/Software Impacts or later JOSS for P2; Informatica, IoT, or Sensors according to the scope and maturity of the research article. Select one primary venue and one fallback per manuscript, rather than repeatedly rewriting for a long succession of unrelated outlets.

### 14.5 A staged schedule that supports the end goal

These milestones assume at least a working prototype or the ability to build a small replay study soon. If data access or the engine does not yet exist, move the dates; this review has not inspected those prerequisites.

| Stage | Work to complete | Publication decision | Reusable value for the final system |
| --- | --- | --- | --- |
| **Next 1–2 weeks** | Inventory actual implemented fusion operations; freeze P1's question; confirm data access; define reference cases and the baseline configurations. Establish a public development history if an open-source release is intended. | Choose P1's primary venue and identify its exact article requirements. | Prevents building a benchmark around a moving target; starts software maturity. |
| **Following 4–8 weeks** | Complete the controlled study, inspect outputs, write the paper, and package replication materials. | Submit P1 only if it has a complete result. MIPRO's currently listed dates provide a concrete target; a journal route avoids an event deadline. | Trustworthy fusion evaluation and baseline artifacts. |
| **Months 2–4** | Stabilize the core library, improve documentation and examples, obtain use by a colleague or another project, and record engineering decisions. Continue P3 development. | Assess P2 for a software outlet. A package can be complete for its declared core scope even while the LLM layer is still being developed. | Maintainable engine, clearer interfaces, stronger execution evidence. |
| **Months 4–8** | Complete synthesis, verifier-feedback experiments, broader held-out fusion tasks, and the principal comparisons. | Draft and submit P3 once its independent advance is demonstrated. | The main end-to-end result. |
| **Months 6–12** | Review actual software uptake and whether the data/resource or deployment work has become independently substantial. | JOSS may become eligible after the required public history; assess one optional P4. | Community reuse or external validity. |

**These are submission-readiness estimates, not acceptance dates.** Reviews and revisions can overlap with work on a different paper. Do not wait for P1's acceptance before developing P3; cite the earlier work in the form allowed by the later venue and preserve any anonymization requirements.

If the repository first becomes public in September 2026, a JOSS submission should be planned for after the six-month-history threshold in 2027, subject to the other criteria. The active development and research-use requirements cannot be satisfied just by leaving a repository online.

### 14.6 Preserve independent contributions and room for the final paper

Maintain a short claim-and-evidence ledger before drafting. For each manuscript, record its research question, principal claim, unique experiments or artifact, and the earlier work it builds on.

| Material | P1: empirical/protocol | P2: software | P3: main method | Optional P4 |
| --- | --- | --- | --- | --- |
| Core ownership of the contribution | Knowledge about fusion-policy behavior or a validated reconstruction procedure. | Reusable implementation, engineering choices, interfaces, and research utility. | New construction/verification method and evidence of its benefit. | New benchmark resource or operational finding. |
| Appropriate reuse | Common source data and configurations, with versions recorded. | Implements and cites P1's protocol. | Uses earlier infrastructure and cites it. | Uses the common platform and cites relevant earlier papers. |
| Evidence that must add something | Controlled policy results and independently checked cases. | Installation/reuse evidence, software design, maintenance and execution assessment. | New method comparisons, ablations, held-out tasks, and any new guarantees. | Additional curation/annotations or actual deployment measurements. |
| Insufficient separation | Splitting each failure mode into a different paper. | Publishing the same library description at several software journals. | Republishing P1's results with an LLM paragraph and a new title. | Reusing the main paper's application section with minor expansion. |

Sharing code and data is efficient; repeatedly presenting the same finding as new is not. Cite prior papers, identify reused evidence, and disclose related manuscripts where requested. JOSS explicitly allows complementary science/method/software publication under its conditions. IEEE Access permits eligible expanded conference versions, but an expansion must meet its publication rules. There is no universal percentage of new text or experiments that makes every extension acceptable. [JOSS co-publication policy](https://joss.readthedocs.io/en/latest/submitting.html); [IEEE Access requirements](https://ieeeaccess.ieee.org/authors/preparing-your-article/).

**Protect P3's future contribution through scope, not by making P1 incomplete.** Fully explain P1's method and results, but give it a question that can be answered without the eventual synthesis method. A later paper can then cite a complete foundation and contribute genuinely new construction and verification results.

If P2 already establishes the full semantic and execution guarantee, P3 should cite that result and claim the synthesis/feedback contribution. Conversely, if the language and verifier are the main new method in P3, the software paper must not present that same scientific claim as a second independent discovery.

### 14.7 How to maximize useful publications per unit of effort

**First, build one research platform.** Use shared loaders, source contracts, replay, reference cases, evaluation outputs, and versioned configurations. Keep separate experiment manifests for each paper. This avoids maintaining several almost-identical systems and makes reviewer-requested checks cheaper.

**Second, design measurements for several legitimate questions at once.** A fusion run can record correctness, coverage, latency, memory, provenance, and downstream effects. Record construction effort separately: prompts, revisions, rejected configurations, elapsed author time, and human corrections. Those measurements support different claims without rerunning everything. Each paper should report the evidence relevant to its own question and acknowledge any prior use.

**Third, prioritize work that survives an uncertain headline result.** P1 and P2 can remain valuable if LLM-generated pipelines match rather than beat expert pipelines. An honest study of reduced configuration effort, stronger correctness, or the limits of automation may still support P3. Small score changes alone are a weak foundation for several papers.

**Fourth, use development milestones as publication opportunities.** A stable deterministic core, a validated source-release reconstruction, and a completed synthesis experiment are meaningful milestones. A new prompt, another aggregation operator, or a different model version usually belongs in an existing paper's evaluation.

**Fifth, include publication overhead in the plan.** A short paper still needs positioning, experiments, references, revisions, and sometimes travel or a fee. Keep one principal manuscript in preparation and at most one substantially different manuscript in review while progressing the core research. More simultaneous drafts can reduce total completion.

**Sixth, choose the count that matters.** If the objective is journal articles recognized by an institution, a local proceedings paper, poster, software DOI, preprint, and indexed journal article may not be equivalent. Record the required publication category before paying fees or optimizing for a nominal paper count. This analysis does not assume the researcher's promotion, PhD, or funding rules.

A practical decision rule is: **prefer a manuscript that answers a distinct question, reuses necessary project work, fits a clear article type, and leaves the end goal stronger after publication.** Avoid numerical acceptance forecasts without evidence.

### 14.8 Lower-priority ideas and what to do if results disappoint

| Situation or proposed extra paper | Better publication decision |
| --- | --- |
| “Publish the literature report as a survey.” | Do not treat this targeted report as survey-ready. A publishable survey needs a defensible search/screening method, sufficiently complete coverage, and a synthesis that adds knowledge. This is a separate substantial effort; lower priority unless a clear survey gap is confirmed. |
| “Publish a Python port of Kenda's implementation.” | A port alone is weak. It could support P2 if it delivers demonstrable reuse, reproducibility, portability, or a meaningful capability improvement and clearly credits the predecessor. |
| “Make one paper for each dataset or prompt variant.” | Keep these in the same evaluation unless they answer genuinely different scientific or operational questions. |
| LLM proposals fail to improve forecast accuracy. | Evaluate valid-pipeline yield, configuration effort, cost, and robustness. If there is no material benefit on any relevant measure, publish a well-supported limitation study where appropriate and keep the infrastructure result separate. |
| Availability rules have little effect on the chosen dataset. | Establish the conditions under which simple fusion is adequate, distinguish those from controlled stress cases, and consider another real source setting. Do not generalize beyond the tested availability structure. |
| A benchmark contains mostly synthetic cases. | Present it as a controlled conformance/stress benchmark, validate its generator and expected outputs, and explain its limits. It does not measure the prevalence of failures in real deployments. |
| The public data cannot be redistributed. | Package original annotations, permitted metadata, acquisition/reconstruction instructions, and a synthetic suite as appropriate. A data-paper route depends on whether the actual reusable resource is substantial and accessible under the applicable terms. |
| Formal proofs take much longer than expected. | P1 and a scoped software contribution can proceed without claiming unproved guarantees. Decide whether P3 can make an empirical systems contribution or should await the formal result. |

### 14.9 Recommended plan for this project

**Base plan: three papers.** Start with the source-level fusion-policy study; produce one software publication when the reusable core is ready; reserve the full LLM-guided fusion construction and validation contribution for the main research paper.

**Expansion plan: four papers.** Add a benchmark/data descriptor if the project produces a substantial validated resource beyond P1's experiment bundle, or add a deployment paper if a separate domain study produces new operational evidence. Choose the branch with the strongest natural evidence and lowest extra burden.

**Higher-output plan: separate substantial planned contributions before expanding the project.** Four or more focused papers may be possible if the engine, verification, evaluation protocol, and LLM construction each support their own result. Additional resource or deployment contributions can expand that portfolio. The number should follow the evidence for these contributions, not a requirement to add domains or a fixed ceiling of three papers. See Section 14.10.

The first concrete action is to specify P1's question, reference outputs, and baseline policies, then assess whether a complete study can be ready for the currently listed MIPRO 2027 deadlines. If its strongest output is instead a validated reusable procedure, MethodsX is a more direct article-type match. A publication strategy built around these complete intermediate contributions can increase output while making the final fusion paper easier to execute and defend.

### 14.10 Alternative: publish separate, smaller contributions

**Yes: different contributions can be published in different papers, including narrower technical or specialist articles.** The three-paper plan above bundles several components for efficiency; it is not a limit on what the work can support. In particular, a verification contribution need not be held back until the LLM method is complete, and a useful fusion engine need not wait for either.

The appropriate unit is **one independently useful and validated contribution**. That contribution can be modest: a useful extension of a known method, a reproducible comparison that resolves a practical uncertainty, or a reusable implementation with demonstrated advantages. It need not introduce a whole platform or outperform every existing method. Article-type fit matters: MethodsX explicitly accommodates methodological advances and protocols, while technical and empirical computing papers are among Informatica's stated options. [Methods publication options](https://www.elsevier.com/researcher/author/tools-and-resources/research-elements-journals); [Informatica article guidance](https://www.informatica.si/index.php/informatica/about/submissions).

#### A more granular four-paper core

These are alternative boundaries to P1–P3, not four additional papers to count on top of them.

| Focused paper | Its principal contribution | Evidence specific to this paper | Plausible route |
| --- | --- | --- | --- |
| **F1. A reusable heterogeneous stream-fusion engine** | A scoped implementation or execution improvement that makes fusion easier to reproduce, configure, or run. | Supported source combinations; comparisons with existing implementations; latency, memory, and throughput; examples of research use. It can use manual configurations throughout. | SoftwareX / Software Impacts for the software contribution; IoT or a systems conference for a substantive execution study. Choose the format that matches the actual advance. |
| **F2. Checking temporal and semantic validity in fusion pipelines** | A concrete checker, rule system, or verification method for a clearly defined class of cross-source errors. | Its contract and limits; comparison with simpler validation; independently specified valid/invalid cases; detection and false-rejection results; proofs only where actually established. It can evaluate human-written or systematically generated pipelines without an LLM. | A technical computing paper, an appropriate methods article, or a focused conference paper. Informatica and MethodsX are candidates to assess against the completed contribution. |
| **F3. A reproducible protocol or benchmark for evaluating streaming fusion** | A method or resource that allows other researchers to evaluate alignment, availability, and revision behavior consistently. | Reconstruction and annotation procedures; independent validation of reference outputs; an empirical comparison or sufficiently substantial reusable corpus. Its value must extend beyond supplying tests for F2. | MethodsX for a protocol; Data / Data in Brief for a substantial resource; MIPRO for a bounded empirical study. These are alternative routes. |
| **F4. LLM-assisted construction of valid fusion pipelines** | A method and study of automatic configuration or synthesis using the previously published engine/checker. | Construction success on held-out tasks; comparison with experts, templates, or non-LLM search; effort and cost; structured-feedback ablations; direct fusion quality and selected downstream outcomes. | MIPRO AIS/BIS-BDP for a bounded result; an appropriate computing or IoT journal for a broader study. |

**A fifth paper** could address a genuine domain-specific deployment, substantial new benchmark release, or another independent method. It is not necessary to make every paper large, but the fifth still needs its own result. Do not automatically separate a unit checker, a lineage checker, and a state-bound checker into three papers: if they are routine parts of one validation method, F2 is their natural home.

#### The key test for each proposed split

Write three sentences before committing to a manuscript:

1. **Question:** What uncertainty does this paper resolve?
2. **Contribution:** What method, evidence, or reusable artifact will a reader gain?
3. **Separation:** What does this paper establish that the other planned papers do not?

Then identify the main table, experiment, theorem, or artifact supporting those sentences. If two manuscripts depend on the same central result and differ mainly in emphasis, combine them. If the engine study establishes execution behavior, the verifier study establishes error-control behavior, and the synthesis study establishes configuration effectiveness, their shared software does not prevent them from being distinct contributions.

F2 and F3 deserve particular scrutiny. If the benchmark is merely a small test suite for the checker, keep them together. If it provides an independently validated evaluation protocol used to compare several systems and answer a separate empirical question, a separate paper becomes more credible. The same reasoning applies to a software article and a systems-performance article about that software.

#### Effect on the eventual main paper

Publishing F1 and F2 first changes the later novelty claim: F4 contributes the synthesis method and its evaluation, while citing the engine and checker as established foundations. It should not claim those components again as new. This is a normal way for a research programme to develop.

There is also **no requirement to publish an additional omnibus paper** after F1–F4. The last contribution paper may complete the programme. A further integration paper would need new evidence about end-to-end behavior, cross-component interactions, scale, or real-world use; simply assembling the earlier descriptions would not supply that advance. A thesis or project report can provide the comprehensive synthesis without needing to be counted as another journal contribution.

#### Revised practical recommendation

For a researcher prioritizing several smaller publications, **plan four candidate contribution papers using F1–F4**, with a fifth as an evidence-driven opportunity. At each milestone, decide whether a candidate is independently ready, belongs in a narrower article type, or should merge with another. This is a more responsive plan than reserving nearly all scientific content for one large final paper, while keeping the total effort connected to the same fusion-system goal.

Start with whichever of F1 or F3 is closest to completion, develop F2 as a separate candidate if its method and evaluation are substantial, and let F4 build explicitly on the published foundations. The venue shortlist in Section 14.4 provides initial options; choosing a smaller venue should change the breadth and presentation of the claim, not substitute for demonstrating it.

### 14.11 Regional conferences: Ljubljana, neighbouring countries, and northern Italy

**Research checked on 10 September 2026.** This shortlist prioritizes research-paper opportunities relevant to data fusion, data mining, and ML, with late-2026 and 2027 planning in mind. It distinguishes an announced upcoming edition from a relevant series whose nearby edition has already closed. Locations rotate: a Budapest organizer or a past Milan conference does not establish the next meeting's location. Recommendations below are assessments of fit, not acceptance-rate estimates or formal conference rankings.

#### Conferences worth examining first

| Conference | Verified location and timing | Submission status | Fit for this project and smaller contributions |
| --- | --- | --- | --- |
| **TELFOR — Telecommunications Forum** | **Belgrade, 24–26 November 2026**. | **Full-paper deadline: 4 October 2026**, extended from 4 September; regular papers have a **four-page maximum**. Separate AI and Data Science sections. [Current author instructions](https://www.telfor.rs/en/authors/). | The most actionable newly identified option for a compact empirical contribution: availability-aware fusion, a scoped validation experiment, or a streaming implementation comparison. Its broader engineering audience makes an applied framing useful. |
| **CINTI — Computational Intelligence and Informatics** | **Budapest, 2027**, listed in the organizers' upcoming events. Exact dates and the new call were not verified. [Organizer's Budapest listing](https://conf.uni-obuda.hu/sisy2026/); [2027 conference calendar](https://conf.uni-obuda.hu/2027.html). | Watch for the 2027 call. The **2025** edition used **4–6 pages** and included an LLM special session; these are precedents, not confirmed 2027 rules. [Previous scope](https://conf.uni-obuda.hu/cinti2025/); [previous format](https://conf.uni-obuda.hu/cinti2025/paper.html). | A plausible route for a focused applied ML or LLM-assisted configuration study. More directly concerned with computational intelligence than a general electronics conference. |
| **CECIIS — Central European Conference on Information and Intelligent Systems** | **Varaždin, 16–18 September 2026**, organized by the University of Zagreb's Faculty of Organization and Informatics and partners. | The published paper deadline was **15 May 2026**; this is a **future-edition watch**, not an open 2026 submission. A 2027 call/location was not verified. [University announcement](https://www.foi.unizg.hr/hr/novosti/ceciis-2026-u-varazdinu-uz-temu-next-wave-intelligent-systems-otvoren-poziv-za-prijavu). | A useful nearby alternative to Zagreb itself. Intelligent systems, databases/knowledge bases, and cyber-physical systems/intelligent energy are relevant areas. Consider an engine, validation, or bounded application paper. |
| **SISY — Intelligent Systems and Informatics** | **Pula, 23–25 September 2026**. | Submission closed **11 June 2026**. Watch subsequent editions; no nearby next edition was verified. [Official conference and topics](https://conf.uni-obuda.hu/sisy2026/). | Computational intelligence, ML, and sensor fusion are explicitly represented. A good series to examine for an engineering contribution with an intelligent-systems application. |
| **DaWaK — Big Data Analytics and Knowledge Discovery**, alongside DEXA | **Graz, 11–13 August 2026**, already held. | The 2026 call offered **short papers up to 6 pages** and full papers up to 15, with Springer LNCS proceedings. The next location and deadline were not verified. [DaWaK call](https://www.dexa.org/2026/dawak2026.html). | **One of the best topical matches** for the fusion engine or evaluation work: its scope explicitly includes preprocessing, metadata, data science workflows, and sensor/network streams. The short-paper category accommodated preliminary work and industrial applications. |
| **IDA — International Symposium on Intelligent Data Analysis** | **Pisa, April 2027**, announced by the IDA Society. | Exact dates, submission deadline, and 2027 format were not published on the society page inspected. [Official announcement and research philosophy](https://www.ida-society.org/). | A particularly good audience for a clear insight about valid fusion or evaluation. IDA explicitly values original ideas and insight and welcomes promising work before exhaustive validation. A small implementation improvement alone would be a weaker fit. |
| **LION — Learning and Intelligent Optimization** | **Milan, 15–19 June 2026**, already held. | The 2026 edition accepted **6–11-page short papers** and 12–15-page long papers, with LNCS proceedings. Do not plan on a Milan repeat: the University of Hamburg hosts a preliminary **LION 21 / 2027** site whose call page was still incomplete. [Milan edition](https://www.lion20.org/); [2027 site](https://www.lion2026.uni-hamburg.de/). | Especially relevant if F4 becomes a constrained search/optimization method. The Milan programme included LLM-assisted optimization. Less direct for a purely deterministic fusion engine. |
| **ICANN — International Conference on Artificial Neural Networks** | **Padua, 14–17 September 2026**. | The programme is already published; this is an attendance or future-series option, not a new 2026 paper opportunity. A 2027 nearby location was not verified. [ENNS conference site](https://e-nns.org/icann2026/). | Relevant if a paper makes a substantive neural-learning contribution. Lower priority for infrastructure or pipeline checking alone. Padua is a useful addition to the northern-Italy search area. |

**TELFOR practical details.** The current page lists advance net registration fees of **€310 regular, €240 IEEE member, and €180 PhD student**, with one fee required per accepted regular paper. Remote presentation carries a listed €100 supplement. Accepted and presented papers are submitted for possible IEEE Xplore publication; the organizer's wording is conditional. [Fees and format](https://www.telfor.rs/en/authors/); [publication policy](https://www.telfor.rs/en/about-telfor/). A four-page submission should establish one result clearly; a complete controlled comparison is more suitable than compressing the entire planned platform into that space.

**DaWaK merits a higher place in the publication plan.** The fusion project sits between data engineering and ML. Its source contracts, alignment decisions, metadata, and streaming execution are central research objects for a data-management audience, even before LLM synthesis is ready. A potential short paper could isolate how source revisions change the correctness and usefulness of fused outputs, while a broader later paper could examine automated construction. DEXA itself is also worth examining when the main result concerns data-system architecture or semantics. This is a recommendation based on scope; it does not imply that future calls will retain the 2026 formats. [DEXA conference family](https://www.dexa.org/).

#### What the requested cities offer

| City or area | Recommendation |
| --- | --- |
| **Budapest** | Prioritize **CINTI 2027** as a research-paper watch. The **Budapest Data+AI Forum**, announced for **10–12 May 2027**, is also highly relevant to practitioners, with a speaker call forthcoming. No archival research-paper track was established from its current page, so budget it for dissemination or finding users and collaborators. [Forum programme overview](https://budapestdata.hu/en/). |
| **Vienna** | The verified upcoming **Applied Artificial Intelligence Conference, 24 September 2026**, describes itself as an AI business symposium with workshops, exhibitions, and matchmaking. It may help find deployment partners, but I did not establish an archival paper route. For the paper goal, the stronger Austrian lead from this search is the **DaWaK/DEXA series**, most recently in Graz. I did not verify a comparably strong upcoming Vienna-specific call for this topic; that is a search limitation, not a claim that none exists. [AAIC organizer page](https://aaic.forum/). |
| **Milan** | **LION 2026** was a relevant research venue, especially for the synthesis/search contribution, but is over. Do not select a generic Milan ML event solely from its title. Expand the Italian search to **IDA 2027 in Pisa**, and follow future LION, AIxIA, and ITADATA calls once locations are known. |
| **Zagreb** | **IWDS — International Workshop on Data Science** at FER is a useful research community to examine. The verified 2025 event published an abstract book and featured talks/posters; a 2026 edition appears in the Croatian Academy of Engineering's activity plan, but a current submission call and archival full-paper route were not verified. For a conventional regional paper, **CECIIS in nearby Varaždin** is the clearer series to examine. [IWDS organizer page](https://sites.google.com/view/iwdatascience2025); [2026 activity plan](https://hatz.hr/wp-content/uploads/2025/12/Odjel-informacijskih-sustava-Izvjestaj-o-radu-u-2025.-i-plan-za-2026.pdf). |
| **Belgrade** | **TELFOR** is the clearest currently open research-paper option identified. **DSC Europe, 23–27 November 2026**, offers a strongly relevant data/AI practitioner audience, tutorials, and demonstrations, but its current page did not establish an archival research-paper submission route. Assess it separately for outreach. [DSC Europe organizer page](https://datasciconference.com/). |
| **Rijeka / Opatija** | **MIPRO AIS and BIS-BDP** remain the leading verified options in this area from the earlier search; Opatija is the conference location. See Section 14.4 for the 2027 call details. **SISY in Pula** is another nearby series to follow, with the 2026 submission already closed. |

The distinctions above matter for the publication plan: a selected talk, poster abstract, workshop proceedings paper, and full conference paper are different outputs. A networking event can still be valuable, particularly for securing the deployment evidence needed for a later application paper.

#### Other series to follow if location is flexible

- **AIxIA — the Italian Association for Artificial Intelligence's conference:** the verified 2026 edition is **Perugia, 5–9 October**, rather than Milan. Follow the association for future venues and suitable workshops; a nearby 2027 edition was not verified. [Association announcement](https://aixia.it/).
- **ITADATA — Italian Conference on Big Data and Data Science:** the verified 2026 edition is **Bari, 10–12 November**, with research, demo, and workshop activity. Its data-centric scope is relevant to F1/F3, but this search did not establish an open submission deadline or a northern-Italy 2027 edition. [Official conference](https://www.itadata.it/).
- **ADBIS:** a strong subject match for data integration and system semantics, with full and short research-paper routes described by the series. The current series page lists **France for 2026**, not a forthcoming Ljubljana/Budapest/Vienna event. Keep it on the thematic list without assuming regional proximity. [Series scope and publication routes](https://adbis.eu/).
- **ECML PKDD:** an excellent ML/data mining audience for a mature contribution or a suitable workshop. **The 2027 edition is announced for Eindhoven in September**, outside the requested region. Workshop calls and their publication status must be checked individually. [Official 2027 announcement](https://ecmlpkdd.org/2027/).

One useful location correction: **INES 2027 is in Corfu, 22–24 September**, despite the Budapest-based organizer and the Budapest 2026 edition. Its page lists **15 April 2027** for full papers. It may fit the research, but should not be counted as a Budapest travel option. [Official INES 2027 call](https://ines2027.conf.uni-obuda.hu/).

#### Suggested order for this research programme

1. **Assess one compact study against TELFOR's current deadline.** A candidate question is: “How do source availability and revision policies affect the validity and downstream utility of heterogeneous stream fusion?” This can stand independently of the LLM component. The deadline is useful only if the experiment and manuscript can actually be completed; implementation readiness has not been assessed here.
2. **Retain MIPRO 2027 as an alternative with more preparation time.** Choose the most suitable conference for a given manuscript; these are alternative submission routes for that result.
3. **Watch CINTI 2027 and the next CECIIS call for focused applied contributions.** They are sensible candidates for the smaller-paper strategy, subject to the new calls' scope and requirements.
4. **Prioritize the next DaWaK call for the fusion/data-engineering result.** The previous short-paper route is unusually relevant to a useful partial step, and the audience understands data preparation as a research subject.
5. **Develop an IDA 2027 candidate if the work produces a general methodological insight.** A precise account of when ordinary temporal alignment becomes invalid could be more compelling there than a small forecasting-score improvement. If the main advance is learning-guided search, consider LION instead when the next call is complete.

For the F1–F4 decomposition, my provisional mapping is **F1 engine → DaWaK/DEXA or CECIIS; F2 validation → a focused CINTI/MIPRO paper or IDA when the insight is sufficiently general; F3 protocol/empirical study → TELFOR, DaWaK, or CECIIS; F4 LLM construction → CINTI, IDA, or LION depending on whether the contribution is applied construction, a general analysis method, or optimization**. These are choices for each contribution, not a recommendation to publish the same result repeatedly.
