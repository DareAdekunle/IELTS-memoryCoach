# Setting Truncation Side: Critical Configuration

## The Question

**"Can truncation_side be set in SFTConfig?"**

## The Answer

**NO** - `truncation_side` is a **tokenizer property**, not a training config parameter.

## Where to Set It

### ❌ WRONG - This doesn't exist:

```python
config = SFTConfig(
    max_seq_length=4096,
    truncation_side="left",  # ← NO SUCH PARAMETER!
    # ...
)
```

### ✅ CORRECT - Set it on the tokenizer:

```python
# Load model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct",
    max_seq_length=4096,
    load_in_4bit=True,
)

# Configure tokenizer BEFORE training
tokenizer.truncation_side = "left"   # ← Set this directly!
tokenizer.padding_side = "right"

# Now use in trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,  # Tokenizer with left truncation
    train_dataset=train_ds,
    args=config,
)
```

## Complete Setup Sequence

### 1. Load Model & Tokenizer

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct",
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
)
```

### 2. Configure Tokenizer (CRITICAL STEP!)

```python
# This is where truncation_side lives
tokenizer.truncation_side = "left"   # Preserve answer at end
tokenizer.padding_side = "right"     # Standard for causal LM

# Verify
print(f"Truncation side: {tokenizer.truncation_side}")
```

### 3. Configure LoRA

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=32,  # alpha = 2*r
    # ...
)
```

### 4. Configure Training (SFTConfig)

```python
config = SFTConfig(
    max_seq_length=4096,  # Maximum sequence length
    # Note: truncation_side NOT here - already set on tokenizer!
    per_device_train_batch_size=1,
    # ...
)
```

### 5. Create Trainer

```python
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,  # ← Uses your configured tokenizer
    train_dataset=train_ds,
    args=config,
)
```

## Why This Matters

### Default Behavior (Right Truncation)

```
Input: [System][Context 1-3000 tokens][Reasoning][Answer: \boxed{3}]
                                      ↑ CUT HERE AT 4096
Output: [System][Context 1-3000 tokens][Reasoning][Answ...
                                                        ↑ LOST!
```

**Result:** Model never sees the answer, training fails.

### With Left Truncation

```
Input: [System][Context 1-3000 tokens][Reasoning][Answer: \boxed{3}]
       ↑ CUT HERE
Output: [Context 2000-3000 tokens][Reasoning][Answer: \boxed{3}]
                                               ↑ PRESERVED!
```

**Result:** Model always sees reasoning + answer, training succeeds.

## Verification Test

```python
# Test truncation behavior
test_text = "A" * 10000 + "\n\nAnswer: \\boxed{3}"
tokens = tokenizer(test_text, max_length=4096, truncation=True)
decoded = tokenizer.decode(tokens.input_ids)

print("Last 200 chars:", decoded[-200:])
# Should contain: \boxed{3}

if "\\boxed{" in decoded:
    print("✅ Truncation configured correctly!")
else:
    print("❌ Check tokenizer.truncation_side")
```

## Common Mistakes

### ❌ Mistake 1: Trying to set in config

```python
config = SFTConfig(
    truncation_side="left",  # This parameter doesn't exist!
)
```

### ❌ Mistake 2: Setting after trainer creation

```python
trainer = SFTTrainer(...)
tokenizer.truncation_side = "left"  # Too late! Trainer already initialized
```

### ❌ Mistake 3: Not setting at all

```python
# Using default right truncation
# Your answers will be lost!
```

### ✅ Correct Approach

```python
# 1. Load tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(...)

# 2. Configure IMMEDIATELY
tokenizer.truncation_side = "left"

# 3. Pass to trainer
trainer = SFTTrainer(tokenizer=tokenizer, ...)
```

## Summary

| Aspect | Value |
|--------|-------|
| **Parameter** | `truncation_side` |
| **Object** | `tokenizer` (not config) |
| **Valid values** | `"left"` or `"right"` |
| **When to set** | After loading tokenizer, before training |
| **Why left** | Preserves reasoning + answer at sequence end |
| **Your use case** | `"left"` to keep `\boxed{n}` answer |

## Quick Checklist

Before running `trainer.train()`:

- [ ] Loaded tokenizer from model
- [ ] Set `tokenizer.truncation_side = "left"`
- [ ] Set `tokenizer.padding_side = "right"`
- [ ] Verified with print statement
- [ ] Passed tokenizer to SFTTrainer
- [ ] Tested with verification cell

**Bottom line:** Truncation direction is a **tokenizer setting**, not a trainer config!
