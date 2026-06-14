# Physics-Based Feature Formalization for Root Cause Classes C1–C8 in 5G RAN Optimization

---

## Abstract

This report presents a comprehensive physics-grounded feature formalization for eight root-cause classes (C1–C8) in 5G Radio Access Network (RAN) optimization. Leveraging expertise in radio propagation physics, LTE/NR air-interface behavior, interference, geometry, and mobility effects, we identify and validate interpretable features computable from drive test and engineering data. Each class is analyzed through its physical failure mechanism, observable RF signatures, candidate physics features with explicit formulas, cross-class disambiguation criteria, alignment with LightGBM feature-importance results, and failure/edge case considerations. The resulting feature set supports robust machine learning classification and large language model (LLM) reasoning, bridging RF theory and data-driven analytics. A summary table maps classes to mechanisms and top features, and recommendations highlight features best suited for tree models and LLM interpretability.

---

## Introduction

Accurate root-cause analysis (RCA) is critical for optimizing 5G Radio Access Networks (RANs), where performance degradations arise from diverse physical and operational factors. These include antenna geometry misconfigurations, interference patterns, mobility effects, and scheduling inefficiencies. While machine learning (ML) models can classify failure classes, their interpretability and robustness depend on physics-based features grounded in radio propagation and air-interface principles.

This report addresses the challenge of discovering, validating, and formalizing such features for eight defined root-cause classes (C1–C8), using user-plane drive test data, engineering parameters, and feature-importance insights from LightGBM models. The goal is to provide a rigorous, interpretable, and implementable feature set that:

- Reflects clear causal physical mechanisms

- Is computable from available data (RSRP, SINR, throughput, RB allocation, PCI, UE speed, antenna parameters)

- Is robust across environments and measurement noise

- Supports both ML model training and LLM reasoning chains

The report is structured to analyze each class in detail, followed by a synthesis of composite features and recommendations.

---

## Background and Literature Review

5G NR air interface behavior and radio propagation physics underpin network performance. Antenna downtilt and beamwidth shape coverage footprints, influencing signal strength and interference patterns [1]. Interference arises from frequency reuse and PCI collisions, degrading SINR and throughput [2]. Mobility effects, including UE speed and handover frequency, impact channel stability and scheduling [3]. Machine learning approaches to RCA leverage feature importance to identify key metrics but often lack explicit physics grounding [4]. This report integrates these domains, informed by recent RCA research using graph neural networks and transformer models [5], and standard 3GPP antenna and beamforming principles [6].

---

# Detailed Physics-Based Feature Formalization for Root Cause Classes C1–C8

---

## C1: Excessive Downtilt → Weak Far-Edge Coverage

### 1️⃣ Physical Failure Mechanism

Excessive electrical or mechanical downtilt directs the antenna main lobe too steeply downward, reducing vertical coverage footprint and weakening signal strength at the far cell edge. This geometric effect causes rapid signal decay with distance, leading to poor coverage and increased interference susceptibility at cell boundaries. The vertical beamwidth (6°, 12°, or 25° depending on beam scenario) modulates this effect, but excessive downtilt (>8° effective) consistently shrinks coverage range.

### 2️⃣ Observable RF Signatures

- Steep negative gradient of serving cell SS-RSRP versus horizontal distance.

- Strong positive correlation between SINR and RSRP, both declining sharply at cell edge.

- Throughput degradation despite sufficient scheduled RBs.

- Neighbor cell signals weaker at far edge, indicating lack of handover candidates.

### 3️⃣ Candidate Physics Features

| Feature Name               | Formula / Computation                                                                 | Units           | Causal Meaning                                  | Expected Direction / Threshold                  |
|----------------------------|--------------------------------------------------------------------------------------|-----------------|------------------------------------------------|-------------------------------------------------|
| **RSRP Gradient**           | Linear slope of serving cell SS-RSRP vs horizontal distance                          | dB / 100 meters | Rapid signal decay due to excessive downtilt   | Gradient < −10 dB/100m → coverage hole          |
| **Far-Edge Coverage Ratio** | % of measurement points beyond cell radius with SS-RSRP < −95 dBm                    | %               | Indicates weak far-edge coverage                | > 50% points below threshold → downtilt problem|
| **Effective Downtilt Angle**| Actual downtilt angle from digital downtilt parameter (6° if default 255)            | Degrees         | Larger downtilt reduces far-edge coverage      | > 8° considered excessive                         |
| **SINR-RSRP Correlation**   | Pearson correlation coefficient between serving cell SINR and RSRP                   | Dimensionless   | Strong correlation expected in downtilt cases | > 0.7 confirms downtilt-driven coverage loss    |

### 4️⃣ Cross-Class Disambiguation

- **Vs C3 (Neighbor better throughput):** C3 shows neighbor RSRP > serving cell; C1 shows serving cell dominant but weak at edge.

- **Vs C2 (Overshooting):** C2 exhibits coverage beyond 1 km; C1 shows coverage hole within cell radius.

- **Key Differentiators:** RSRP gradient magnitude, neighbor RSRP dominance.

### 5️⃣ Alignment With Feature-Importance Tables

LightGBM models emphasize RSRP and SINR metrics for C1. Downtilt angle is implicitly important but often abstracted; explicit inclusion enhances interpretability and causal clarity.

### 6️⃣ Failure & Edge Cases

- Terrain shadowing or obstructions may mimic downtilt effects; guard with neighbor strength and handover patterns.

- Urban macro cells with variable antenna heights may distort gradients.

---

## C2: Overshooting (Coverage > 1 km)

### 1️⃣ Physical Failure Mechanism

Insufficient downtilt causes the antenna main beam to extend beyond the intended coverage area (>1 km), elongating the coverage footprint and potentially causing interference and degraded near-site signal quality. The vertical beamwidth and mechanical azimuth influence the overshoot direction and extent.

### 2️⃣ Observable RF Signatures

- Serving cell SS-RSRP remains strong beyond 1 km.

- Neighbor cell signals weaker near site due to overshadowing.

- SINR decreases with distance, but RSRP remains relatively high.

- Increased handover failures or ping-pong handovers near cell edge.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **Coverage Radius at −100 dBm**| Maximum horizontal distance where serving cell SS-RSRP > −100 dBm          | Meters          | Extended coverage radius indicates overshoot| > 1000 m signals overshooting                  |
| **RSRP Slope**                 | Linear slope of serving cell SS-RSRP vs distance                          | dB / 100 meters | Shallower slope indicates extended coverage | > −5 dB/100m (less negative)                    |
| **Neighbor-to-Serving RSRP Ratio (near site)** | Ratio of top neighbor RSRP to serving cell RSRP within 500 m          | Dimensionless   | Low ratio indicates neighbor overshadowing  | < 0.5 indicates overshoot                       |
| **Effective Downtilt Angle**   | Actual downtilt angle from digital/mechanical tilt                        | Degrees         | Smaller angles cause overshoot               | < 6° or digital tilt < 4                        |

### 4️⃣ Cross-Class Disambiguation

- **Vs C1:** C2 shows extended coverage; C1 shows coverage holes.

- **Vs C4:** C4 involves co-frequency overlap; C2 is coverage shape related.

- **Key Differentiators:** Coverage radius, RSRP slope, neighbor RSRP ratio.

### 5️⃣ Alignment With Feature-Importance Tables

Distance-based RSRP and PCI features align with LightGBM importance, supporting radius and slope metrics.

### 6️⃣ Failure & Edge Cases

- Sparse macro cells or terrain may naturally have large coverage radius.

- Validate with PCI collision and interference metrics.

---

## C3: Neighbor Cell Provides Better Throughput

### 1️⃣ Physical Failure Mechanism

Load imbalance, interference, or geometry cause neighbor cell to provide better throughput than serving cell. UE may be better aligned with neighbor beam or experience less interference, and neighbor scheduler may allocate more resources.

### 2️⃣ Observable RF Signatures

- Neighbor cell SS-RSRP equal or stronger than serving cell.

- Neighbor throughput higher despite similar RSRP.

- Neighbor cell scheduled more RBs.

- Neighbor SINR higher or comparable.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **Neighbor-to-Serving Throughput Ratio** | Neighbor max throughput / serving cell throughput                      | Dimensionless   | Quantifies neighbor throughput advantage    | > 1.2 indicates neighbor dominance             |
| **RSRP Difference**            | Serving cell SS-RSRP − top neighbor SS-RSRP                              | dB              | Negative difference signals neighbor advantage| < 0 dB indicates neighbor preferable           |
| **Scheduled RB Difference**   | Serving cell scheduled RBs − neighbor cell scheduled RBs                 | RB count        | Higher neighbor RBs indicate better resource allocation | Negative values favor neighbor                 |
| **SINR Difference**            | Serving cell SINR − top neighbor SINR                                    | dB              | Neighbor SINR superiority contributes to throughput | Negative values favor neighbor                 |

### 4️⃣ Cross-Class Disambiguation

- **Vs C1:** C3 shows neighbor RSRP dominance; C1 shows serving cell dominant but weak edge.

- **Vs C4:** C4 involves PCI collision; C3 does not necessarily.

- **Overlap:** Possible with C5 if handovers frequent.

### 5️⃣ Alignment With Feature-Importance Tables

Throughput and RB allocation features are prominent in LightGBM results.

### 6️⃣ Failure & Edge Cases

- May fail if neighbor RBs are low or interference masks signals.

- Combine with mobility and PCI collision features for robustness.

---

## C4: Non-Colocated Co-Frequency Overlapping Coverage

### 1️⃣ Physical Failure Mechanism

Cells with identical PCI but spatially separated cause co-frequency interference, degrading SINR and throughput due to frequency reuse errors. This interference coupling decouples SINR from RSRP and causes handover instability.

### 2️⃣ Observable RF Signatures

- Multiple strong RSRP signals from neighbors with same PCI.

- Low correlation between SINR and RSRP (decoupling).

- Neighbor RSRP close to serving cell RSRP (<5 dB difference).

- Frequent ping-pong handovers.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **Co-frequency PCI Collision Ratio** | Number of neighbors with same PCI / total neighbors                    | Ratio / %       | Measures frequency reuse problem extent     | > 0.3 indicates collision risk                  |
| **SINR-RSRP Correlation Coefficient** | Pearson correlation between SINR and RSRP across samples with same PCI neighbors | Dimensionless   | Low correlation indicates interference dominance | < 0.5 indicates strong interference coupling   |
| **Neighbor RSRP Similarity Index** | Average absolute RSRP difference between serving cell and same PCI neighbors | dB              | Small difference indicates overlapping coverage | < 5 dB indicates overlap                         |
| **Interference-to-Signal Ratio (ISR)** | Estimated interference power / serving cell signal power               | Ratio / dB      | Quantifies interference level                | Higher ISR indicates interference problem       |

### 4️⃣ Cross-Class Disambiguation

- **Vs C3:** C4 involves PCI collision; C3 does not.

- **Vs C1/C2:** C4 driven by interference, not coverage geometry.

### 5️⃣ Alignment With Feature-Importance Tables

PCI collision and interference features are highly important in LightGBM models.

### 6️⃣ Failure & Edge Cases

- Dense urban deployments may mimic collisions; use spatial neighbor data to confirm.

---

## C5: Frequent Handovers Degrade Performance

### 1️⃣ Physical Failure Mechanism

High handover frequency causes signaling delays, data interruptions, and scheduling inefficiencies, degrading throughput and link stability. This is often mobility-driven or due to poor cell planning.

### 2️⃣ Observable RF Signatures

- Rapid serving PCI changes over time.

- SINR and RSRP fluctuations synchronized with handovers.

- Throughput dips around handover events.

- Variability in scheduled RBs.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **Handover Rate**              | Number of serving PCI changes / total measurement interval                | Hz (changes/sec)| Quantifies handover frequency                | > 0.1 Hz indicates frequent handovers          |
| **SINR Variance Near Handovers** | Variance of SINR in time windows around handover events                  | (dB)^2          | High variance indicates unstable signal     | Elevated variance during handovers              |
| **Throughput Drop Ratio at Handovers** | Mean throughput pre-handover / mean throughput post-handover          | Dimensionless   | Throughput degradation due to handover      | Ratio < 1 indicates drop                         |
| **RB Count Variability**       | Standard deviation of RB count around handover timestamps                 | RB count        | Scheduling inefficiency during handovers    | High variability indicates disruption           |

### 4️⃣ Cross-Class Disambiguation

- **Vs C7 (UE speed):** C5 focuses on handover count; C7 on speed.

- Combine speed and handover features to resolve overlap.

### 5️⃣ Alignment With Feature-Importance Tables

Temporal PCI changes and scheduling variability align with importance rankings.

### 6️⃣ Failure & Edge Cases

- Sparse data may miss handovers; stationary UEs near borders may cause false positives.

- Use speed and RB features to guard misclassification.

---

## C6: PCI mod-30 Collision

### 1️⃣ Physical Failure Mechanism

Cells with PCI values differing by multiples of 30 cause cyclic interference due to reuse patterns, degrading SINR and impairing neighbor measurements and handovers.

### 2️⃣ Observable RF Signatures

- Neighbor PCI mod 30 equals serving PCI mod 30.

- SINR degradation disproportionate to RSRP.

- Increased interference-related throughput drops.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **PCI mod-30 Collision Indicator** | Binary flag if any neighbor PCI mod 30 == serving PCI mod 30            | Binary (0/1)    | Identifies mod-30 collision presence         | 1 indicates collision                           |
| **SINR-RSRP Decoupling in Collision Regions** | Correlation coefficient between SINR and RSRP where collision detected | Dimensionless   | Low correlation indicates interference       | < 0.5 indicates collision interference          |
| **Interference Power Increase** | Difference in interference power during collision vs average             | dB              | Quantifies collision impact                   | Positive increase indicates collision effect    |

### 4️⃣ Cross-Class Disambiguation

- Differs from C4 by cyclic PCI relation, not general PCI reuse.

- Distinguished from C3 and C1 by interference pattern linked to PCI arithmetic.

### 5️⃣ Alignment With Feature-Importance Tables

PCI collision and interference features are prominent.

### 6️⃣ Failure & Edge Cases

- Sparse neighbor data may hide collisions.

- False negatives if PCI allocation not mod-30 aligned.

---

## C7: UE Speed > 40 km/h

### 1️⃣ Physical Failure Mechanism

High UE speed induces rapid channel fading and Doppler shifts, reducing link stability and throughput, and increasing handover frequency.

### 2️⃣ Observable RF Signatures

- GPS speed > 40 km/h.

- Increased short-term SINR and RSRP variance.

- Frequent serving PCI changes.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **GPS UE Speed**               | Logged GPS speed from drive test data                                    | km/h            | Direct measure of user mobility               | > 40 km/h indicates high speed                  |
| **SINR Variance (short window)** | Variance of SINR over short time window (e.g., 1s)                      | (dB)^2          | Reflects fast fading due to mobility          | Elevated variance indicates high speed          |
| **Consecutive PCI Change Count** | Number of serving PCI changes within 10s window                         | Count           | Reflects mobility-induced cell transitions    | High count indicates fast mobility               |

### 4️⃣ Cross-Class Disambiguation

- Differs from C5 by focus on speed rather than handover count.

- Combine speed and handover features for clarity.

### 5️⃣ Alignment With Feature-Importance Tables

Speed is a top feature; SINR variance and PCI changes complement.

### 6️⃣ Failure & Edge Cases

- Stationary UEs in moving vehicles or GPS errors may mislead.

- Sensor fusion recommended for validation.

---

## C8: Low Scheduled RBs (<160)

### 1️⃣ Physical Failure Mechanism

Low downlink RB allocation due to traffic load, scheduler policies, or congestion limits throughput regardless of RF quality.

### 2️⃣ Observable RF Signatures

- Scheduled RB count persistently below 160.

- Throughput lower than expected given RSRP and SINR.

- No significant interference or PCI anomalies.

### 3️⃣ Candidate Physics Features

| Feature Name                  | Formula / Computation                                                      | Units           | Causal Meaning                              | Expected Direction / Threshold                |
|-------------------------------|---------------------------------------------------------------------------|-----------------|----------------------------------------------|-----------------------------------------------|
| **Scheduled RB Count**         | Number of Layer 1 DL RBs allocated                                       | RB count        | Direct measure of resource allocation         | < 160 indicates low scheduling                  |
| **Throughput Efficiency Ratio**| Throughput / Scheduled RB count                                          | Mbps per RB     | Measures throughput efficiency per resource   | Low value indicates scheduling or link issues  |
| **RSRP-to-Throughput Ratio**   | RSRP (dBm) / Throughput (Mbps)                                           | dB per Mbps     | High ratio suggests throughput bottleneck beyond RF | Elevated ratio indicates scheduling bottleneck |

### 4️⃣ Cross-Class Disambiguation

- Differentiates from RF-driven classes (C1–C4) and mobility (C7) by focusing on scheduling.

- Overlaps throughput issues but low RB allocation is key.

### 5️⃣ Alignment With Feature-Importance Tables

RB allocation features highly important for C8.

### 6️⃣ Failure & Edge Cases

- Dynamic scheduling may cause transient low RBs; time averaging recommended.

- UE capability limits may affect RB allocation.

---

# Summary Table: Class → Physics Mechanism → Top 3 Features

| Class | Physics Mechanism                            | Top 3 Features                                                  |
|-------|--------------------------------------------|----------------------------------------------------------------|
| C1    | Excessive downtilt geometry                 | RSRP Gradient, Effective Downtilt Angle, SINR-RSRP Correlation |
| C2    | Antenna overshooting coverage footprint     | Coverage Radius at −100 dBm, RSRP Slope, Neighbor-to-Serving RSRP Ratio |
| C3    | Neighbor cell throughput dominance           | Neighbor/Serving Throughput Ratio, RSRP Difference, Scheduled RB Difference |
| C4    | Co-frequency PCI overlap causing interference| PCI Collision Ratio, SINR-RSRP Decoupling, Neighbor RSRP Similarity |
| C5    | Frequent handovers degrading performance     | Handover Rate, SINR Variance at Handovers, Throughput Drop Ratio |
| C6    | PCI mod-30 cyclic interference               | PCI mod-30 Collision Indicator, SINR-RSRP Decoupling, Interference Power Increase |
| C7    | High UE speed-induced fading                  | GPS UE Speed, SINR Variance, Consecutive PCI Change Count      |
| C8    | Low scheduled RBs causing throughput loss    | Scheduled RB Count, Throughput Efficiency Ratio, RSRP-to-Throughput Ratio |

---

# High-Value Composite Features

- **Geometry + RF:** RSRP Gradient combined with Effective Downtilt Angle quantifies coverage shape changes due to antenna settings.

- **RF + Throughput:** Throughput Efficiency Ratio (Throughput / Scheduled RBs) captures resource utilization beyond raw radio metrics.

- **Interference + Stability:** SINR vs RSRP Decoupling Index plus SINR Variance identify interference-dominant conditions with temporal instability.

---

# Recommendations

**For Tree-Based Models:**  
- Use precise numerical features with clear physical meaning and thresholds (e.g., RSRP Gradient, Scheduled RB Count, Handover Rate, PCI Collision Indicator) for robust, explainable splits.

**For LLM Reasoning Prompts:**  
- Employ composite, causally interpretable features that map to whiteboard physics concepts (e.g., downtilt-induced coverage loss, PCI collision interference patterns) to enhance interpretability and reasoning.

---

## References

[1] 3GPP TS 38.214, "NR; Physical layer procedures for data," 3rd Generation Partnership Project; Technical Specification Group Radio Access Network, 2020. [Online]. Available: <https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=3208> (target="_blank")

[2] S. Sesia, I. Toufik, and M. Baker, *LTE - The UMTS Long Term Evolution: From Theory to Practice*, 2nd ed., Wiley, 2011.

[3] M. Polese, M. Mezzavilla, and M. Zorzi, "Improved handover through dual connectivity in 5G mmWave mobile networks," *IEEE Journal on Selected Areas in Communications*, vol. 35, no. 9, pp. 2069–2084, 2017. DOI: 10.1109/JSAC.2017.2712420

[4] J. Zhang et al., "Machine learning for 5G and beyond: From theory to practice," *IEEE Communications Surveys & Tutorials*, vol. 22, no. 3, pp. 1702–1725, 2020. DOI: 10.1109/COMST.2020.2988299

[5] Y. Liu et al., "Root Cause Analysis of Anomalies in 5G RAN Using Graph Neural Network and Transformer," arXiv preprint arXiv:2406.15638, 2024. [Online]. Available: <https://arxiv.org/abs/2406.15638v1> (target="_blank")

[6] A. Ghosh et al., *Fundamentals of LTE*, Prentice Hall, 2010.

---

*Report prepared by 5G RAN Optimization Research Agent*