
# Fine-Tuning Improvements Based on Physics Research

## Summary of Current Approach ✅

Your current fine-tuning strategy is **strong** and already incorporates many best practices:

1. **Anti-Catastrophic Forgetting**: System prompt frames model as "helpful AI assistant" applying analytical reasoning, NOT as domain expert
2. **Principle-Based Learning**: Teaches physical reasoning patterns, not memorized templates
3. **Natural Reasoning Variants**: 2 diverse examples per class prevent overfitting to templates
4. **Proper Data Split**: 85/15 train/val with stratification maintains class distribution

## Key Insights from Research Paper 📊

The `research_final_report.md` provides **physics-grounded feature formalization** for C1-C8:

### Core Physics Principles

| Root Cause | Physical Mechanism | Key Observable Signature |
|------------|-------------------|--------------------------|
| **C1 - Excessive Downtilt** | Antenna beam angle too steep downward | **RSRP gradient > -10 dB/100m**, RSRP-SINR correlated, weak far-edge |
| **C2 - Overshoot** | Insufficient tilt extends coverage >1km | **Shallow RSRP decay**, extended radius >1000m, neighbor weak near-site |
| **C3 - Wrong Cell** | Geometry/penetration favors neighbor | **Neighbor RSRP stronger**, throughput improves post-handover |
| **C4 - Overlapping Coverage** | Co-frequency PCI collision/overlap | **SINR-RSRP decoupled**, multiple strong neighbors within 5dB, PCI collision |
| **C5 - Ping-Pong** | Hysteresis/handover params misconfigured | **Handover rate >0.1 Hz**, repeated PCI changes, small RSRP deltas |
| **C6 - PCI Mod-30** | Same PCI mod-30 across cells | **Interference at specific locations**, PCI collision indicator |
| **C7 - High Speed** | Doppler/tracking at >40 km/h | **Speed >40 km/h**, SINR variance, speed-TP correlation negative |
| **C8 - Resource Congestion** | Low RB allocation despite demand | **RB count <160**, poor RB-to-throughput efficiency |

### Critical Feature Relationships

1. **RSRP-SINR Correlation**:
   - **Correlated degradation** → Coverage issue (C1, C2)
   - **Decoupled** (good RSRP, poor SINR) → Interference (C4, C6)

2. **Spatial Gradients**:
   - **Steep RSRP decay** (>-10 dB/100m) → Excessive downtilt (C1)
   - **Shallow decay** (<-5 dB/100m) → Overshoot (C2)

3. **Neighbor Relationships**:
   - **Single dominant neighbor** → Wrong cell selection (C3)
   - **Multiple equal neighbors** (within 5 dB) → Overlapping coverage (C4)

4. **Temporal Patterns**:
   - **Handover frequency** >0.1 Hz → Ping-pong (C5)
   - **Speed-correlated** degradation → Mobility (C7)

## Recommended Improvements 🚀

### 1. **Enhanced System Prompt** (Already Implemented ✅)

I've already updated your system prompt in the notebook to include:
- Physics-based thresholds (RSRP gradients, downtilt angles, speed thresholds)
- Explicit RSRP-SINR correlation guidance
- Spatial gradient interpretation
- Interference signature detection
- Resource efficiency metrics

### 2. **Add Physics-Based Feature Context to Training Examples**

**Current approach**: Your reasoning examples mention features but don't always explicitly compute physics metrics.

**Enhancement**: Add explicit physics calculations to some reasoning variants:
```python
# Example for C1 - Add gradient calculation
f"""First, let me calculate the RSRP spatial gradient:
- RSRP at cell center (min dist {dist_min}m): {rsrp_at_min} dBm
- RSRP at cell edge (max dist {dist_max}m): {rsrp_at_max} dBm
- Gradient = ({rsrp_at_max} - {rsrp_at_min}) / ({dist_max} - {dist_min}) × 100
- Gradient = {gradient:.2f} dB/100m

This gradient of {gradient:.2f} dB/100m is **steeper than typical** (-8 to -10 dB/100m),
indicating rapid signal decay characteristic of excessive downtilt (C1).

The effective downtilt is {tilt}°, which for this cell radius is excessive...
"""
```

### 3. **Add Explicit Disambiguation Examples**

**Current**: Your examples implicitly rule out other classes.

**Enhancement**: Add explicit comparison sections:

```python
# Example disambiguation reasoning
f"""**Disambiguating between C1 (Downtilt) vs C2 (Overshoot):**
- C1 signature: Steep gradient + coverage holes at far edge
- C2 signature: Shallow gradient + extended coverage >1km

In this case:
- RSRP gradient: {gradient:.2f} dB/100m (steep → C1)
- Max distance: {dist_max}m (normal range → NOT C2)
- Conclusion: C1 pattern confirmed

**Disambiguating vs C4 (Interference):**
- If interference: RSRP good, SINR poor (decoupled)
- Observed: RSRP {rsrp_mean} dBm, SINR {sinr_mean} dB (both weak, correlated)
- Conclusion: Coverage-driven, not interference → C1
"""
```

### 4. **Physics-Based Feature Engineering Suggestions**

The research identifies high-value composite features. Consider adding these to your dataset:

| Composite Feature | Formula | Purpose |
|-------------------|---------|---------|
| **RSRP Gradient** | `(RSRP_p95 - RSRP_p5) / (dist_p95 - dist_p5) × 100` | Quantifies C1 vs C2 |
| **SINR-RSRP Correlation** | `pearson_corr(SINR, RSRP)` | Detects interference (C4, C6) |
| **Neighbor RSRP Spread** | `std(neighbor_rsrp_values)` | Distinguishes C3 vs C4 |
| **Speed-TP Correlation** | `pearson_corr(speed, throughput)` | Confirms C7 |
| **RB Efficiency** | `mean(throughput / scheduled_RB)` | Quantifies C8 |

### 5. **Add "Physical Contradiction" Training Examples**

Teach the model to recognize when features conflict with hypotheses:

```python
# Example: Ruling out C1 when gradient is normal
f"""**Testing C1 Hypothesis (Excessive Downtilt):**

C1 prediction: RSRP gradient should be steep (>-10 dB/100m) with weak far edge.

Observed gradient calculation:
- Distance range: {dist_p5}m to {dist_p95}m
- RSRP range: {rsrp_p5} to {rsrp_p95} dBm
- Computed gradient: {gradient:.2f} dB/100m

**Physical contradiction**: The gradient of {gradient:.2f} dB/100m is within
normal path loss range (-8 to -10 dB/100m). This does NOT match the steep
decay expected from excessive downtilt.

Therefore, C1 is RULED OUT based on physics.
"""
```

### 6. **Include Multi-Hypothesis Reasoning Chains**

Add examples where multiple causes are plausible initially, then systematically eliminated:

```python
f"""**Initial Hypotheses Based on Symptoms:**

Symptom: Poor throughput ({tp_mean} Mbps) + Adequate RSRP ({rsrp_mean} dBm)

Plausible causes:
- C4 (Interference): Would show poor SINR despite good RSRP ← CHECK
- C8 (Congestion): Would show low RB allocation ← CHECK  
- C3 (Wrong Cell): Would improve after handover ← CHECK

**Testing C4 (Interference):**
- SINR: {sinr_mean} dB (poor ✓)
- RSRP: {rsrp_mean} dBm (adequate ✓)
- Neighbor count: {neighbor_count} strong neighbors
- PCI collision: {pci_collision_detected}
- VERDICT: C4 hypothesis **SUPPORTED**

**Testing C8 (Congestion):**
- Mean RB allocation: {rb_mean} RBs (high → C8 unlikely)
- VERDICT: C8 hypothesis **REJECTED**

**Testing C3 (Wrong Cell):**
- Handover TP improvement: {ho_tp_delta} Mbps (minimal)
- VERDICT: C3 hypothesis **REJECTED**

**Final Diagnosis:** C4 confirmed by interference signature.
\\boxed{{4}}
"""
```

## Training Optimization Recommendations 📈

### Hyperparameters (Already covered in your markdown cell ✅)

Your updated training config is excellent:
- Unsloth + LoRA for efficiency
- 4-bit quantization for memory
- GPU-specific batch sizes
- Proper validation setup

### Additional Training Tips

1. **Use Physics-Aware Loss Weighting** (Optional):
   - Weight misclassifications by physical similarity
   - C1↔C2 confusion is more acceptable than C1↔C7
   - Create confusion matrix penalty based on physics distance

2. **Add Validation Metrics**:
   ```python
   # Track physics-aware metrics
   - Accuracy by root cause
   - Confusion between physically similar classes
   - Reasoning coherence (does explanation match prediction?)
   ```

3. **Monitor Catastrophic Forgetting**:
   ```python
   # Add general reasoning validation examples (NOT telco)
   val_examples = [
       {"type": "math", "example": "If x + 5 = 12, what is x? Show reasoning."},
       {"type": "logic", "example": "All birds have wings. Penguins are birds. What can we conclude?"},
       {"type": "history", "example": "Why did the industrial revolution begin in Britain?"}
   ]
   # Periodically test on these during training
   ```

## Testing Your Fine-Tuned Model 🧪

After fine-tuning, validate with:

### 1. **Physics Consistency Tests**
```python
test_cases = [
    {
        "scenario": "C1 with WRONG gradient",
        "features": {"gradient": -8.5, "tilt": 12, ...},  # Normal gradient but high tilt
        "expected": "Should recognize gradient contradicts C1"
    },
    {
        "scenario": "C4 with correlated RSRP-SINR", 
        "features": {"rsrp": -95, "sinr": 8, "correlation": 0.9, ...},
        "expected": "Should recognize correlation rules out interference"
    }
]
```

### 2. **Ambiguous Cases**
```python
edge_cases = [
    "C1 + C7: High speed near cell edge with excessive downtilt",
    "C3 + C4: Neighbor better but also has interference",
    "C5 + C7: Ping-pong during high-speed mobility"
]
# Model should identify primary cause and acknowledge secondary factors
```

### 3. **General Reasoning Preservation**
```python
general_tests = [
    "Solve: 2x + 5 = 15. Show your work.",
    "Explain why water boils at lower temperatures at high altitudes.",
    "A train leaves Chicago at 60 mph..."
]
# Should maintain base reasoning abilities
```

## Summary of Changes Made ✅

I've updated your `instuct.ipynb` with:

1. **Enhanced System Prompt** (Lines ~1231-1267):
   - Added physics thresholds (RSRP gradients, speed limits, PCI collision)
   - Explicit RSRP-SINR correlation guidance
   - Spatial gradient interpretation with quantitative thresholds
   - Interference signatures with physical mechanisms
   - Root cause signatures with observable RF physics

The prompt now teaches:
- **When** features indicate specific root causes (thresholds)
- **Why** those features matter (physical mechanisms)  
- **How** to distinguish similar classes (disambiguation logic)

## Next Steps 🎯

1. **Generate datasets with new prompt**:
   ```bash
   # Run cells 13-16 in your notebook
   ```

2. **Verify examples look good**:
   ```python
   # Check a few samples from qwen_rca_train_principle_based.jsonl
   # Ensure physics reasoning is present
   ```

3. **Train with Unsloth**:
   ```python
   # Use the config from markdown cell 30
   # Monitor val_loss and physics-aware metrics
   ```

4. **Test on validation set**:
   ```python
   # Run inference on qwen_rca_val_principle_based.jsonl
   # Check reasoning quality, not just accuracy
   ```

5. **Validate catastrophic forgetting**:
   ```python
   # Test on general reasoning examples
   # Ensure model still handles math, logic, etc.
   ```

## Expected Improvements 📊

Based on the physics enhancements:

- **Better discrimination** between C1 ↔ C2 (gradient-based)
- **Stronger interference detection** for C4, C6 (SINR-RSRP decoupling)
- **More robust C7 detection** (explicit speed thresholds)
- **Clearer C8 reasoning** (RB efficiency metrics)
- **Improved explainability**: Reasoning traces show physical calculations

The key innovation: Model learns to **compute physics features** (gradients, correlations) as part of reasoning, not just pattern match on raw values.
